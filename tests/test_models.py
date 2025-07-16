"""Unit tests for data models."""

import pytest
from datetime import datetime
from uuid import UUID, uuid4

from ai_sales_eval_arena.models import (
    Participant, Transcript, Grade, CriterionGrade, Match, 
    Tournament, TournamentStandings, TournamentFormat, 
    MatchStatus, GradingCriterion, VisualizationConfig, ArenaConfig
)


class TestParticipant:
    """Test cases for Participant model."""
    
    def test_participant_creation(self):
        """Test basic participant creation."""
        participant = Participant(
            name="John Doe",
            email="john@example.com",
            department="Sales",
            experience_years=5
        )
        
        assert participant.name == "John Doe"
        assert participant.email == "john@example.com"
        assert participant.department == "Sales"
        assert participant.experience_years == 5
        assert isinstance(participant.id, UUID)
        assert isinstance(participant.created_at, datetime)
    
    def test_participant_minimal(self):
        """Test participant with minimal required fields."""
        participant = Participant(name="Jane Smith")
        
        assert participant.name == "Jane Smith"
        assert participant.email is None
        assert participant.department is None
        assert participant.experience_years is None
    
    def test_participant_validation(self):
        """Test participant field validation."""
        # Test invalid email
        with pytest.raises(ValueError):
            Participant(name="Test", email="invalid-email")
        
        # Test negative experience
        with pytest.raises(ValueError):
            Participant(name="Test", experience_years=-1)
        
        # Test excessive experience
        with pytest.raises(ValueError):
            Participant(name="Test", experience_years=100)
    
    def test_participant_serialization(self):
        """Test participant JSON serialization."""
        participant = Participant(name="Test User")
        data = participant.dict()
        
        assert "id" in data
        assert "created_at" in data
        assert data["name"] == "Test User"


class TestTranscript:
    """Test cases for Transcript model."""
    
    def test_transcript_creation(self):
        """Test basic transcript creation."""
        participant_id = uuid4()
        content = "This is a test sales pitch with more than fifty characters to meet the minimum requirement."
        
        transcript = Transcript(
            participant_id=participant_id,
            content=content,
            duration_minutes=15.5
        )
        
        assert transcript.participant_id == participant_id
        assert transcript.content == content
        assert transcript.duration_minutes == 15.5
        assert transcript.word_count > 0
        assert isinstance(transcript.id, UUID)
    
    def test_word_count_calculation(self):
        """Test automatic word count calculation."""
        content = "This is a test content with exactly ten words here."
        transcript = Transcript(
            participant_id=uuid4(),
            content=content
        )
        
        assert transcript.word_count == 10
    
    def test_transcript_validation(self):
        """Test transcript validation."""
        # Test content too short
        with pytest.raises(ValueError):
            Transcript(
                participant_id=uuid4(),
                content="Short"
            )
        
        # Test negative duration
        with pytest.raises(ValueError):
            Transcript(
                participant_id=uuid4(),
                content="This is a valid content with enough characters for the test.",
                duration_minutes=-1
            )


class TestCriterionGrade:
    """Test cases for CriterionGrade model."""
    
    def test_criterion_grade_creation(self):
        """Test criterion grade creation."""
        grade = CriterionGrade(
            criterion=GradingCriterion.ICP_ALIGNMENT,
            score=3.5,
            explanation="Good alignment with target customer profile.",
            feedback="Consider adding more specific industry examples."
        )
        
        assert grade.criterion == GradingCriterion.ICP_ALIGNMENT
        assert grade.score == 3.5
        assert "alignment" in grade.explanation
        assert "Consider" in grade.feedback
    
    def test_score_validation(self):
        """Test score range validation."""
        # Test score too low
        with pytest.raises(ValueError):
            CriterionGrade(
                criterion=GradingCriterion.ICP_ALIGNMENT,
                score=0.5,
                explanation="Test"
            )
        
        # Test score too high
        with pytest.raises(ValueError):
            CriterionGrade(
                criterion=GradingCriterion.ICP_ALIGNMENT,
                score=4.5,
                explanation="Test"
            )


