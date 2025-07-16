"""Unit tests for transcript loader."""

import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
from ai_sales_eval_arena.transcript_loader import (
    TranscriptLoader, load_sample_data, create_sample_data
)
from ai_sales_eval_arena.models import Participant, Transcript


class TestTranscriptLoader:
    """Test cases for TranscriptLoader."""
    
    def test_loader_initialization_default(self):
        """Test loader initialization with default path."""
        with patch('pathlib.Path.exists', return_value=True):
            loader = TranscriptLoader()
            assert loader.transcripts_dir == Path("data/transcripts")
    
    def test_loader_initialization_custom_path(self):
        """Test loader initialization with custom path."""
        custom_path = Path("/custom/path")
        with patch('pathlib.Path.exists', return_value=True):
            loader = TranscriptLoader(custom_path)
            assert loader.transcripts_dir == custom_path
    
    def test_loader_initialization_nonexistent_path(self):
        """Test loader initialization with nonexistent path."""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError):
                TranscriptLoader(Path("/nonexistent"))
    
    def test_infer_skill_level_excellent(self):
        """Test skill level inference for excellent names."""
        with patch('pathlib.Path.exists', return_value=True):
            loader = TranscriptLoader()
            
            assert loader._infer_skill_level("maxwell_profiler", "") == "expert"
            assert loader._infer_skill_level("maya_magnificent", "") == "expert"
            assert loader._infer_skill_level("stella_stacktrace", "") == "expert"
    
    def test_infer_skill_level_very_good(self):
        """Test skill level inference for very good names."""
        with patch('pathlib.Path.exists', return_value=True):
            loader = TranscriptLoader()
            
            assert loader._infer_skill_level("betty_benchmark", "") == "expert"
            assert loader._infer_skill_level("felicia_fantastic", "") == "expert"
            assert loader._infer_skill_level("eddie_exception", "") == "expert"
    
    def test_infer_skill_level_poor(self):
        """Test skill level inference for poor names."""
        with patch('pathlib.Path.exists', return_value=True):
            loader = TranscriptLoader()
            
            assert loader._infer_skill_level("gary_garbage", "") == "beginner"
            assert loader._infer_skill_level("derek_disaster", "") == "beginner"
            assert loader._infer_skill_level("nancy_nonsense", "") == "beginner"
    
    def test_infer_skill_level_intermediate(self):
        """Test skill level inference for intermediate names."""
        with patch('pathlib.Path.exists', return_value=True):
            loader = TranscriptLoader()
            
            assert loader._infer_skill_level("unknown_person", "") == "intermediate"
            assert loader._infer_skill_level("test_user", "") == "intermediate"
    
    @patch('pathlib.Path.glob')
    @patch('pathlib.Path.exists', return_value=True)
    def test_get_available_transcripts(self, mock_exists, mock_glob):
        """Test getting available transcript filenames."""
        # Mock Path objects
        mock_files = [
            Path("maya_magnificent.txt"),
            Path("gary_garbage.txt"),
            Path("betty_benchmark.txt")
        ]
        mock_glob.return_value = mock_files
        
        loader = TranscriptLoader()
        available = loader.get_available_transcripts()
        
        assert len(available) == 3
        assert "maya_magnificent.txt" in available
        assert "gary_garbage.txt" in available
        assert "betty_benchmark.txt" in available
    
    @patch('pathlib.Path.glob')
    @patch('pathlib.Path.exists', return_value=True)
    def test_get_transcripts_by_quality(self, mock_exists, mock_glob):
        """Test grouping transcripts by quality level."""
        # Mock Path objects with stems
        mock_files = []
        file_data = [
            ("maya_magnificent.txt", "maya_magnificent"),
            ("gary_garbage.txt", "gary_garbage"),
            ("betty_benchmark.txt", "betty_benchmark"),
            ("unknown_person.txt", "unknown_person")
        ]
        
        for filename, stem in file_data:
            mock_file = Path(filename)
            mock_file.stem = stem
            mock_files.append(mock_file)
        
        mock_glob.return_value = mock_files
        
        loader = TranscriptLoader()
        quality_groups = loader.get_transcripts_by_quality()
        
        assert "maya_magnificent.txt" in quality_groups["expert"]
        assert "betty_benchmark.txt" in quality_groups["expert"]
        assert "gary_garbage.txt" in quality_groups["beginner"]
        assert "unknown_person.txt" in quality_groups["intermediate"]
    
    @patch('builtins.open', new_callable=mock_open, read_data="This is a test sales pitch content.")
    @patch('pathlib.Path.exists', return_value=True)
    def test_load_transcript_file(self, mock_exists, mock_file):
        """Test loading a single transcript file."""
        loader = TranscriptLoader()
        file_path = Path("maya_magnificent.txt")
        file_path.stem = "maya_magnificent"
        
        participant, transcript = loader._load_transcript_file(file_path)
        
        assert isinstance(participant, Participant)
        assert participant.name == "Maya Magnificent"
        assert participant.email == "maya_magnificent@salesteam.com"
        assert participant.department == "Sales"
        
        assert isinstance(transcript, Transcript)
        assert transcript.content == "This is a test sales pitch content."
        assert transcript.word_count == 7
        assert transcript.metadata["filename"] == "maya_magnificent.txt"
        assert transcript.metadata["skill_level"] == "expert"
        assert transcript.metadata["source"] == "real_transcript"
    
    @patch('builtins.open', side_effect=FileNotFoundError("File not found"))
    @patch('pathlib.Path.exists', return_value=True)
    def test_load_transcript_file_read_error(self, mock_exists, mock_file):
        """Test handling of file read errors."""
        loader = TranscriptLoader()
        file_path = Path("nonexistent.txt")
        
        with pytest.raises(ValueError, match="Failed to read file"):
            loader._load_transcript_file(file_path)
    
    @patch('builtins.open', new_callable=mock_open, read_data="")
    @patch('pathlib.Path.exists', return_value=True)
    def test_load_transcript_file_empty_content(self, mock_exists, mock_file):
        """Test handling of empty transcript files."""
        loader = TranscriptLoader()
        file_path = Path("empty.txt")
        
        with pytest.raises(ValueError, match="Empty transcript file"):
            loader._load_transcript_file(file_path)
    
    @patch('ai_sales_eval_arena.transcript_loader.TranscriptLoader.load_all_transcripts')
    @patch('pathlib.Path.exists', return_value=True)
    def test_load_sample_data_default(self, mock_exists, mock_load_all):
        """Test loading sample data with default parameters."""
        # Mock return data
        mock_participants = [Participant(name=f"Test {i}") for i in range(10)]
        mock_transcripts = [
            Transcript(
                participant_id=p.id,
                content="Test content",
                word_count=2
            ) for p in mock_participants
        ]
        mock_load_all.return_value = (mock_participants, mock_transcripts)
        
        participants, transcripts = load_sample_data(num_participants=5)
        
        assert len(participants) == 5
        assert len(transcripts) == 5
    
    @patch('ai_sales_eval_arena.transcript_loader.TranscriptLoader.get_transcripts_by_quality')
    @patch('ai_sales_eval_arena.transcript_loader.TranscriptLoader.load_specific_transcripts')
    @patch('pathlib.Path.exists', return_value=True)
    def test_load_sample_data_with_distribution(self, mock_exists, mock_load_specific, mock_get_quality):
        """Test loading sample data with quality distribution."""
        # Mock quality groups
        mock_get_quality.return_value = {
            "expert": ["maya_magnificent.txt", "betty_benchmark.txt"],
            "intermediate": ["test_user.txt"],
            "beginner": ["gary_garbage.txt", "derek_disaster.txt"]
        }
        
        # Mock return data
        mock_participants = [Participant(name=f"Test {i}") for i in range(4)]
        mock_transcripts = [
            Transcript(
                participant_id=p.id,
                content="Test content",
                word_count=2
            ) for p in mock_participants
        ]
        mock_load_specific.return_value = (mock_participants, mock_transcripts)
        
        distribution = {"expert": 0.5, "intermediate": 0.25, "beginner": 0.25}
        participants, transcripts = load_sample_data(
            num_participants=4,
            quality_distribution=distribution
        )
        
        assert len(participants) == 4
        assert len(transcripts) == 4
    
    def test_create_sample_data_backward_compatibility(self):
        """Test backward compatibility function."""
        with patch('ai_sales_eval_arena.transcript_loader.load_sample_data') as mock_load:
            mock_load.return_value = ([], [])
            
            create_sample_data(num_participants=6, seed=42)
            
            # Should call load_sample_data with num_participants, ignoring seed
            mock_load.assert_called_once_with(6)


