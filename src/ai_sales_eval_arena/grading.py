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
    """Centralized prompt templates for grading."""
    
    RUBRIC = """
# Sales Pitch Evaluation Rubric

## Scoring Scale
- 4 (Excellent): Exceeds expectations, demonstrates mastery
- 3 (Very Good): Meets expectations with strong execution  
- 2 (Good): Meets basic expectations, room for improvement
- 1 (Needs Improvement): Below expectations, significant gaps

## Evaluation Criteria

### 1. ICP Alignment (Ideal Customer Profile)
**4 (Excellent)**: Demonstrates deep research with 75%+ ICP criteria met, uses specific company examples, shows clear understanding of prospect's business model and challenges.

**3 (Very Good)**: Shows good research with 50-74% ICP criteria met, references relevant industry trends or company information.

**2 (Good)**: Basic research evident with 25-49% ICP criteria met, general industry knowledge without specific company details.

**1 (Needs Improvement)**: Little to no research evident, 0-24% ICP criteria met, generic approach without customization.

### 2. PBO Messaging Alignment (Positive Business Outcomes)
**4 (Excellent)**: Messaging precisely tied to specific lead pain points, quantifies business impact, connects technical features to business outcomes.

**3 (Very Good)**: Good messaging alignment with clear business benefits, some quantification of impact.

**2 (Good)**: Accurate messaging but limited impact for target personas, generic business benefits.

**1 (Needs Improvement)**: Poor alignment with PBOs, focuses on features without business context.

### 3. Continuous Profiling Explanation
**4 (Excellent)**: Clear, detailed explanation with concrete examples, explains benefits and differentiators, uses appropriate technical depth for audience.

**3 (Very Good)**: Clear explanation with good understanding, lacks some depth or examples.

**2 (Good)**: High-level explanation of profiling concepts without sufficient specificity or examples.

**1 (Needs Improvement)**: Vague or confusing explanation, demonstrates poor understanding of the technology.

### 4. Observability Context
**4 (Excellent)**: Explains profiling in context of 2+ observability signals (metrics, logs, traces), shows how they complement each other.

**3 (Very Good)**: Explains profiling in context of 1 observability signal, good understanding of ecosystem.

**2 (Good)**: Mentions observability concepts but doesn't clearly connect profiling to the broader ecosystem.

**1 (Needs Improvement)**: No connection to observability signals, treats profiling as isolated tool.

### 5. Talk Track Alignment
**4 (Excellent)**: High PBO accuracy effectively tied to account research, natural flow, handles objections proactively.

**3 (Very Good)**: Good PBO accuracy with adequate research connection, mostly natural delivery.

**2 (Good)**: Accurate messaging but limited research integration, some awkward transitions.

**1 (Needs Improvement)**: Poor accuracy, little research integration, choppy or confusing delivery.
"""

    INDIVIDUAL_EVALUATION = """
You are an expert sales trainer evaluating a sales pitch for Pyroscope (continuous profiling tool). 

## Context
Pyroscope helps developers optimize application performance by providing continuous, code-level profiling data. Key value propositions:
- Faster incident resolution through code-level visibility
- Reduced infrastructure costs via optimization insights  
- Improved application reliability and performance
- Seamless integration with existing observability stack

## Your Task
Evaluate this sales pitch transcript against the provided rubric. Be thorough, fair, and constructive in your feedback.

## Rubric
{rubric}

## Transcript to Evaluate
{transcript}

## Instructions
1. Read the transcript carefully
2. Evaluate each criterion using the 4-point scale
3. Provide specific examples from the transcript to support your scores
4. Offer constructive feedback for improvement
5. Calculate an overall score (average of all criteria)

Respond ONLY with valid JSON in this exact format:
{{
  "criterion_grades": [
    {{
      "criterion": "icp_alignment",
      "score": 3.0,
      "explanation": "Specific explanation with examples from transcript",
      "feedback": "Constructive suggestions for improvement"
    }},
    {{
      "criterion": "pbo_messaging",
      "score": 2.0,
      "explanation": "Specific explanation with examples from transcript", 
      "feedback": "Constructive suggestions for improvement"
    }},
    {{
      "criterion": "profiling_explanation",
      "score": 4.0,
      "explanation": "Specific explanation with examples from transcript",
      "feedback": "Constructive suggestions for improvement"
    }},
    {{
      "criterion": "observability_context", 
      "score": 3.0,
      "explanation": "Specific explanation with examples from transcript",
      "feedback": "Constructive suggestions for improvement"
    }},
    {{
      "criterion": "talk_track_alignment",
      "score": 2.0,
      "explanation": "Specific explanation with examples from transcript",
      "feedback": "Constructive suggestions for improvement"
    }}
  ],
  "overall_score": 2.8,
  "overall_feedback": "Comprehensive summary of strengths and areas for improvement"
}}
"""

    COMPARATIVE_EVALUATION = """
You are an expert sales trainer comparing two sales pitch performances for Pyroscope (continuous profiling tool).

## Context  
Pyroscope helps developers optimize application performance by providing continuous, code-level profiling data. Key value propositions:
- Faster incident resolution through code-level visibility
- Reduced infrastructure costs via optimization insights
- Improved application reliability and performance  
- Seamless integration with existing observability stack

## Your Task
Compare these two sales pitches and determine which is more effective overall. Consider all aspects of sales effectiveness.

## Evaluation Criteria
- ICP Alignment: Research quality and prospect targeting
- PBO Messaging: Business outcome focus and impact quantification
- Profiling Explanation: Technical accuracy and clarity
- Observability Context: Integration with monitoring ecosystem
- Talk Track Alignment: Flow, research integration, objection handling

## Participant A ({participant_a_name})
{transcript_a}

## Participant B ({participant_b_name})  
{transcript_b}

## Instructions
1. Analyze both pitches thoroughly
2. Compare their relative strengths and weaknesses
3. Determine the overall winner based on sales effectiveness
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
        
    async def grade_transcript(
        self, 
        transcript: Transcript, 
        participant: Participant
    ) -> Grade:
        """Grade a single transcript."""
        try:
            logger.info(f"Grading transcript for {participant.name}")
            
            # Prepare the prompt
            prompt = self.prompts.INDIVIDUAL_EVALUATION.format(
                rubric=self.prompts.RUBRIC,
                transcript=transcript.content
            )
            
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
            prompt = self.prompts.COMPARATIVE_EVALUATION.format(
                participant_a_name=participant_a.name,
                transcript_a=transcript_a.content,
                participant_b_name=participant_b.name,
                transcript_b=transcript_b.content
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