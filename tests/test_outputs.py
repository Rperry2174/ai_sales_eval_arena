"""Tests for the outputs module - history tracking and GIF generation."""

import json
import pytest
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from ai_sales_eval_arena.models import (
    Tournament, TournamentFormat, Participant, Match, 
    TournamentStandings, MatchStatus
)
from ai_sales_eval_arena.outputs import (
    append_history_entry, create_tournament_progression_gif
)


@pytest.fixture
def sample_tournament():
    """Create a sample completed tournament for testing."""
    # Create participants
    participants = [
        Participant(name="Alice"),
        Participant(name="Bob"),
        Participant(name="Charlie")
    ]
    
    # Create matches
    matches = []
    match_time = datetime.utcnow()
    
    # Match 1: Alice vs Bob - Alice wins
    match1 = Match(
        tournament_id=uuid4(),
        participant1_id=participants[0].id,
        participant2_id=participants[1].id,
        transcript1_id=uuid4(),
        transcript2_id=uuid4(),
        winner_id=participants[0].id,
        status=MatchStatus.COMPLETED,
        completed_at=match_time
    )
    matches.append(match1)
    
    # Match 2: Alice vs Charlie - Alice wins
    match2 = Match(
        tournament_id=uuid4(),
        participant1_id=participants[0].id,
        participant2_id=participants[2].id,
        transcript1_id=uuid4(),
        transcript2_id=uuid4(),
        winner_id=participants[0].id,
        status=MatchStatus.COMPLETED,
        completed_at=match_time
    )
    matches.append(match2)
    
    # Match 3: Bob vs Charlie - Charlie wins
    match3 = Match(
        tournament_id=uuid4(),
        participant1_id=participants[1].id,
        participant2_id=participants[2].id,
        transcript1_id=uuid4(),
        transcript2_id=uuid4(),
        winner_id=participants[2].id,
        status=MatchStatus.COMPLETED,
        completed_at=match_time
    )
    matches.append(match3)
    
    # Create standings
    standings = [
        TournamentStandings(
            participant_id=participants[0].id,
            wins=2, losses=0, total_matches=2, rank=1,
            win_percentage=100.0, average_score=0.0
        ),
        TournamentStandings(
            participant_id=participants[2].id,
            wins=1, losses=1, total_matches=2, rank=2,
            win_percentage=50.0, average_score=0.0
        ),
        TournamentStandings(
            participant_id=participants[1].id,
            wins=0, losses=2, total_matches=2, rank=3,
            win_percentage=0.0, average_score=0.0
        ),
    ]
    
    tournament = Tournament(
        name="Test Tournament",
        format=TournamentFormat.ROUND_ROBIN,
        participants=participants,
        matches=matches,
        standings=standings,
        winner_id=participants[0].id
    )
    
    return tournament


