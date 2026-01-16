"""AI-powered grading engine for sales pitch evaluation."""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID

import anthropic
from pydantic import BaseModel, ValidationError

from .models import (
    Transcript, Grade, CriterionGrade, GradingCriterion, 
    Participant, ArenaConfig
)

logger = logging.getLogger(__name__)


class GradingPrompts:
    """Centralized prompt templates for grading.
    
    These are DEFAULT templates. When using the library generically, you MUST provide
    your own rubric_text and evaluation_context_text via ArenaConfig, otherwise
    the defaults below (which are Pyroscope-specific examples) will be used.
    """
    
    # Generic fallback context - users should always override this
    DEFAULT_CONTEXT = """
You are evaluating sales pitch quality. Consider the overall effectiveness of the pitch
including clarity, persuasiveness, objection handling, and value proposition communication.
"""

    # Generic fallback rubric - users should always override this
    RUBRIC = """
# Sales Pitch Evaluation Rubric

## Scoring Scale
- 4 (Excellent): Exceeds expectations, demonstrates mastery
- 3 (Very Good): Meets expectations with strong execution  
- 2 (Good): Meets basic expectations, room for improvement
- 1 (Needs Improvement): Below expectations, significant gaps

## Evaluation Criteria

Evaluate the pitch holistically considering:
- Research and preparation quality
- Clear communication of value proposition
- Handling of objections and questions
- Natural flow and delivery
- Connection of features to business outcomes
"""

    INDIVIDUAL_EVALUATION = """
You are an expert evaluator assessing a performance.

## Context
{context}

## Your Task
Evaluate this transcript against the provided rubric. Be thorough, fair, and constructive in your feedback.

## Rubric
{rubric}

## Transcript to Evaluate
{transcript}

## Instructions
1. Read the transcript carefully
2. Evaluate against the criteria in the rubric using the scoring scale
3. Provide specific examples from the transcript to support your assessment
4. Offer constructive feedback for improvement
5. Calculate an overall score

Respond ONLY with valid JSON in this format:
{{
  "criterion_grades": [
    {{
      "criterion": "criterion_name_from_rubric",
      "score": 3.0,
      "explanation": "Specific explanation with examples from transcript",
      "feedback": "Constructive suggestions for improvement"
    }}
  ],
  "overall_score": 3.0,
  "overall_feedback": "Comprehensive summary of strengths and areas for improvement"
}}
"""

    COMPARATIVE_EVALUATION = """
You are an expert evaluator comparing two performances.

## Context
{context}

## Rubric
{rubric}

## Your Task
Compare these two pitches and determine which is more effective overall based on the rubric above.

## Participant A ({participant_a_name})
{transcript_a}

## Participant B ({participant_b_name})  
{transcript_b}

## Instructions
1. Analyze both pitches thoroughly against the rubric
2. Compare their relative strengths and weaknesses
3. Determine the overall winner based on the evaluation criteria
4. Provide specific examples to support your decision
5. Offer insights into what made the difference

Respond ONLY with valid JSON in this exact format:
{{
  "winner_name": "{participant_a_name}",
  "winner_reasoning": "Detailed explanation of why this participant won",
  "participant_a_strengths": ["Strength 1", "Strength 2", "Strength 3"],
  "participant_a_weaknesses": ["Weakness 1", "Weakness 2"],
  "participant_b_strengths": ["Strength 1", "Strength 2"],
  "participant_b_weaknesses": ["Weakness 1", "Weakness 2", "Weakness 3"],
  "key_differentiators": ["Factor 1", "Factor 2"],
  "improvement_suggestions": {{
    "{participant_a_name}": "Specific feedback for improvement",
    "{participant_b_name}": "Specific feedback for improvement"
  }}
}}
"""


class GradingResponse(BaseModel):
    """Structured response from AI grading."""
    criterion_grades: List[Dict[str, Any]]
    overall_score: float
    overall_feedback: str


