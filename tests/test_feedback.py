"""Tests for the feedback module - wins/losses matchup summaries."""

import pytest
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from ai_sales_eval_arena.models import (
    Tournament, TournamentFormat, Participant, Match, Transcript,
    TournamentStandings, MatchStatus
)
from ai_sales_eval_arena.feedback import (
    get_participant_key,
    generate_matchup_summary_markdown,
    FeedbackWriter,
    write_tournament_feedback,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def participant_alice():
    """Create a sample participant named Alice."""
    return Participant(name="Alice Anderson")


@pytest.fixture
def participant_bob():
    """Create a sample participant named Bob."""
    return Participant(name="Bob Builder")


@pytest.fixture
def transcript_alice(participant_alice):
    """Create a transcript for Alice with filename metadata."""
    return Transcript(
        participant_id=participant_alice.id,
        content="This is Alice's pitch transcript with sufficient content for testing purposes. " * 10,
        metadata={"filename": "alice_anderson.txt", "source": "test"}
    )


@pytest.fixture
def transcript_bob(participant_bob):
    """Create a transcript for Bob with filename metadata."""
    return Transcript(
        participant_id=participant_bob.id,
        content="This is Bob's pitch transcript with sufficient content for testing purposes. " * 10,
        metadata={"filename": "bob_builder.txt", "source": "test"}
    )


@pytest.fixture
def sample_metadata():
    """Create sample comparison metadata."""
    return {
        "participant_a_strengths": ["Clear value proposition", "Strong objection handling"],
        "participant_a_weaknesses": ["Could improve pacing"],
        "participant_b_strengths": ["Good rapport building"],
        "participant_b_weaknesses": ["Missed key differentiators", "Weak close"],
        "key_differentiators": ["Better product knowledge", "More concrete examples"],
        "improvement_suggestions": {
            "Alice Anderson": "Keep using specific customer examples",
            "Bob Builder": "Focus on addressing competitive objections earlier"
        }
    }


@pytest.fixture
def sample_tournament(participant_alice, participant_bob, transcript_alice, transcript_bob):
    """Create a sample completed tournament for testing."""
    participants = [participant_alice, participant_bob]
    
    # Create a match where Alice beats Bob
    match = Match(
        tournament_id=uuid4(),
        participant1_id=participant_alice.id,
        participant2_id=participant_bob.id,
        transcript1_id=transcript_alice.id,
        transcript2_id=transcript_bob.id,
        winner_id=participant_alice.id,
        comparison_feedback="Alice demonstrated stronger product knowledge and handled objections more effectively.",
        comparison_metadata={
            "participant_a_strengths": ["Clear value proposition", "Strong objection handling"],
            "participant_a_weaknesses": ["Could improve pacing"],
            "participant_b_strengths": ["Good rapport building"],
            "participant_b_weaknesses": ["Missed key differentiators", "Weak close"],
            "key_differentiators": ["Better product knowledge", "More concrete examples"],
            "improvement_suggestions": {
                "Alice Anderson": "Keep using specific customer examples",
                "Bob Builder": "Focus on addressing competitive objections earlier"
            }
        },
        status=MatchStatus.COMPLETED,
        completed_at=datetime.utcnow()
    )
    
    # Create standings
    standings = [
        TournamentStandings(
            participant_id=participant_alice.id,
            wins=1, losses=0, total_matches=1, rank=1,
            win_percentage=100.0, average_score=0.0
        ),
        TournamentStandings(
            participant_id=participant_bob.id,
            wins=0, losses=1, total_matches=1, rank=2,
            win_percentage=0.0, average_score=0.0
        ),
    ]
    
    tournament = Tournament(
        name="Test Tournament",
        format=TournamentFormat.ROUND_ROBIN,
        participants=participants,
        matches=[match],
        standings=standings,
        winner_id=participant_alice.id
    )
    
    return tournament


# ============================================================================
# Tests for get_participant_key
# ============================================================================

class TestGetParticipantKey:
    """Tests for participant key extraction."""
    
    def test_key_from_filename_metadata(self, participant_alice, transcript_alice):
        """Test that key is extracted from transcript filename metadata."""
        key = get_participant_key(participant_alice, transcript_alice)
        assert key == "alice_anderson"
    
    def test_key_from_filename_with_extension(self, participant_bob):
        """Test key extraction strips the file extension."""
        transcript = Transcript(
            participant_id=participant_bob.id,
            content="Test content " * 20,
            metadata={"filename": "bob_builder.txt"}
        )
        key = get_participant_key(participant_bob, transcript)
        assert key == "bob_builder"
    
    def test_key_fallback_to_name(self, participant_alice):
        """Test fallback to participant name when no filename metadata."""
        transcript = Transcript(
            participant_id=participant_alice.id,
            content="Test content " * 20,
            metadata={}  # No filename
        )
        key = get_participant_key(participant_alice, transcript)
        assert key == "alice_anderson"
    
    def test_key_fallback_no_filename_in_metadata(self, participant_bob):
        """Test fallback when metadata has no filename key."""
        transcript = Transcript(
            participant_id=participant_bob.id,
            content="Test content " * 20,
            metadata={"other_key": "value"}  # No filename key
        )
        key = get_participant_key(participant_bob, transcript)
        assert key == "bob_builder"
    
    def test_key_handles_special_characters(self):
        """Test that special characters are handled in name fallback."""
        participant = Participant(name="O'Connor-Smith Jr.")
        transcript = Transcript(
            participant_id=participant.id,
            content="Test content " * 20,
            metadata={}
        )
        key = get_participant_key(participant, transcript)
        # Should convert to safe key
        assert "'" not in key
        assert "-" not in key or key.replace("_", "").isalnum()


# ============================================================================
# Tests for generate_matchup_summary_markdown
# ============================================================================

class TestGenerateMatchupSummaryMarkdown:
    """Tests for markdown generation."""
    
    def test_basic_markdown_structure(self, participant_alice, participant_bob):
        """Test that generated markdown has required sections."""
        markdown = generate_matchup_summary_markdown(
            winner=participant_alice,
            loser=participant_bob,
            winner_key="alice_anderson",
            loser_key="bob_builder",
            comparison_feedback="Alice won because of better objection handling.",
        )
        
        # Check required sections
        assert "# Matchup:" in markdown
        assert "Alice Anderson" in markdown
        assert "Bob Builder" in markdown
        assert "**Winner:**" in markdown
        assert "**Loser:**" in markdown
        assert "## Overall Summary" in markdown
        assert "## Coaching Notes" in markdown
    
    def test_markdown_contains_comparison_feedback(self, participant_alice, participant_bob):
        """Test that comparison feedback is included in markdown."""
        feedback = "Alice demonstrated superior product knowledge."
        markdown = generate_matchup_summary_markdown(
            winner=participant_alice,
            loser=participant_bob,
            winner_key="alice_anderson",
            loser_key="bob_builder",
            comparison_feedback=feedback,
        )
        
        assert feedback in markdown
    
    def test_markdown_with_metadata(self, participant_alice, participant_bob, sample_metadata):
        """Test that metadata is incorporated into markdown."""
        markdown = generate_matchup_summary_markdown(
            winner=participant_alice,
            loser=participant_bob,
            winner_key="alice_anderson",
            loser_key="bob_builder",
            comparison_feedback="Alice won.",
            metadata=sample_metadata,
            winner_was_participant_a=True,
        )
        
        # Check that key differentiators are included
        assert "Key Differentiators" in markdown or "Better product knowledge" in markdown
        
        # Check that improvement suggestions are included
        assert "Keep using specific customer examples" in markdown or "Coaching Notes" in markdown
    
    def test_markdown_footer_contains_keys(self, participant_alice, participant_bob):
        """Test that footer contains participant keys."""
        markdown = generate_matchup_summary_markdown(
            winner=participant_alice,
            loser=participant_bob,
            winner_key="alice_anderson",
            loser_key="bob_builder",
            comparison_feedback="Test",
        )
        
        assert "alice_anderson" in markdown
        assert "bob_builder" in markdown
    
    def test_markdown_handles_none_feedback(self, participant_alice, participant_bob):
        """Test graceful handling when comparison_feedback is None."""
        markdown = generate_matchup_summary_markdown(
            winner=participant_alice,
            loser=participant_bob,
            winner_key="alice_anderson",
            loser_key="bob_builder",
            comparison_feedback=None,
        )
        
        # Should have a default summary
        assert "outperformed" in markdown


# ============================================================================
# Tests for FeedbackWriter
# ============================================================================

class TestFeedbackWriter:
    """Tests for the FeedbackWriter class."""
    
    def test_creates_feedback_directory_structure(self, tmp_path, participant_alice, participant_bob, transcript_alice, transcript_bob):
        """Test that correct directory structure is created."""
        writer = FeedbackWriter(tmp_path)
        
        writer.write_matchup_feedback(
            winner=participant_alice,
            loser=participant_bob,
            winner_transcript=transcript_alice,
            loser_transcript=transcript_bob,
            comparison_feedback="Alice won.",
        )
        
        # Check directory structure
        feedback_dir = tmp_path / "feedback" / "salespeople"
        assert feedback_dir.exists()
        
        alice_dir = feedback_dir / "alice_anderson"
        bob_dir = feedback_dir / "bob_builder"
        
        assert alice_dir.exists()
        assert bob_dir.exists()
        assert (alice_dir / "wins").exists()
        assert (alice_dir / "losses").exists()
        assert (bob_dir / "wins").exists()
        assert (bob_dir / "losses").exists()
    
    def test_writes_to_correct_files(self, tmp_path, participant_alice, participant_bob, transcript_alice, transcript_bob):
        """Test that feedback is written to correct win/loss files."""
        writer = FeedbackWriter(tmp_path)
        
        winner_file, loser_file = writer.write_matchup_feedback(
            winner=participant_alice,
            loser=participant_bob,
            winner_transcript=transcript_alice,
            loser_transcript=transcript_bob,
            comparison_feedback="Alice won.",
        )
        
        # Winner's file should be in wins/ folder named after loser
        expected_winner_file = tmp_path / "feedback" / "salespeople" / "alice_anderson" / "wins" / "bob_builder.md"
        assert winner_file == expected_winner_file
        assert winner_file.exists()
        
        # Loser's file should be in losses/ folder named after winner
        expected_loser_file = tmp_path / "feedback" / "salespeople" / "bob_builder" / "losses" / "alice_anderson.md"
        assert loser_file == expected_loser_file
        assert loser_file.exists()
    
    def test_same_content_in_both_files(self, tmp_path, participant_alice, participant_bob, transcript_alice, transcript_bob):
        """Test that identical content is written to both files."""
        writer = FeedbackWriter(tmp_path)
        
        winner_file, loser_file = writer.write_matchup_feedback(
            winner=participant_alice,
            loser=participant_bob,
            winner_transcript=transcript_alice,
            loser_transcript=transcript_bob,
            comparison_feedback="Alice won because of superior demonstration.",
        )
        
        winner_content = winner_file.read_text()
        loser_content = loser_file.read_text()
        
        assert winner_content == loser_content
    
    def test_skips_duplicate_matchups(self, tmp_path, participant_alice, participant_bob, transcript_alice, transcript_bob):
        """Test that same matchup is not generated twice."""
        writer = FeedbackWriter(tmp_path)
        
        # First call should write files
        w1, l1 = writer.write_matchup_feedback(
            winner=participant_alice,
            loser=participant_bob,
            winner_transcript=transcript_alice,
            loser_transcript=transcript_bob,
            comparison_feedback="First matchup.",
        )
        
        assert w1 is not None
        assert l1 is not None
        
        # Second call with same participants should skip
        w2, l2 = writer.write_matchup_feedback(
            winner=participant_alice,
            loser=participant_bob,
            winner_transcript=transcript_alice,
            loser_transcript=transcript_bob,
            comparison_feedback="Duplicate matchup.",
        )
        
        assert w2 is None
        assert l2 is None
    
    def test_overwrite_false_skips_existing(self, tmp_path, participant_alice, participant_bob, transcript_alice, transcript_bob):
        """Test that overwrite=False skips existing files."""
        # First write with overwrite=True
        writer1 = FeedbackWriter(tmp_path, overwrite=True)
        w1, l1 = writer1.write_matchup_feedback(
            winner=participant_alice,
            loser=participant_bob,
            winner_transcript=transcript_alice,
            loser_transcript=transcript_bob,
            comparison_feedback="First content.",
        )
        
        first_content = w1.read_text()
        
        # Second write with overwrite=False (new writer instance)
        writer2 = FeedbackWriter(tmp_path, overwrite=False)
        w2, l2 = writer2.write_matchup_feedback(
            winner=participant_alice,
            loser=participant_bob,
            winner_transcript=transcript_alice,
            loser_transcript=transcript_bob,
            comparison_feedback="New content that should not be written.",
        )
        
        # Should return None (skipped)
        assert w2 is None
        assert l2 is None
        
        # Original content should be unchanged
        assert w1.read_text() == first_content


# ============================================================================
# Tests for write_tournament_feedback (integration)
# ============================================================================

class TestWriteTournamentFeedback:
    """Integration tests for tournament feedback writing."""
    
    def test_writes_feedback_for_all_matches(self, tmp_path, sample_tournament, transcript_alice, transcript_bob, participant_alice, participant_bob):
        """Test that feedback is written for all completed matches."""
        transcripts_by_participant = {
            participant_alice.id: transcript_alice,
            participant_bob.id: transcript_bob,
        }
        
        result = write_tournament_feedback(
            tournament=sample_tournament,
            transcripts_by_participant=transcripts_by_participant,
            output_dir=tmp_path,
        )
        
        # Should have written files
        assert len(result["wins"]) == 1
        assert len(result["losses"]) == 1
    
    def test_feedback_directory_structure(self, tmp_path, sample_tournament, transcript_alice, transcript_bob, participant_alice, participant_bob):
        """Test that correct directory structure is created."""
        transcripts_by_participant = {
            participant_alice.id: transcript_alice,
            participant_bob.id: transcript_bob,
        }
        
        write_tournament_feedback(
            tournament=sample_tournament,
            transcripts_by_participant=transcripts_by_participant,
            output_dir=tmp_path,
        )
        
        # Verify structure
        feedback_dir = tmp_path / "feedback" / "salespeople"
        assert feedback_dir.exists()
        
        # Alice won, so she should have a win file
        alice_win_file = feedback_dir / "alice_anderson" / "wins" / "bob_builder.md"
        assert alice_win_file.exists()
        
        # Bob lost, so he should have a loss file
        bob_loss_file = feedback_dir / "bob_builder" / "losses" / "alice_anderson.md"
        assert bob_loss_file.exists()
    
    def test_markdown_content_is_reasonable(self, tmp_path, sample_tournament, transcript_alice, transcript_bob, participant_alice, participant_bob):
        """Test that generated markdown has reasonable content."""
        transcripts_by_participant = {
            participant_alice.id: transcript_alice,
            participant_bob.id: transcript_bob,
        }
        
        write_tournament_feedback(
            tournament=sample_tournament,
            transcripts_by_participant=transcripts_by_participant,
            output_dir=tmp_path,
        )
        
        # Read generated file
        win_file = tmp_path / "feedback" / "salespeople" / "alice_anderson" / "wins" / "bob_builder.md"
        content = win_file.read_text()
        
        # Check for required elements
        assert "# Matchup:" in content
        assert "**Winner:**" in content
        assert "Alice Anderson" in content
        assert "Bob Builder" in content
        assert "## Coaching Notes" in content
        
        # Should contain the comparison feedback from the match
        assert "product knowledge" in content or "objection" in content
    
    def test_skips_incomplete_matches(self, tmp_path, participant_alice, participant_bob, transcript_alice, transcript_bob):
        """Test that incomplete matches are skipped."""
        # Create tournament with an incomplete match
        match = Match(
            tournament_id=uuid4(),
            participant1_id=participant_alice.id,
            participant2_id=participant_bob.id,
            transcript1_id=transcript_alice.id,
            transcript2_id=transcript_bob.id,
            winner_id=None,  # No winner yet
            status=MatchStatus.PENDING,  # Not completed
        )
        
        tournament = Tournament(
            name="Incomplete Tournament",
            format=TournamentFormat.ROUND_ROBIN,
            participants=[participant_alice, participant_bob],
            matches=[match],
            standings=[],
        )
        
        transcripts_by_participant = {
            participant_alice.id: transcript_alice,
            participant_bob.id: transcript_bob,
        }
        
        result = write_tournament_feedback(
            tournament=tournament,
            transcripts_by_participant=transcripts_by_participant,
            output_dir=tmp_path,
        )
        
        # Should have written no files
        assert len(result["wins"]) == 0
        assert len(result["losses"]) == 0


# ============================================================================
# Tests for multi-participant tournament
# ============================================================================

class TestMultiParticipantTournament:
    """Tests with 3+ participants to verify correct folder organization."""
    
    def test_three_participant_tournament(self, tmp_path):
        """Test feedback generation with 3 participants."""
        # Create 3 participants
        alice = Participant(name="Alice")
        bob = Participant(name="Bob")
        charlie = Participant(name="Charlie")
        
        # Create transcripts with filename metadata
        t_alice = Transcript(
            participant_id=alice.id,
            content="Alice's transcript content. " * 20,
            metadata={"filename": "alice.txt"}
        )
        t_bob = Transcript(
            participant_id=bob.id,
            content="Bob's transcript content. " * 20,
            metadata={"filename": "bob.txt"}
        )
        t_charlie = Transcript(
            participant_id=charlie.id,
            content="Charlie's transcript content. " * 20,
            metadata={"filename": "charlie.txt"}
        )
        
        # Create matches: Alice beats Bob, Alice beats Charlie, Charlie beats Bob
        matches = [
            Match(
                tournament_id=uuid4(),
                participant1_id=alice.id,
                participant2_id=bob.id,
                transcript1_id=t_alice.id,
                transcript2_id=t_bob.id,
                winner_id=alice.id,
                comparison_feedback="Alice beat Bob.",
                status=MatchStatus.COMPLETED,
                completed_at=datetime.utcnow()
            ),
            Match(
                tournament_id=uuid4(),
                participant1_id=alice.id,
                participant2_id=charlie.id,
                transcript1_id=t_alice.id,
                transcript2_id=t_charlie.id,
                winner_id=alice.id,
                comparison_feedback="Alice beat Charlie.",
                status=MatchStatus.COMPLETED,
                completed_at=datetime.utcnow()
            ),
            Match(
                tournament_id=uuid4(),
                participant1_id=bob.id,
                participant2_id=charlie.id,
                transcript1_id=t_bob.id,
                transcript2_id=t_charlie.id,
                winner_id=charlie.id,
                comparison_feedback="Charlie beat Bob.",
                status=MatchStatus.COMPLETED,
                completed_at=datetime.utcnow()
            ),
        ]
        
        tournament = Tournament(
            name="Three Person Tournament",
            format=TournamentFormat.ROUND_ROBIN,
            participants=[alice, bob, charlie],
            matches=matches,
            standings=[],
        )
        
        transcripts_by_participant = {
            alice.id: t_alice,
            bob.id: t_bob,
            charlie.id: t_charlie,
        }
        
        result = write_tournament_feedback(
            tournament=tournament,
            transcripts_by_participant=transcripts_by_participant,
            output_dir=tmp_path,
        )
        
        # Should have 3 wins and 3 losses (one per match)
        assert len(result["wins"]) == 3
        assert len(result["losses"]) == 3
        
        feedback_dir = tmp_path / "feedback" / "salespeople"
        
        # Alice: 2 wins, 0 losses
        assert (feedback_dir / "alice" / "wins" / "bob.md").exists()
        assert (feedback_dir / "alice" / "wins" / "charlie.md").exists()
        assert not list((feedback_dir / "alice" / "losses").glob("*.md"))
        
        # Bob: 0 wins, 2 losses
        assert not list((feedback_dir / "bob" / "wins").glob("*.md"))
        assert (feedback_dir / "bob" / "losses" / "alice.md").exists()
        assert (feedback_dir / "bob" / "losses" / "charlie.md").exists()
        
        # Charlie: 1 win, 1 loss
        assert (feedback_dir / "charlie" / "wins" / "bob.md").exists()
        assert (feedback_dir / "charlie" / "losses" / "alice.md").exists()