class TestIntegration:
    """Integration tests for transcript loader."""
    
    @patch('pathlib.Path.glob')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists', return_value=True)
    def test_load_multiple_transcripts(self, mock_exists, mock_file, mock_glob):
        """Test loading multiple transcript files."""
        # Mock file data
        file_contents = {
            "maya_magnificent.txt": "Excellent sales pitch with detailed analysis.",
            "gary_garbage.txt": "Poor sales pitch with minimal effort.",
            "test_user.txt": "Average sales pitch with some good points."
        }
        
        def mock_open_side_effect(file_path, *args, **kwargs):
            filename = file_path.name if hasattr(file_path, 'name') else str(file_path).split('/')[-1]
            content = file_contents.get(filename, "Default content")
            return mock_open(read_data=content).return_value
        
        mock_file.side_effect = mock_open_side_effect
        
        # Mock Path objects
        mock_files = []
        for filename in file_contents.keys():
            mock_path = Path(filename)
            mock_path.stem = filename.replace('.txt', '')
            mock_files.append(mock_path)
        
        mock_glob.return_value = mock_files
        
        loader = TranscriptLoader()
        participants, transcripts = loader.load_all_transcripts()
        
        assert len(participants) == 3
        assert len(transcripts) == 3
        
        # Check names are properly formatted
        names = [p.name for p in participants]
        assert "Maya Magnificent" in names
        assert "Gary Garbage" in names
        assert "Test User" in names
        
        # Check skill levels are properly inferred
        skill_levels = [t.metadata["skill_level"] for t in transcripts]
        assert "expert" in skill_levels
        assert "beginner" in skill_levels
        assert "intermediate" in skill_levels