class TestGrade:
    """Test cases for Grade model."""
    
    def test_grade_creation(self):
        """Test grade creation."""
        criterion_grades = [
            CriterionGrade(
                criterion=GradingCriterion.ICP_ALIGNMENT,
                score=3.0,
                explanation="Good ICP alignment"
            ),
            CriterionGrade(
                criterion=GradingCriterion.PBO_MESSAGING,
                score=4.0,
                explanation="Excellent messaging"
            )
        ]
        
        grade = Grade(
            transcript_id=uuid4(),
            participant_id=uuid4(),
            criterion_grades=criterion_grades,
            overall_score=3.5,
            overall_feedback="Strong performance overall"
        )
        
        assert len(grade.criterion_grades) == 2
        assert grade.overall_score == 3.5
        assert isinstance(grade.id, UUID)
    
    def test_overall_score_calculation(self):
        """Test automatic overall score calculation."""
        criterion_grades = [
            CriterionGrade(
                criterion=GradingCriterion.ICP_ALIGNMENT,
                score=2.0,
                explanation="Test"
            ),
            CriterionGrade(
                criterion=GradingCriterion.PBO_MESSAGING,
                score=4.0,
                explanation="Test"
            )
        ]
        
        grade = Grade(
            transcript_id=uuid4(),
            participant_id=uuid4(),
            criterion_grades=criterion_grades,
            overall_feedback="Test feedback"
        )
        
        # Should calculate as (2.0 + 4.0) / 2 = 3.0
        assert grade.overall_score == 3.0


class TestMatch:
    """Test cases for Match model."""
    
    def test_match_creation(self):
        """Test match creation."""
        match = Match(
            tournament_id=uuid4(),
            participant1_id=uuid4(),
            participant2_id=uuid4(),
            transcript1_id=uuid4(),
            transcript2_id=uuid4()
        )
        
        assert match.status == MatchStatus.PENDING
        assert match.winner_id is None
        assert isinstance(match.id, UUID)
        assert isinstance(match.created_at, datetime)
    
    def test_winner_validation(self):
        """Test winner validation."""
        p1_id = uuid4()
        p2_id = uuid4()
        
        match = Match(
            tournament_id=uuid4(),
            participant1_id=p1_id,
            participant2_id=p2_id,
            transcript1_id=uuid4(),
            transcript2_id=uuid4(),
            winner_id=p1_id
        )
        
        assert match.winner_id == p1_id
        
        # Test invalid winner
        with pytest.raises(ValueError):
            Match(
                tournament_id=uuid4(),
                participant1_id=p1_id,
                participant2_id=p2_id,
                transcript1_id=uuid4(),
                transcript2_id=uuid4(),
                winner_id=uuid4()  # Not one of the participants
            )


class TestTournamentStandings:
    """Test cases for TournamentStandings model."""
    
    def test_standings_creation(self):
        """Test standings creation."""
        standings = TournamentStandings(
            participant_id=uuid4(),
            wins=5,
            losses=2,
            total_matches=7
        )
        
        assert standings.wins == 5
        assert standings.losses == 2
        assert standings.total_matches == 7
        assert standings.win_percentage == (5/7) * 100
    
    def test_win_percentage_calculation(self):
        """Test win percentage calculation."""
        standings = TournamentStandings(
            participant_id=uuid4(),
            wins=3,
            total_matches=10
        )
        
        assert standings.win_percentage == 30.0


class TestTournament:
    """Test cases for Tournament model."""
    
    def test_tournament_creation(self):
        """Test tournament creation."""
        participants = [
            Participant(name="Player 1"),
            Participant(name="Player 2")
        ]
        
        tournament = Tournament(
            name="Test Tournament",
            description="A test tournament",
            format=TournamentFormat.ROUND_ROBIN,
            participants=participants
        )
        
        assert tournament.name == "Test Tournament"
        assert tournament.format == TournamentFormat.ROUND_ROBIN
        assert len(tournament.participants) == 2
        assert len(tournament.matches) == 0
        assert isinstance(tournament.id, UUID)
    
    def test_tournament_properties(self):
        """Test tournament computed properties."""
        tournament = Tournament(name="Test")
        
        # Test empty tournament
        assert tournament.is_completed is True  # No matches
        assert tournament.completion_percentage == 0.0
        
        # Add some matches
        matches = [
            Match(
                tournament_id=tournament.id,
                participant1_id=uuid4(),
                participant2_id=uuid4(),
                transcript1_id=uuid4(),
                transcript2_id=uuid4(),
                status=MatchStatus.COMPLETED
            ),
            Match(
                tournament_id=tournament.id,
                participant1_id=uuid4(),
                participant2_id=uuid4(),
                transcript1_id=uuid4(),
                transcript2_id=uuid4(),
                status=MatchStatus.PENDING
            )
        ]
        tournament.matches = matches
        
        assert tournament.is_completed is False
        assert tournament.completion_percentage == 50.0


