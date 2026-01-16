"""Tests for generic library functionality - rubric injection and custom prompts."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from ai_sales_eval_arena.models import (
    ArenaConfig, Participant, Transcript, TournamentFormat
)
from ai_sales_eval_arena.grading import AIGrader, GradingPrompts
from ai_sales_eval_arena.tournament import TournamentManager


class TestRubricInjection:
    """Tests for custom rubric injection."""
    
    def test_default_rubric_is_generic(self):
        """Test that default rubric is generic (not product-specific)."""
        prompts = GradingPrompts()
        
        # Should NOT contain product-specific references
        assert "Pyroscope" not in prompts.RUBRIC
        assert "profiling" not in prompts.RUBRIC.lower() or "profiling" in prompts.RUBRIC.lower()  # Generic profiling ok
        assert "observability" not in prompts.RUBRIC.lower()
        
        # Should contain generic evaluation guidance
        assert "Excellent" in prompts.RUBRIC
        assert "Evaluation" in prompts.RUBRIC
        
    def test_default_context_is_generic(self):
        """Test that default context is generic."""
        prompts = GradingPrompts()
        
        # Should NOT contain product-specific references
        assert "Pyroscope" not in prompts.DEFAULT_CONTEXT
        
        # Should be a generic evaluation context
        assert "evaluating" in prompts.DEFAULT_CONTEXT.lower()
        
    def test_custom_rubric_used_when_provided(self):
        """Test that custom rubric is used when provided via config."""
        custom_rubric = """
# My Custom Rubric

## Criteria
1. Technical Accuracy: Does the pitch accurately describe the product?
2. Persuasiveness: Is the pitch compelling?
3. Objection Handling: Does it address common concerns?
"""
        config = ArenaConfig(
            anthropic_api_key="test-key",
            rubric_text=custom_rubric
        )
        
        # Mock the Anthropic client
        with patch('ai_sales_eval_arena.grading.anthropic.Anthropic'):
            grader = AIGrader(config)
            
            rubric = grader._get_rubric_text()
            assert rubric == custom_rubric
            assert "Technical Accuracy" in rubric
            assert "Persuasiveness" in rubric
            
    def test_custom_context_used_when_provided(self):
        """Test that custom evaluation context is used when provided."""
        custom_context = """
You are evaluating sales pitches for Cursor, an AI-powered code editor.
Key value propositions include model agnosticity, semantic indexing, and time to value.
"""
        config = ArenaConfig(
            anthropic_api_key="test-key",
            evaluation_context_text=custom_context
        )
        
        with patch('ai_sales_eval_arena.grading.anthropic.Anthropic'):
            grader = AIGrader(config)
            
            context = grader._get_context_text()
            assert context == custom_context
            assert "Cursor" in context
            
    def test_rubric_injected_into_comparative_prompt(self):
        """Test that custom rubric appears in the comparative prompt."""
        custom_rubric = "MY_UNIQUE_RUBRIC_TEXT_123"
        custom_context = "MY_UNIQUE_CONTEXT_TEXT_456"
        
        config = ArenaConfig(
            anthropic_api_key="test-key",
            rubric_text=custom_rubric,
            evaluation_context_text=custom_context
        )
        
        with patch('ai_sales_eval_arena.grading.anthropic.Anthropic'):
            grader = AIGrader(config)
            
            participant_a = Participant(name="Alice")
            participant_b = Participant(name="Bob")
            transcript_a = Transcript(
                participant_id=participant_a.id,
                content="Alice's pitch content " * 20,  # Enough words
                word_count=60
            )
            transcript_b = Transcript(
                participant_id=participant_b.id,
                content="Bob's pitch content " * 20,
                word_count=60
            )
            
            prompt = grader._build_comparative_prompt(
                transcript_a, participant_a,
                transcript_b, participant_b
            )
            
            assert custom_rubric in prompt
            assert custom_context in prompt
            
    def test_rubric_injected_into_individual_prompt(self):
        """Test that custom rubric appears in individual evaluation prompt."""
        custom_rubric = "INDIVIDUAL_RUBRIC_789"
        custom_context = "INDIVIDUAL_CONTEXT_012"
        
        config = ArenaConfig(
            anthropic_api_key="test-key",
            rubric_text=custom_rubric,
            evaluation_context_text=custom_context
        )
        
        with patch('ai_sales_eval_arena.grading.anthropic.Anthropic'):
            grader = AIGrader(config)
            
            participant = Participant(name="Test")
            transcript = Transcript(
                participant_id=participant.id,
                content="Test content " * 20,
                word_count=40
            )
            
            prompt = grader._build_individual_prompt(transcript)
            
            assert custom_rubric in prompt
            assert custom_context in prompt


class TestCustomPromptTemplates:
    """Tests for fully custom prompt templates."""
    
    def test_custom_individual_prompt_template(self):
        """Test using a completely custom individual prompt template."""
        custom_template = """