@pytest.fixture
def sample_transcript_content():
    """Fixture for sample transcript content."""
    return """
    Thank you for taking the time to meet with me today. I wanted to discuss how Pyroscope 
    can help optimize your application performance. Based on my research of your company, 
    I understand you're dealing with significant latency issues that are impacting user 
    experience and costing you customers.
    
    Pyroscope provides continuous profiling that gives you code-level visibility into 
    performance bottlenecks. Unlike traditional monitoring tools that only tell you 
    something is slow, Pyroscope shows you exactly which functions and lines of code 
    are causing the problems.
    
    For a company like yours, this typically translates to 30-50% reduction in incident 
    resolution time and significant cost savings through optimized infrastructure usage.
    
    I'd love to set up a proof of concept to show you the immediate impact on your 
    specific use case. What would be the best time for a technical deep dive?
    """.strip()


def test_real_transcript_loading_example(sample_transcript_content):
    """Test loading with realistic transcript content."""
    with patch('pathlib.Path.exists', return_value=True):
        with patch('builtins.open', mock_open(read_data=sample_transcript_content)):
            loader = TranscriptLoader()
            file_path = Path("professional_pitch.txt")
            file_path.stem = "professional_pitch"
            
            participant, transcript = loader._load_transcript_file(file_path)
            
            assert participant.name == "Professional Pitch"
            assert len(transcript.content) > 100
            assert transcript.word_count > 20
            assert transcript.duration_minutes > 0
            assert transcript.metadata["skill_level"] == "intermediate" 