class TestVisualizationConfig:
    """Test cases for VisualizationConfig model."""
    
    def test_config_defaults(self):
        """Test default configuration values."""
        config = VisualizationConfig()
        
        assert config.title == "AI Sales Evaluation Arena"
        assert config.theme == "plotly_white"
        assert config.width == 1200
        assert config.height == 800
        assert len(config.color_scheme) > 0
        assert "html" in config.export_formats
    
    def test_config_customization(self):
        """Test configuration customization."""
        config = VisualizationConfig(
            title="Custom Tournament",
            width=1600,
            height=900,
            export_formats=["png", "pdf"]
        )
        
        assert config.title == "Custom Tournament"
        assert config.width == 1600
        assert config.height == 900
        assert config.export_formats == ["png", "pdf"]


class TestArenaConfig:
    """Test cases for ArenaConfig model."""
    
    def test_arena_config_defaults(self):
        """Test default arena configuration."""
        config = ArenaConfig()
        
        assert config.openai_model == "gpt-4o-mini"
        assert config.max_concurrent_matches == 5
        assert config.grading_timeout_seconds == 60
        assert config.data_directory == "data"
        assert config.enable_real_time_updates is True
    
    def test_arena_config_validation(self):
        """Test arena configuration validation."""
        # Test invalid max concurrent matches
        with pytest.raises(ValueError):
            ArenaConfig(max_concurrent_matches=0)
        
        with pytest.raises(ValueError):
            ArenaConfig(max_concurrent_matches=25)
        
        # Test invalid timeout
        with pytest.raises(ValueError):
            ArenaConfig(grading_timeout_seconds=0)


class TestEnums:
    """Test cases for enum values."""
    
    def test_tournament_format_enum(self):
        """Test TournamentFormat enum."""
        assert TournamentFormat.ROUND_ROBIN == "round_robin"
        assert TournamentFormat.SINGLE_ELIMINATION == "single_elimination"
        assert TournamentFormat.DOUBLE_ELIMINATION == "double_elimination"
    
    def test_match_status_enum(self):
        """Test MatchStatus enum."""
        assert MatchStatus.PENDING == "pending"
        assert MatchStatus.IN_PROGRESS == "in_progress"
        assert MatchStatus.COMPLETED == "completed"
        assert MatchStatus.FAILED == "failed"
    
    def test_grading_criterion_enum(self):
        """Test GradingCriterion enum."""
        assert GradingCriterion.ICP_ALIGNMENT == "icp_alignment"
        assert GradingCriterion.PBO_MESSAGING == "pbo_messaging"
        assert GradingCriterion.PROFILING_EXPLANATION == "profiling_explanation"
        assert GradingCriterion.OBSERVABILITY_CONTEXT == "observability_context"
        assert GradingCriterion.TALK_TRACK_ALIGNMENT == "talk_track_alignment"


@pytest.fixture
def sample_participant():
    """Fixture for creating a sample participant."""
    return Participant(
        name="Test Participant",
        email="test@example.com",
        department="Sales",
        experience_years=3
    )


@pytest.fixture
def sample_transcript(sample_participant):
    """Fixture for creating a sample transcript."""
    return Transcript(
        participant_id=sample_participant.id,
        content="This is a comprehensive sales pitch transcript that meets all the minimum requirements for content length and demonstrates various sales techniques and approaches.",
        duration_minutes=20.0
    )


@pytest.fixture
def sample_grade(sample_participant, sample_transcript):
    """Fixture for creating a sample grade."""
    criterion_grades = [
        CriterionGrade(
            criterion=GradingCriterion.ICP_ALIGNMENT,
            score=3.0,
            explanation="Good ICP alignment with specific examples"
        ),
        CriterionGrade(
            criterion=GradingCriterion.PBO_MESSAGING,
            score=3.5,
            explanation="Strong business outcome messaging"
        )
    ]
    
    return Grade(
        transcript_id=sample_transcript.id,
        participant_id=sample_participant.id,
        criterion_grades=criterion_grades,
        overall_feedback="Good overall performance with room for improvement"
    ) 