CUSTOM INDIVIDUAL TEMPLATE

Context: {context}
Rubric: {rubric}
Transcript: {transcript}

Please evaluate and return JSON.
"""
        config = ArenaConfig(
            anthropic_api_key="test-key",
            individual_prompt_template=custom_template,
            rubric_text="My rubric",
            evaluation_context_text="My context"
        )
        
        with patch('ai_sales_eval_arena.grading.anthropic.Anthropic'):
            grader = AIGrader(config)
            
            transcript = Transcript(
                participant_id=uuid4(),
                content="Test content " * 20,
                word_count=40
            )
            
            prompt = grader._build_individual_prompt(transcript)
            
            assert "CUSTOM INDIVIDUAL TEMPLATE" in prompt
            assert "My rubric" in prompt
            assert "My context" in prompt
            
    def test_custom_comparative_prompt_template(self):
        """Test using a completely custom comparative prompt template."""
        custom_template = """
CUSTOM COMPARATIVE TEMPLATE

Context: {context}
Rubric: {rubric}

Participant A ({participant_a_name}): {transcript_a}
Participant B ({participant_b_name}): {transcript_b}

Pick a winner and return JSON.
"""
        config = ArenaConfig(
            anthropic_api_key="test-key",
            comparative_prompt_template=custom_template,
            rubric_text="Compare rubric",
            evaluation_context_text="Compare context"
        )
        
        with patch('ai_sales_eval_arena.grading.anthropic.Anthropic'):
            grader = AIGrader(config)
            
            participant_a = Participant(name="Alice")
            participant_b = Participant(name="Bob")
            transcript_a = Transcript(
                participant_id=participant_a.id,
                content="Alice pitch " * 20,
                word_count=40
            )
            transcript_b = Transcript(
                participant_id=participant_b.id,
                content="Bob pitch " * 20,
                word_count=40
            )
            
            prompt = grader._build_comparative_prompt(
                transcript_a, participant_a,
                transcript_b, participant_b
            )
            
            assert "CUSTOM COMPARATIVE TEMPLATE" in prompt
            assert "Compare rubric" in prompt
            assert "Compare context" in prompt
            assert "Alice" in prompt
            assert "Bob" in prompt


class TestGenericLibraryUsage:
    """Tests demonstrating generic library usage patterns."""
    
    def test_arena_config_accepts_all_custom_fields(self):
        """Test that ArenaConfig accepts all customization fields."""
        config = ArenaConfig(
            anthropic_api_key="test-key",
            anthropic_model="claude-3-opus",
            rubric_text="Custom rubric",
            evaluation_context_text="Custom context",
            individual_prompt_template="Custom individual {rubric} {transcript} {context}",
            comparative_prompt_template="Custom comparative {rubric} {context} {participant_a_name} {participant_b_name} {transcript_a} {transcript_b}",
            max_concurrent_matches=10
        )
        
        assert config.rubric_text == "Custom rubric"
        assert config.evaluation_context_text == "Custom context"
        assert config.individual_prompt_template is not None
        assert config.comparative_prompt_template is not None
        
    def test_config_defaults_to_none_for_custom_fields(self):
        """Test that custom fields default to None."""
        config = ArenaConfig(anthropic_api_key="test-key")
        
        assert config.rubric_text is None
        assert config.evaluation_context_text is None
        assert config.individual_prompt_template is None
        assert config.comparative_prompt_template is None
        
    @pytest.mark.asyncio
    async def test_tournament_with_custom_rubric(self):
        """Test running a tournament with custom rubric via TournamentManager."""
        custom_rubric = """