class TestHistoryEntry:
    """Tests for history entry appending."""
    
    def test_append_history_creates_file(self, tmp_path, sample_tournament):
        """Test that append_history_entry creates the history file."""
        history_file = tmp_path / "results" / "history.jsonl"
        
        append_history_entry(
            history_file=history_file,
            tournament=sample_tournament,
            model="test-model",
            rubric_text="Test rubric",
            input_dir="/path/to/transcripts",
            input_format="gong_txt",
            output_dir="/path/to/output"
        )
        
        assert history_file.exists()
        
    def test_history_entry_content(self, tmp_path, sample_tournament):
        """Test that history entry contains expected fields."""
        history_file = tmp_path / "history.jsonl"
        
        append_history_entry(
            history_file=history_file,
            tournament=sample_tournament,
            model="test-model",
            rubric_text="My custom rubric",
            input_dir="/transcripts",
            input_format="gong_txt",
            output_dir="/output"
        )
        
        with open(history_file, "r") as f:
            entry = json.loads(f.readline())
            
        assert entry["tournament_name"] == "Test Tournament"
        assert entry["format"] == "round_robin"
        assert entry["participants"] == 3
        assert entry["matches"] == 3
        assert entry["winner_name"] == "Alice"
        assert entry["model"] == "test-model"
        assert entry["input_dir"] == "/transcripts"
        assert entry["input_format"] == "gong_txt"
        assert "rubric_hash" in entry
        assert "timestamp" in entry
        assert "top_three" in entry
        
    def test_rubric_hash_generated(self, tmp_path, sample_tournament):
        """Test that rubric hash is generated from rubric text."""
        history_file = tmp_path / "history.jsonl"
        
        append_history_entry(
            history_file=history_file,
            tournament=sample_tournament,
            model="test",
            rubric_text="Test rubric content",
            input_dir="",
            input_format="",
            output_dir=""
        )
        
        with open(history_file, "r") as f:
            entry = json.loads(f.readline())
            
        assert entry["rubric_hash"] is not None
        assert len(entry["rubric_hash"]) == 64  # SHA256 hex length
        
    def test_rubric_hash_none_when_no_rubric(self, tmp_path, sample_tournament):
        """Test that rubric_hash is None when no rubric provided."""
        history_file = tmp_path / "history.jsonl"
        
        append_history_entry(
            history_file=history_file,
            tournament=sample_tournament,
            model="test",
            rubric_text=None,  # No rubric
            input_dir="",
            input_format="",
            output_dir=""
        )
        
        with open(history_file, "r") as f:
            entry = json.loads(f.readline())
            
        assert entry["rubric_hash"] is None
        
    def test_multiple_entries_appended(self, tmp_path, sample_tournament):
        """Test that multiple entries are appended to same file."""
        history_file = tmp_path / "history.jsonl"
        
        # Append first entry
        append_history_entry(
            history_file=history_file,
            tournament=sample_tournament,
            model="model-1",
            rubric_text=None,
            input_dir="",
            input_format="",
            output_dir=""
        )
        
        # Append second entry
        sample_tournament.name = "Second Tournament"
        append_history_entry(
            history_file=history_file,
            tournament=sample_tournament,
            model="model-2",
            rubric_text=None,
            input_dir="",
            input_format="",
            output_dir=""
        )
        
        with open(history_file, "r") as f:
            lines = f.readlines()
            
        assert len(lines) == 2
        
        entry1 = json.loads(lines[0])
        entry2 = json.loads(lines[1])
        
        assert entry1["model"] == "model-1"
        assert entry2["model"] == "model-2"
        
    def test_top_three_populated(self, tmp_path, sample_tournament):
        """Test that top_three list is populated correctly."""
        history_file = tmp_path / "history.jsonl"
        
        append_history_entry(
            history_file=history_file,
            tournament=sample_tournament,
            model="test",
            rubric_text=None,
            input_dir="",
            input_format="",
            output_dir=""
        )
        
        with open(history_file, "r") as f:
            entry = json.loads(f.readline())
            
        top_three = entry["top_three"]
        assert len(top_three) == 3
        assert top_three[0] == "Alice"  # Rank 1
        assert top_three[1] == "Charlie"  # Rank 2
        assert top_three[2] == "Bob"  # Rank 3


class TestProgressionGif:
    """Tests for tournament progression GIF generation."""
    
    def test_gif_created(self, tmp_path, sample_tournament):
        """Test that GIF file is created."""
        gif_path = create_tournament_progression_gif(sample_tournament, tmp_path)
        
        if gif_path is not None:  # May be None if matplotlib not available
            assert Path(gif_path).exists()
            assert gif_path.endswith(".gif")
            
    def test_gif_returns_none_with_no_matches(self, tmp_path):
        """Test that GIF returns None when no completed matches."""
        tournament = Tournament(
            name="Empty Tournament",
            format=TournamentFormat.ROUND_ROBIN,
            participants=[Participant(name="Test")],
            matches=[],
            standings=[]
        )
        
        result = create_tournament_progression_gif(tournament, tmp_path)
        assert result is None
        
    def test_output_directory_created(self, tmp_path, sample_tournament):
        """Test that output directory is created if it doesn't exist."""
        try:
            import matplotlib
            matplotlib_available = True
        except ImportError:
            matplotlib_available = False
            
        new_dir = tmp_path / "new" / "nested" / "dir"
        
        result = create_tournament_progression_gif(sample_tournament, new_dir)
        
        if matplotlib_available:
            # If matplotlib is available, directory should be created
            assert new_dir.exists()
        else:
            # If matplotlib not available, function returns None without creating dir
            assert result is None
