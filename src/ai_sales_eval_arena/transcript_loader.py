"""Load real transcript files and convert them to Participant and Transcript objects."""

import logging
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from uuid import uuid4

from .models import Participant, Transcript

logger = logging.getLogger(__name__)


class TranscriptLoader:
    """Loads transcript files and creates Participant and Transcript objects."""
    
    def __init__(self, transcripts_dir: Path = None):
        """Initialize the transcript loader."""
        if transcripts_dir is None:
            # Default to data/transcripts relative to the current working directory
            transcripts_dir = Path("data/transcripts")
        
        self.transcripts_dir = Path(transcripts_dir)
        
        if not self.transcripts_dir.exists():
            raise FileNotFoundError(f"Transcripts directory not found: {self.transcripts_dir}")
    
    def load_all_transcripts(self) -> Tuple[List[Participant], List[Transcript]]:
        """Load all transcript files and return participants and transcripts."""
        participants = []
        transcripts = []
        
        # Get all .txt files in the transcripts directory
        transcript_files = list(self.transcripts_dir.glob("*.txt"))
        
        if not transcript_files:
            raise ValueError(f"No transcript files found in {self.transcripts_dir}")
        
        logger.info(f"Found {len(transcript_files)} transcript files")
        
        for file_path in sorted(transcript_files):
            try:
                participant, transcript = self._load_transcript_file(file_path)
                participants.append(participant)
                transcripts.append(transcript)
            except Exception as e:
                logger.error(f"Failed to load transcript {file_path}: {e}")
                continue
        
        logger.info(f"Successfully loaded {len(participants)} participants and transcripts")
        return participants, transcripts
    
    def _load_transcript_file(self, file_path: Path) -> Tuple[Participant, Transcript]:
        """Load a single transcript file and create Participant and Transcript objects."""
        
        # Extract participant name from filename (e.g., "maya_magnificent.txt" -> "Maya Magnificent")
        name_parts = file_path.stem.split('_')
        participant_name = ' '.join(word.capitalize() for word in name_parts)
        
        # Read the transcript content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
        except Exception as e:
            raise ValueError(f"Failed to read file {file_path}: {e}")
        
        if not content:
            raise ValueError(f"Empty transcript file: {file_path}")
        
        # Create participant
        participant = Participant(
            name=participant_name,
            email=f"{file_path.stem}@salesteam.com",
            department="Sales"
        )
        
        # Estimate duration based on content length (rough approximation)
        word_count = len(content.split())
        estimated_duration = word_count / 150  # Assume ~150 words per minute speaking rate
        
        # Infer skill level from quality indicators in the name or content
        skill_level = self._infer_skill_level(file_path.stem, content)
        
        # Create transcript
        transcript = Transcript(
            participant_id=participant.id,
            content=content,
            duration_minutes=estimated_duration,
            word_count=word_count,
            metadata={
                "filename": file_path.name,
                "skill_level": skill_level,
                "source": "real_transcript"
            }
        )
        
        return participant, transcript
    
    def _infer_skill_level(self, filename: str, content: str) -> str:
        """Infer skill level based on filename and content quality indicators."""
        
        # High-quality indicators in filenames
        excellent_names = {
            "maxwell_profiler", "stella_stacktrace", "victor_variables", "diana_debugger",
            "carlos_codecrusher", "miranda_metrics", "samantha_speedster", "felix_functions",
            "vicky_velocity", "maya_magnificent"
        }
        
        very_good_names = {
            "betty_benchmark", "frank_flamegraph", "wendy_widgets", "ollie_optimize",
            "larry_latency", "alex_algorithms", "monica_memory", "eddie_exception",
            "felicia_fantastic"
        }
        
        poor_names = {
            "garfield_graphs", "benny_bottleneck", "zara_zippy", "nancy_nonsense",
            "derek_disaster", "pablo_pathetic", "wanda_wobbly", "chester_chaotic",
            "oscar_overloaded", "neo_newbie", "harold_haphazard", "gary_garbage"
        }
        
        if filename in excellent_names:
            return "expert"
        elif filename in very_good_names:
            return "expert"  # Treat very good as expert for tournament purposes
        elif filename in poor_names:
            return "beginner"
        else:
            return "intermediate"
    
    def load_specific_transcripts(self, filenames: List[str]) -> Tuple[List[Participant], List[Transcript]]:
        """Load specific transcript files by filename."""
        participants = []
        transcripts = []
        
        for filename in filenames:
            file_path = self.transcripts_dir / filename
            if not file_path.exists():
                logger.warning(f"Transcript file not found: {file_path}")
                continue
            
            try:
                participant, transcript = self._load_transcript_file(file_path)
                participants.append(participant)
                transcripts.append(transcript)
            except Exception as e:
                logger.error(f"Failed to load transcript {filename}: {e}")
                continue
        
        return participants, transcripts
    
    def get_available_transcripts(self) -> List[str]:
        """Get a list of available transcript filenames."""
        return [f.name for f in self.transcripts_dir.glob("*.txt")]
    
    def get_transcripts_by_quality(self) -> Dict[str, List[str]]:
        """Group available transcripts by inferred quality level."""
        quality_groups = {"expert": [], "intermediate": [], "beginner": []}
        
        for file_path in self.transcripts_dir.glob("*.txt"):
            skill_level = self._infer_skill_level(file_path.stem, "")
            quality_groups[skill_level].append(file_path.name)
        
        return quality_groups


def load_sample_data(
    num_participants: int = 8, 
    transcripts_dir: Path = None,
    quality_distribution: Optional[Dict[str, float]] = None
) -> Tuple[List[Participant], List[Transcript]]:
    """
    Load sample data from real transcript files.
    
    Args:
        num_participants: Number of participants to load
        transcripts_dir: Directory containing transcript files
        quality_distribution: Optional distribution of quality levels
    
    Returns:
        Tuple of (participants, transcripts)
    """
    loader = TranscriptLoader(transcripts_dir)
    
    if quality_distribution is None:
        # Just load the first N transcripts
        all_participants, all_transcripts = loader.load_all_transcripts()
        return all_participants[:num_participants], all_transcripts[:num_participants]
    
    # Load with specific quality distribution
    quality_groups = loader.get_transcripts_by_quality()
    selected_files = []
    
    for quality, ratio in quality_distribution.items():
        count = int(num_participants * ratio)
        available_files = quality_groups.get(quality, [])
        
        # Take up to the requested count
        selected_files.extend(available_files[:count])
    
    # If we don't have enough files, pad with remaining files
    if len(selected_files) < num_participants:
        all_files = loader.get_available_transcripts()
        remaining_files = [f for f in all_files if f not in selected_files]
        needed = num_participants - len(selected_files)
        selected_files.extend(remaining_files[:needed])
    
    return loader.load_specific_transcripts(selected_files[:num_participants])


# Convenience function for backward compatibility
def create_sample_data(num_participants: int = 8, seed: int = None) -> Tuple[List[Participant], List[Transcript]]:
    """Create sample data by loading real transcripts (ignores seed for compatibility)."""
    return load_sample_data(num_participants) 