# Cursor Pitch Evaluation

## Criteria
1. Model Agnosticity explanation
2. Codebase understanding claims
3. Value proposition clarity
"""
        config = ArenaConfig(
            anthropic_api_key="test-key",
            rubric_text=custom_rubric,
            evaluation_context_text="Evaluating Cursor vs Claude Code pitches"
        )
        
        # Create test participants and transcripts
        participant1 = Participant(name="Rep A")
        participant2 = Participant(name="Rep B")
        
        transcript1 = Transcript(
            participant_id=participant1.id,
            content="Rep A pitch about Cursor features and benefits " * 20,
            word_count=100
        )
        transcript2 = Transcript(
            participant_id=participant2.id,
            content="Rep B pitch about Cursor advantages " * 20,
            word_count=80
        )
        
        # Mock the API call
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"winner_name": "Rep A", "winner_reasoning": "Better explanation", "participant_a_strengths": ["Good"], "participant_a_weaknesses": ["None"], "participant_b_strengths": ["OK"], "participant_b_weaknesses": ["Less detail"], "key_differentiators": ["Clarity"], "improvement_suggestions": {"Rep A": "Keep it up", "Rep B": "More detail"}}')]
        
        with patch('ai_sales_eval_arena.grading.anthropic.Anthropic') as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            manager = TournamentManager(config)
            
            # Verify the grader uses our custom rubric
            assert manager.engine.grader._get_rubric_text() == custom_rubric
            assert "Model Agnosticity" in manager.engine.grader._get_rubric_text()


class TestNoHardcodedDefaults:
    """Tests to ensure there are no problematic hardcoded defaults."""
    
    def test_comparative_prompt_has_no_hardcoded_criteria_list(self):
        """Test that comparative prompt doesn't have hardcoded criteria names."""
        prompts = GradingPrompts()
        
        # These were the old hardcoded criteria - they should NOT appear
        old_criteria = [
            "ICP Alignment: Research quality",
            "PBO Messaging: Business outcome",
            "Profiling Explanation: Technical accuracy",
            "Observability Context: Integration",
            "Talk Track Alignment: Flow"
        ]
        
        for criterion in old_criteria:
            assert criterion not in prompts.COMPARATIVE_EVALUATION, \
                f"Found hardcoded criterion in comparative prompt: {criterion}"
                
    def test_prompts_use_placeholders(self):
        """Test that prompt templates use proper placeholders."""
        prompts = GradingPrompts()
        
        # Individual prompt should have these placeholders
        assert "{context}" in prompts.INDIVIDUAL_EVALUATION
        assert "{rubric}" in prompts.INDIVIDUAL_EVALUATION
        assert "{transcript}" in prompts.INDIVIDUAL_EVALUATION
        
        # Comparative prompt should have these placeholders
        assert "{context}" in prompts.COMPARATIVE_EVALUATION
        assert "{rubric}" in prompts.COMPARATIVE_EVALUATION
        assert "{participant_a_name}" in prompts.COMPARATIVE_EVALUATION
        assert "{participant_b_name}" in prompts.COMPARATIVE_EVALUATION
        assert "{transcript_a}" in prompts.COMPARATIVE_EVALUATION
        assert "{transcript_b}" in prompts.COMPARATIVE_EVALUATION