class ComparisonResponse(BaseModel):
    """Structured response from AI comparison."""
    winner_name: str
    winner_reasoning: str
    participant_a_strengths: List[str]
    participant_a_weaknesses: List[str]
    participant_b_strengths: List[str]
    participant_b_weaknesses: List[str]
    key_differentiators: List[str]
    improvement_suggestions: Dict[str, str]


class AIGrader:
    """AI-powered grading engine for sales pitches."""
    
    def __init__(self, config: ArenaConfig):
        """Initialize the grader with configuration."""
        self.config = config
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.prompts = GradingPrompts()

    def _get_rubric_text(self) -> str:
        if self.config.rubric_text is not None:
            return self.config.rubric_text
        return self.prompts.RUBRIC

    def _get_context_text(self) -> str:
        if self.config.evaluation_context_text is not None:
            return self.config.evaluation_context_text
        return self.prompts.DEFAULT_CONTEXT

    def _build_individual_prompt(self, transcript: Transcript) -> str:
        template = self.config.individual_prompt_template or self.prompts.INDIVIDUAL_EVALUATION
        return template.format(
            rubric=self._get_rubric_text(),
            transcript=transcript.content,
            context=self._get_context_text()
        )

    def _build_comparative_prompt(
        self,
        transcript_a: Transcript,
        participant_a: Participant,
        transcript_b: Transcript,
        participant_b: Participant
    ) -> str:
        template = self.config.comparative_prompt_template or self.prompts.COMPARATIVE_EVALUATION
        return template.format(
            participant_a_name=participant_a.name,
            transcript_a=transcript_a.content,
            participant_b_name=participant_b.name,
            transcript_b=transcript_b.content,
            context=self._get_context_text(),
            rubric=self._get_rubric_text()
        )
        
    async def grade_transcript(
        self, 
        transcript: Transcript, 
        participant: Participant
    ) -> Grade:
        """Grade a single transcript."""
        try:
            logger.info(f"Grading transcript for {participant.name}")
            
            # Prepare the prompt
            prompt = self._build_individual_prompt(transcript)
            
            # Make API call
            response = await self._make_api_call(prompt)
            
            # Parse response
            grading_data = self._parse_grading_response(response)
            
            # Convert to Grade model
            criterion_grades = []
            for grade_data in grading_data.criterion_grades:
                criterion_grades.append(CriterionGrade(
                    criterion=GradingCriterion(grade_data["criterion"]),
                    score=grade_data["score"],
                    explanation=grade_data["explanation"],
                    feedback=grade_data.get("feedback")
                ))
            
            grade = Grade(
                transcript_id=transcript.id,
                participant_id=participant.id,
                criterion_grades=criterion_grades,
                overall_score=grading_data.overall_score,
                overall_feedback=grading_data.overall_feedback,
                grader_model=self.config.anthropic_model
            )
            
            logger.info(f"Successfully graded {participant.name}: {grade.overall_score:.2f}")
            return grade
            
        except Exception as e:
            logger.error(f"Error grading transcript for {participant.name}: {e}")
            raise

    async def compare_transcripts(
        self,
        transcript_a: Transcript,
        participant_a: Participant,
        transcript_b: Transcript, 
        participant_b: Participant
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Compare two transcripts and determine winner."""
        try:
            logger.info(f"Comparing {participant_a.name} vs {participant_b.name}")
            
            # Prepare the prompt
            prompt = self._build_comparative_prompt(
                transcript_a=transcript_a,
                participant_a=participant_a,
                transcript_b=transcript_b,
                participant_b=participant_b
            )
            
            # Make API call
            response = await self._make_api_call(prompt)
            
            # Parse response
            comparison_data = self._parse_comparison_response(response)
            
            # Determine winner ID
            winner_name = comparison_data.winner_name
            if winner_name == participant_a.name:
                winner_id = str(participant_a.id)
            elif winner_name == participant_b.name:
                winner_id = str(participant_b.id)
            else:
                # Fallback to first participant if name doesn't match exactly
                logger.warning(f"Winner name '{winner_name}' doesn't match participants")
                winner_id = str(participant_a.id)
            
            feedback = comparison_data.winner_reasoning
            metadata = {
                "participant_a_strengths": comparison_data.participant_a_strengths,
                "participant_a_weaknesses": comparison_data.participant_a_weaknesses,
                "participant_b_strengths": comparison_data.participant_b_strengths,
                "participant_b_weaknesses": comparison_data.participant_b_weaknesses,
                "key_differentiators": comparison_data.key_differentiators,
                "improvement_suggestions": comparison_data.improvement_suggestions
            }
            
            logger.info(f"Comparison complete: {winner_name} wins")
            return winner_id, feedback, metadata
            
        except Exception as e:
            logger.error(f"Error comparing transcripts: {e}")
            raise

    async def _make_api_call(self, prompt: str) -> str:
        """Make an API call to Anthropic Claude."""
        try:
            # Combine system message and user prompt for Claude
            full_prompt = (
                "You are an expert sales trainer. Respond only with valid JSON as requested.\n\n"
                f"{prompt}"
            )
            
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.config.anthropic_model,
                max_tokens=2000,
                temperature=0.1,  # Low temperature for consistent grading
                messages=[
                    {"role": "user", "content": full_prompt}
                ]
            )
            
            # Extract text content from Claude's response
            content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text
            
            return content.strip()
            
        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            raise

    def _parse_grading_response(self, response: str) -> GradingResponse:
        """Parse and validate grading response."""
        try:
            # Try to extract JSON if response has extra text
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip()
            elif "{" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                response = response[start:end]
            
            data = json.loads(response)
            return GradingResponse(**data)
            
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to parse grading response: {e}")
            logger.error(f"Response was: {response}")
            raise ValueError(f"Invalid grading response format: {e}")

    def _parse_comparison_response(self, response: str) -> ComparisonResponse:
        """Parse and validate comparison response."""
        try:
            # Try to extract JSON if response has extra text
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip()
            elif "{" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                response = response[start:end]
            
            data = json.loads(response)
            return ComparisonResponse(**data)
            
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to parse comparison response: {e}")
            logger.error(f"Response was: {response}")
            raise ValueError(f"Invalid comparison response format: {e}")


class BatchGrader:
    """Batch processing for multiple grading operations."""
    
    def __init__(self, grader: AIGrader, max_concurrent: int = 5):
        """Initialize batch grader."""
        self.grader = grader
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
    async def grade_multiple(
        self, 
        transcript_participant_pairs: List[Tuple[Transcript, Participant]]
    ) -> List[Grade]:
        """Grade multiple transcripts concurrently."""
        tasks = []
        for transcript, participant in transcript_participant_pairs:
            task = self._grade_with_semaphore(transcript, participant)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log errors
        grades = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                transcript, participant = transcript_participant_pairs[i]
                logger.error(f"Failed to grade {participant.name}: {result}")
            else:
                grades.append(result)
        
        return grades
    
    async def compare_multiple(
        self, 
        comparison_pairs: List[Tuple[Transcript, Participant, Transcript, Participant]]
    ) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Compare multiple transcript pairs concurrently."""
        tasks = []
        for transcript_a, participant_a, transcript_b, participant_b in comparison_pairs:
            task = self._compare_with_semaphore(
                transcript_a, participant_a, transcript_b, participant_b
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log errors
        comparisons = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                _, participant_a, _, participant_b = comparison_pairs[i]
                logger.error(f"Failed to compare {participant_a.name} vs {participant_b.name}: {result}")
            else:
                comparisons.append(result)
        
        return comparisons
    
    async def _grade_with_semaphore(
        self, 
        transcript: Transcript, 
        participant: Participant
    ) -> Grade:
        """Grade with semaphore for concurrency control."""
        async with self.semaphore:
            return await self.grader.grade_transcript(transcript, participant)
    
    async def _compare_with_semaphore(
        self,
        transcript_a: Transcript,
        participant_a: Participant, 
        transcript_b: Transcript,
        participant_b: Participant
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Compare with semaphore for concurrency control."""
        async with self.semaphore:
            return await self.grader.compare_transcripts(
                transcript_a, participant_a, transcript_b, participant_b
            ) 