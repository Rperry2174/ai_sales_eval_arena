"""Feedback generation and writing for tournament matchups.

Generates per-matchup summaries and writes them to salespeople folders
organized by wins and losses.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID

from .models import Tournament, Match, Participant, Transcript, MatchStatus

logger = logging.getLogger(__name__)


def get_participant_key(
    participant: Participant,
    transcript: Transcript,
) -> str:
    """Get the filename-stem key for a participant.
    
    Uses the transcript's metadata filename if available,
    otherwise falls back to a sanitized version of the participant name.
    
    Args:
        participant: The participant
        transcript: The participant's transcript
        
    Returns:
        A filesystem-safe key string (e.g., "allegra_beth")
    """
    # Prefer the original filename stem from metadata
    if transcript.metadata and "filename" in transcript.metadata:
        filename = transcript.metadata["filename"]
        # Remove extension to get stem
        return Path(filename).stem
    
    # Fallback: convert participant name to snake_case
    name = participant.name.lower()
    # Replace spaces and special chars with underscores
    key = "".join(c if c.isalnum() else "_" for c in name)
    # Collapse multiple underscores
    while "__" in key:
        key = key.replace("__", "_")
    return key.strip("_")


def generate_matchup_summary_markdown(
    winner: Participant,
    loser: Participant,
    winner_key: str,
    loser_key: str,
    comparison_feedback: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    rubric_criteria: Optional[List[str]] = None,
    winner_was_participant_a: bool = True,
) -> str:
    """Generate a Markdown summary for a single matchup.
    
    The summary is written in 3rd-person neutral language so it can be
    placed in both the winner's wins/ folder and the loser's losses/ folder.
    
    Args:
        winner: The winning participant
        loser: The losing participant  
        winner_key: Filename stem for winner
        loser_key: Filename stem for loser
        comparison_feedback: The LLM's comparison reasoning
        metadata: Optional metadata from grading (strengths, weaknesses, etc.)
        rubric_criteria: Optional list of rubric criterion names
        winner_was_participant_a: True if winner was participant_a in the comparison
        
    Returns:
        Markdown content string
    """
    lines = []
    
    # Header
    lines.append(f"# Matchup: {winner.name} vs {loser.name}")
    lines.append("")
    lines.append(f"**Winner:** {winner.name} (`{winner_key}`)")
    lines.append(f"**Loser:** {loser.name} (`{loser_key}`)")
    lines.append("")
    
    # Overall Summary
    lines.append("## Overall Summary")
    lines.append("")
    if comparison_feedback:
        lines.append(comparison_feedback)
    else:
        lines.append(f"{winner.name} outperformed {loser.name} in this matchup.")
    lines.append("")
    
    # Performance Comparison (if we have metadata with strengths/weaknesses)
    if metadata:
        # Determine which participant was A vs B
        if winner_was_participant_a:
            winner_strengths = metadata.get("participant_a_strengths", [])
            winner_weaknesses = metadata.get("participant_a_weaknesses", [])
            loser_strengths = metadata.get("participant_b_strengths", [])
            loser_weaknesses = metadata.get("participant_b_weaknesses", [])
        else:
            winner_strengths = metadata.get("participant_b_strengths", [])
            winner_weaknesses = metadata.get("participant_b_weaknesses", [])
            loser_strengths = metadata.get("participant_a_strengths", [])
            loser_weaknesses = metadata.get("participant_a_weaknesses", [])
        
        key_differentiators = metadata.get("key_differentiators", [])
        
        # Key Differentiators Table
        if key_differentiators:
            lines.append("## Key Differentiators")
            lines.append("")
            lines.append("| Factor | Why It Mattered |")
            lines.append("|--------|-----------------|")
            for diff in key_differentiators[:5]:  # Limit to 5 rows
                # Escape pipe characters in the content
                escaped_diff = diff.replace("|", "\\|")
                lines.append(f"| {winner.name}'s Advantage | {escaped_diff} |")
            lines.append("")
        
        # Strengths and Weaknesses Breakdown
        lines.append("## Detailed Comparison")
        lines.append("")
        
        # Winner's Strengths
        if winner_strengths:
            lines.append(f"### {winner.name}'s Strengths (Winner)")
            lines.append("")
            for strength in winner_strengths[:5]:
                lines.append(f"- {strength}")
            lines.append("")
        
        # Loser's Strengths (what they did well)
        if loser_strengths:
            lines.append(f"### {loser.name}'s Strengths")
            lines.append("")
            for strength in loser_strengths[:5]:
                lines.append(f"- {strength}")
            lines.append("")
        
        # Winner's Areas for Improvement
        if winner_weaknesses:
            lines.append(f"### {winner.name}'s Areas for Improvement")
            lines.append("")
            for weakness in winner_weaknesses[:3]:
                lines.append(f"- {weakness}")
            lines.append("")
        
        # Loser's Areas for Improvement
        if loser_weaknesses:
            lines.append(f"### {loser.name}'s Areas for Improvement")
            lines.append("")
            for weakness in loser_weaknesses[:5]:
                lines.append(f"- {weakness}")
            lines.append("")
    
    # Coaching Notes
    lines.append("## Coaching Notes")
    lines.append("")
    
    # Winner's takeaways
    lines.append(f"### For {winner.name} (Winner)")
    lines.append("")
    if metadata:
        improvement = metadata.get("improvement_suggestions", {})
        winner_suggestion = improvement.get(winner.name)
        if winner_suggestion:
            lines.append(f"- **Keep doing:** {winner_suggestion}")
        else:
            lines.append("- Continue the strong performance demonstrated in this matchup")
    else:
        lines.append("- Continue the strong performance demonstrated in this matchup")
    lines.append("")
    
    # Loser's takeaways
    lines.append(f"### For {loser.name} (Areas for Improvement)")
    lines.append("")
    if metadata:
        improvement = metadata.get("improvement_suggestions", {})
        loser_suggestion = improvement.get(loser.name)
        if loser_suggestion:
            lines.append(f"- **Focus on:** {loser_suggestion}")
        else:
            lines.append("- Review the winning approach and identify specific areas to improve")
    else:
        lines.append("- Review the winning approach and identify specific areas to improve")
    lines.append("")
    
    # Footer with file references
    lines.append("---")
    lines.append(f"*Matchup between `{winner_key}` and `{loser_key}`*")
    
    return "\n".join(lines)


class FeedbackWriter:
    """Writes matchup feedback to per-salesperson wins/losses folders."""
    
    def __init__(
        self,
        output_dir: Path,
        overwrite: bool = True,
    ):
        """Initialize the feedback writer.
        
        Args:
            output_dir: Base output directory (typically tournament results dir)
            overwrite: If True, overwrite existing files. If False, skip existing.
        """
        self.output_dir = Path(output_dir)
        self.overwrite = overwrite
        self.feedback_dir = self.output_dir / "feedback" / "salespeople"
        self._generated_matchups: set = set()  # Track which matchups we've generated
        
    def _get_matchup_pair_key(self, key_a: str, key_b: str) -> Tuple[str, str]:
        """Get a deterministic pair key (sorted) to avoid generating twice."""
        return tuple(sorted([key_a, key_b]))
    
    def _ensure_salesperson_dirs(self, salesperson_key: str) -> Tuple[Path, Path]:
        """Ensure wins/ and losses/ directories exist for a salesperson.
        
        Returns:
            Tuple of (wins_dir, losses_dir)
        """
        salesperson_dir = self.feedback_dir / salesperson_key
        wins_dir = salesperson_dir / "wins"
        losses_dir = salesperson_dir / "losses"
        
        wins_dir.mkdir(parents=True, exist_ok=True)
        losses_dir.mkdir(parents=True, exist_ok=True)
        
        return wins_dir, losses_dir
    
    def write_matchup_feedback(
        self,
        winner: Participant,
        loser: Participant,
        winner_transcript: Transcript,
        loser_transcript: Transcript,
        comparison_feedback: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        winner_was_participant_a: bool = True,
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """Write feedback for a single matchup to both participants' folders.
        
        Generates the summary once and writes the same content to:
        - winner's wins/<loser_key>.md
        - loser's losses/<winner_key>.md
        
        Args:
            winner: The winning participant
            loser: The losing participant
            winner_transcript: Winner's transcript (for key extraction)
            loser_transcript: Loser's transcript (for key extraction)
            comparison_feedback: LLM comparison reasoning
            metadata: Optional grading metadata
            winner_was_participant_a: True if winner was participant_a in the comparison
            
        Returns:
            Tuple of (winner_file_path, loser_file_path) or (None, None) if skipped
        """
        # Get participant keys from transcript filenames
        winner_key = get_participant_key(winner, winner_transcript)
        loser_key = get_participant_key(loser, loser_transcript)
        
        # Check if we've already generated this matchup (avoid duplicates)
        pair_key = self._get_matchup_pair_key(winner_key, loser_key)
        if pair_key in self._generated_matchups:
            logger.debug(f"Skipping already-generated matchup: {winner_key} vs {loser_key}")
            return None, None
        
        # Ensure directories exist
        winner_wins_dir, _ = self._ensure_salesperson_dirs(winner_key)
        _, loser_losses_dir = self._ensure_salesperson_dirs(loser_key)
        
        # Define output paths
        winner_file = winner_wins_dir / f"{loser_key}.md"
        loser_file = loser_losses_dir / f"{winner_key}.md"
        
        # Check if files exist and we shouldn't overwrite
        if not self.overwrite:
            if winner_file.exists() and loser_file.exists():
                logger.debug(f"Skipping existing feedback files for {winner_key} vs {loser_key}")
                return None, None
        
        # Generate the markdown content (once)
        markdown_content = generate_matchup_summary_markdown(
            winner=winner,
            loser=loser,
            winner_key=winner_key,
            loser_key=loser_key,
            comparison_feedback=comparison_feedback,
            metadata=metadata,
            winner_was_participant_a=winner_was_participant_a,
        )
        
        # Write to both files (same content)
        winner_file.write_text(markdown_content, encoding="utf-8")
        loser_file.write_text(markdown_content, encoding="utf-8")
        
        # Track that we've generated this matchup
        self._generated_matchups.add(pair_key)
        
        logger.info(f"Wrote matchup feedback: {winner_key}/wins/{loser_key}.md and {loser_key}/losses/{winner_key}.md")
        
        return winner_file, loser_file


def write_tournament_feedback(
    tournament: Tournament,
    transcripts_by_participant: Dict[UUID, Transcript],
    output_dir: Path,
    overwrite: bool = True,
) -> Dict[str, List[Path]]:
    """Write feedback for all completed matches in a tournament.
    
    Args:
        tournament: The tournament with completed matches
        transcripts_by_participant: Mapping of participant ID to transcript
        output_dir: Base output directory
        overwrite: Whether to overwrite existing files
        
    Returns:
        Dict with "wins" and "losses" keys, each containing list of written file paths
    """
    writer = FeedbackWriter(output_dir, overwrite=overwrite)
    participants_by_id = {p.id: p for p in tournament.participants}
    
    written_files = {"wins": [], "losses": []}
    
    for match in tournament.matches:
        # Skip non-completed matches or matches without a winner
        if match.status != MatchStatus.COMPLETED or match.winner_id is None:
            continue
        
        # Determine winner and loser
        # participant1 is always "A" and participant2 is always "B" in comparisons
        if match.winner_id == match.participant1_id:
            winner = participants_by_id[match.participant1_id]
            loser = participants_by_id[match.participant2_id]
            winner_transcript = transcripts_by_participant.get(match.participant1_id)
            loser_transcript = transcripts_by_participant.get(match.participant2_id)
            winner_was_participant_a = True
        else:
            winner = participants_by_id[match.participant2_id]
            loser = participants_by_id[match.participant1_id]
            winner_transcript = transcripts_by_participant.get(match.participant2_id)
            loser_transcript = transcripts_by_participant.get(match.participant1_id)
            winner_was_participant_a = False
        
        if not winner_transcript or not loser_transcript:
            logger.warning(f"Missing transcript for match {match.id}, skipping feedback")
            continue
        
        # Write feedback for this match
        winner_file, loser_file = writer.write_matchup_feedback(
            winner=winner,
            loser=loser,
            winner_transcript=winner_transcript,
            loser_transcript=loser_transcript,
            comparison_feedback=match.comparison_feedback,
            metadata=match.comparison_metadata,  # Includes strengths, weaknesses, key_differentiators
            winner_was_participant_a=winner_was_participant_a,
        )
        
        if winner_file:
            written_files["wins"].append(winner_file)
        if loser_file:
            written_files["losses"].append(loser_file)
    
    logger.info(f"Wrote {len(written_files['wins'])} win files and {len(written_files['losses'])} loss files")
    return written_files
