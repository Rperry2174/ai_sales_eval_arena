"""Tournament orchestration system for the AI Sales Evaluation Arena."""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from uuid import UUID, uuid4
import itertools

from .models import (
    Tournament, TournamentFormat, TournamentStandings, Participant, 
    Transcript, Match, MatchStatus, ArenaConfig
)
from .grading import AIGrader, BatchGrader
from .feedback import write_tournament_feedback

logger = logging.getLogger(__name__)


class TournamentEngine:
    """Core tournament orchestration engine."""
    
    def __init__(self, config: ArenaConfig):
        """Initialize tournament engine."""
        self.config = config
        self.grader = AIGrader(config)
        self.batch_grader = BatchGrader(self.grader, config.max_concurrent_matches)
        
    async def create_tournament(
        self,
        name: str,
        participants: List[Participant],
        transcripts: List[Transcript],
        tournament_format: TournamentFormat = TournamentFormat.ROUND_ROBIN,
        description: Optional[str] = None
    ) -> Tournament:
        """Create a new tournament with participants and their transcripts."""
        logger.info(f"Creating tournament '{name}' with {len(participants)} participants")
        
        # Validate that we have transcripts for all participants
        transcript_by_participant = {t.participant_id: t for t in transcripts}
        missing_transcripts = []
        for participant in participants:
            if participant.id not in transcript_by_participant:
                missing_transcripts.append(participant.name)
        
        if missing_transcripts:
            raise ValueError(f"Missing transcripts for participants: {missing_transcripts}")
        
        # Create tournament
        tournament = Tournament(
            name=name,
            description=description,
            format=tournament_format,
            participants=participants,
            matches=[],
            standings=[]
        )
        
        # Generate matches based on format
        matches = self._generate_matches(tournament, transcript_by_participant)
        tournament.matches = matches
        
        # Initialize standings
        standings = self._initialize_standings(participants)
        tournament.standings = standings
        
        logger.info(f"Tournament created with {len(matches)} matches")
        return tournament
    
    async def run_tournament(self, tournament: Tournament) -> Tournament:
        """Run the complete tournament."""
        logger.info(f"Starting tournament: {tournament.name}")
        tournament.started_at = datetime.utcnow()
        
        if tournament.format == TournamentFormat.ROUND_ROBIN:
            tournament = await self._run_round_robin(tournament)
        elif tournament.format == TournamentFormat.SINGLE_ELIMINATION:
            tournament = await self._run_single_elimination(tournament)
        elif tournament.format == TournamentFormat.DOUBLE_ELIMINATION:
            tournament = await self._run_double_elimination(tournament)
        else:
            raise ValueError(f"Unsupported tournament format: {tournament.format}")
        
        tournament.completed_at = datetime.utcnow()
        self._determine_winner(tournament)
        
        logger.info(f"Tournament completed: {tournament.name}")
        return tournament
    
    def _generate_matches(
        self, 
        tournament: Tournament, 
        transcript_by_participant: Dict[UUID, Transcript]
    ) -> List[Match]:
        """Generate matches based on tournament format."""
        matches = []
        
        if tournament.format == TournamentFormat.ROUND_ROBIN:
            # Every participant plays every other participant
            for i, participant1 in enumerate(tournament.participants):
                for participant2 in tournament.participants[i+1:]:
                    match = Match(
                        tournament_id=tournament.id,
                        participant1_id=participant1.id,
                        participant2_id=participant2.id,
                        transcript1_id=transcript_by_participant[participant1.id].id,
                        transcript2_id=transcript_by_participant[participant2.id].id
                    )
                    matches.append(match)
        
        elif tournament.format in [TournamentFormat.SINGLE_ELIMINATION, TournamentFormat.DOUBLE_ELIMINATION]:
            # Generate initial bracket matches
            matches = self._generate_bracket_matches(tournament, transcript_by_participant)
        
        return matches
    
    def _generate_bracket_matches(
        self, 
        tournament: Tournament, 
        transcript_by_participant: Dict[UUID, Transcript]
    ) -> List[Match]:
        """Generate bracket-style matches for elimination tournaments."""
        participants = tournament.participants.copy()
        
        # For simplicity, if odd number of participants, give one a bye
        if len(participants) % 2 == 1:
            # The participant with the highest experience gets a bye
            participants.sort(key=lambda p: p.experience_years or 0, reverse=True)
            bye_participant = participants.pop(0)
            logger.info(f"{bye_participant.name} receives a bye to the next round")
        
        matches = []
        # Create first round matches
        for i in range(0, len(participants), 2):
            participant1 = participants[i]
            participant2 = participants[i + 1]
            
            match = Match(
                tournament_id=tournament.id,
                participant1_id=participant1.id,
                participant2_id=participant2.id,
                transcript1_id=transcript_by_participant[participant1.id].id,
                transcript2_id=transcript_by_participant[participant2.id].id
            )
            matches.append(match)
        
        return matches
    
    def _initialize_standings(self, participants: List[Participant]) -> List[TournamentStandings]:
        """Initialize tournament standings."""
        standings = []
        for participant in participants:
            standing = TournamentStandings(
                participant_id=participant.id,
                wins=0,
                losses=0,
                draws=0,
                total_matches=0,
                average_score=0.0,
                win_percentage=0.0,
                rank=0
            )
            standings.append(standing)
        
        return standings
    
    async def _run_round_robin(self, tournament: Tournament) -> Tournament:
        """Run a round-robin tournament with per-match progress output."""
        import sys
        
        logger.info("Running round-robin tournament")
        print("\n📋 Processing matches one at a time...", flush=True)
        
        transcripts_by_id = {t.id: t for t in self._get_all_transcripts(tournament)}
        participants_by_id = {p.id: p for p in tournament.participants}
        
        total_matches = len(tournament.matches)
        
        # Process matches ONE AT A TIME for better progress tracking
        for match_num, match in enumerate(tournament.matches, start=1):
            transcript1 = transcripts_by_id[match.transcript1_id]
            transcript2 = transcripts_by_id[match.transcript2_id]
            participant1 = participants_by_id[match.participant1_id]
            participant2 = participants_by_id[match.participant2_id]
            
            # Log match start with flush to ensure immediate output
            print(f"\n{'='*60}", flush=True)
            print(f"🥊 Match {match_num}/{total_matches}: {participant1.name} vs {participant2.name}", flush=True)
            print(f"   ⏳ Calling AI for comparison...", flush=True)
            print(f"{'='*60}", flush=True)
            sys.stdout.flush()
            logger.info(f"Starting match {match_num}/{total_matches}: {participant1.name} vs {participant2.name}")
            
            match.status = MatchStatus.IN_PROGRESS
            
            try:
                # Run single comparison
                winner_id, feedback, metadata = await self.grader.compare_transcripts(
                    transcript1, participant1, transcript2, participant2
                )
                
                # Update match with result
                match.winner_id = UUID(winner_id)
                match.comparison_feedback = feedback
                match.comparison_metadata = metadata  # Store strengths, weaknesses, etc.
                match.status = MatchStatus.COMPLETED
                match.completed_at = datetime.utcnow()
                
                # Determine winner name
                winner_name = participant1.name if winner_id == str(participant1.id) else participant2.name
                print(f"✅ Winner: {winner_name}", flush=True)
                logger.info(f"Match {match_num} complete: {winner_name} wins")
                
                # Update standings after each match
                self._update_standings(tournament)
                
                # Print current standings
                print(f"\n📊 Current Standings (after {match_num} matches):", flush=True)
                for standing in tournament.standings[:5]:  # Top 5
                    name = participants_by_id[standing.participant_id].name
                    print(f"   {standing.rank}. {name}: {standing.wins}W-{standing.losses}L", flush=True)
                
                sys.stdout.flush()
                
                # Call progress callback if set
                if hasattr(self, '_progress_callback') and self._progress_callback:
                    await self._progress_callback(tournament, match_num, total_matches)
                    
            except Exception as e:
                logger.error(f"Match {match_num} failed: {e}")
                print(f"❌ Match failed: {e}", flush=True)
                match.status = MatchStatus.COMPLETED  # Mark as completed even if failed
                continue
        
        print(f"\n{'='*60}", flush=True)
        print(f"🏁 All {total_matches} matches completed!", flush=True)
        print(f"{'='*60}", flush=True)
        
        return tournament
    
    async def _run_single_elimination(self, tournament: Tournament) -> Tournament:
        """Run a single elimination tournament."""
        logger.info("Running single elimination tournament")
        
        current_matches = tournament.matches.copy()
        all_matches = tournament.matches.copy()
        transcripts_by_id = {t.id: t for t in self._get_all_transcripts(tournament)}
        participants_by_id = {p.id: p for p in tournament.participants}
        
        round_number = 1
        
        while len(current_matches) > 0:
            logger.info(f"Processing elimination round {round_number} with {len(current_matches)} matches")
            
            # Process current round
            comparison_pairs = []
            for match in current_matches:
                transcript1 = transcripts_by_id[match.transcript1_id]
                transcript2 = transcripts_by_id[match.transcript2_id]
                participant1 = participants_by_id[match.participant1_id]
                participant2 = participants_by_id[match.participant2_id]
                
                comparison_pairs.append((transcript1, participant1, transcript2, participant2))
                match.status = MatchStatus.IN_PROGRESS
            
            # Run comparisons for this round
            comparison_results = await self.batch_grader.compare_multiple(comparison_pairs)
            
            # Update matches and collect winners
            winners = []
            for i, (winner_id, feedback, metadata) in enumerate(comparison_results):
                match = current_matches[i]
                match.winner_id = UUID(winner_id)
                match.comparison_feedback = feedback
                match.status = MatchStatus.COMPLETED
                match.completed_at = datetime.utcnow()
                
                winners.append(UUID(winner_id))
            
            # Generate next round matches if we have more than one winner
            if len(winners) > 1:
                next_round_matches = []
                for i in range(0, len(winners), 2):
                    if i + 1 < len(winners):
                        participant1_id = winners[i]
                        participant2_id = winners[i + 1]
                        
                        match = Match(
                            tournament_id=tournament.id,
                            participant1_id=participant1_id,
                            participant2_id=participant2_id,
                            transcript1_id=transcripts_by_id[participant1_id].id,
                            transcript2_id=transcripts_by_id[participant2_id].id
                        )
                        next_round_matches.append(match)
                        all_matches.append(match)
                
                current_matches = next_round_matches
                round_number += 1
            else:
                # Tournament complete
                break
        
        tournament.matches = all_matches
        self._update_standings(tournament)
        
        return tournament
    
    async def _run_double_elimination(self, tournament: Tournament) -> Tournament:
        """Run a double elimination tournament."""
        # For now, implement as single elimination
        # Double elimination would require more complex bracket management
        logger.warning("Double elimination not fully implemented, falling back to single elimination")
        return await self._run_single_elimination(tournament)
    
    def _get_all_transcripts(self, tournament: Tournament) -> List[Transcript]:
        """Get all transcripts needed for the tournament."""
        # Get transcripts from the tournament's stored transcript mapping
        if hasattr(self, '_tournament_transcripts'):
            return list(self._tournament_transcripts.values())
        else:
            # Fallback - reconstruct from match transcript IDs
            transcript_ids = set()
            for match in tournament.matches:
                transcript_ids.add(match.transcript1_id)
                transcript_ids.add(match.transcript2_id)
            
            # This would need to be populated by the caller
            # For now, return empty list to avoid breaking
            return []
    
    def _update_standings(self, tournament: Tournament) -> None:
        """Update tournament standings based on match results."""
        # Reset standings
        standings_by_participant = {s.participant_id: s for s in tournament.standings}
        
        for standing in tournament.standings:
            standing.wins = 0
            standing.losses = 0
            standing.draws = 0
            standing.total_matches = 0
            standing.average_score = 0.0
        
        # Count wins/losses
        participant_scores = {p.id: [] for p in tournament.participants}
        
        for match in tournament.matches:
            if match.status == MatchStatus.COMPLETED and match.winner_id:
                # Update match counts
                standings_by_participant[match.participant1_id].total_matches += 1
                standings_by_participant[match.participant2_id].total_matches += 1
                
                # Update wins/losses
                if match.winner_id == match.participant1_id:
                    standings_by_participant[match.participant1_id].wins += 1
                    standings_by_participant[match.participant2_id].losses += 1
                elif match.winner_id == match.participant2_id:
                    standings_by_participant[match.participant2_id].wins += 1
                    standings_by_participant[match.participant1_id].losses += 1
                
                # Collect scores for average calculation
                if match.grade1:
                    participant_scores[match.participant1_id].append(match.grade1.overall_score)
                if match.grade2:
                    participant_scores[match.participant2_id].append(match.grade2.overall_score)
        
        # Calculate averages and win percentages
        for standing in tournament.standings:
            scores = participant_scores[standing.participant_id]
            standing.average_score = sum(scores) / len(scores) if scores else 0.0
            
            if standing.total_matches > 0:
                standing.win_percentage = (standing.wins / standing.total_matches) * 100
        
        # Sort by wins, then by average score, then by win percentage
        tournament.standings.sort(
            key=lambda s: (s.wins, s.average_score, s.win_percentage), 
            reverse=True
        )
        
        # Assign ranks
        for i, standing in enumerate(tournament.standings):
            standing.rank = i + 1
    
    def _determine_winner(self, tournament: Tournament) -> None:
        """Determine the tournament winner."""
        if tournament.standings:
            winner_standing = tournament.standings[0]
            tournament.winner_id = winner_standing.participant_id
            
            winner_name = next(
                (p.name for p in tournament.participants if p.id == tournament.winner_id),
                "Unknown"
            )
            logger.info(f"Tournament winner: {winner_name}")


class TournamentManager:
    """High-level tournament management interface."""
    
    def __init__(self, config: ArenaConfig):
        """Initialize tournament manager."""
        self.config = config
        self.engine = TournamentEngine(config)
        self.active_tournaments: Dict[UUID, Tournament] = {}
        self.output_dir: Optional[Any] = None
    
    async def create_and_run_tournament(
        self,
        name: str,
        participants: List[Participant],
        transcripts: List[Transcript],
        tournament_format: TournamentFormat = TournamentFormat.ROUND_ROBIN,
        description: Optional[str] = None,
        output_dir: Optional[Any] = None
    ) -> Tournament:
        """Create and run a complete tournament."""
        self.output_dir = output_dir
        
        tournament = await self.engine.create_tournament(
            name=name,
            participants=participants,
            transcripts=transcripts,
            tournament_format=tournament_format,
            description=description
        )
        
        self.active_tournaments[tournament.id] = tournament
        
        # Add transcripts to engine for processing
        # This is a workaround for the design - in a real system, 
        # transcripts would be stored in a database
        self.engine._tournament_transcripts = {t.id: t for t in transcripts}
        
        # Set up progress callback for intermediate saving
        if output_dir:
            self.engine._progress_callback = self._create_progress_callback(output_dir, self.config)
        
        tournament = await self.engine.run_tournament(tournament)
        
        # Generate feedback files if enabled and output_dir is provided
        if output_dir and self.config.enable_feedback_generation:
            try:
                from pathlib import Path
                transcripts_by_participant = {t.participant_id: t for t in transcripts}
                feedback_result = write_tournament_feedback(
                    tournament=tournament,
                    transcripts_by_participant=transcripts_by_participant,
                    output_dir=Path(output_dir),
                    overwrite=self.config.feedback_overwrite,
                )
                logger.info(f"Generated feedback: {len(feedback_result.get('wins', []))} win files, {len(feedback_result.get('losses', []))} loss files")
                print(f"\n📝 Generated feedback files in {output_dir}/feedback/salespeople/", flush=True)
            except Exception as e:
                logger.warning(f"Could not generate feedback files: {e}")
                print(f"⚠️ Could not generate feedback files: {e}", flush=True)
        
        return tournament
    
    def _create_progress_callback(self, output_dir, config: ArenaConfig):
        """Create a callback function for saving progress after each match.
        
        Args:
            output_dir: Directory to save progress files
            config: Arena configuration (includes snapshot_interval)
        """
        import json
        from pathlib import Path
        from .outputs import create_participant_color_mapping, create_progression_snapshot
        
        # Track which matches we've saved snapshots for
        saved_snapshots = set()
        
        # Color mapping will be initialized on first call (when we have tournament data)
        color_mapping = None
        
        # Get snapshot interval from config (1 = every match, 5 = every 5 matches, etc.)
        snapshot_interval = getattr(config, 'snapshot_interval', 1)
        
        async def save_progress(tournament: Tournament, match_num: int, total_matches: int):
            """Save intermediate results after each match."""
            nonlocal color_mapping
            
            try:
                output_path = Path(output_dir)
                
                # Initialize color mapping on first call (static colors for entire tournament)
                if color_mapping is None:
                    color_mapping = create_participant_color_mapping(tournament.participants)
                
                # Save current standings to a progress file
                progress_file = output_path / "progress.json"
                participant_names = {p.id: p.name for p in tournament.participants}
                
                progress_percent = round(match_num / total_matches * 100, 1)
                progress_data = {
                    "matches_completed": match_num,
                    "total_matches": total_matches,
                    "progress_percent": progress_percent,
                    "current_standings": [
                        {
                            "rank": s.rank,
                            "name": participant_names.get(s.participant_id, "Unknown"),
                            "wins": s.wins,
                            "losses": s.losses,
                            "win_percentage": s.win_percentage
                        }
                        for s in tournament.standings
                    ]
                }
                
                with open(progress_file, "w") as f:
                    json.dump(progress_data, f, indent=2)
                
                logger.info(f"Saved progress: {match_num}/{total_matches} matches ({progress_percent}%)")
                
                # Save visualization snapshot based on interval
                # Take snapshot if: match_num is divisible by interval OR it's the last match
                should_snapshot = (match_num % snapshot_interval == 0) or (match_num == total_matches)
                
                if should_snapshot and match_num not in saved_snapshots:
                    saved_snapshots.add(match_num)
                    try:
                        # Save leaderboard snapshot with static colors
                        viz_dir = output_path / "visualizations"
                        viz_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Name snapshots by match number for easy ordering
                        snapshot_file = viz_dir / f"match_{match_num:04d}.png"
                        
                        snapshot_path = create_progression_snapshot(
                            tournament=tournament,
                            match_num=match_num,
                            total_matches=total_matches,
                            color_mapping=color_mapping,
                            output_path=snapshot_file
                        )
                        
                        if snapshot_path:
                            print(f"📸 Saved snapshot after match {match_num}/{total_matches}: {snapshot_file}")
                            logger.info(f"Saved snapshot at match {match_num}")
                    except Exception as viz_e:
                        logger.warning(f"Could not save snapshot: {viz_e}")
                
            except Exception as e:
                logger.warning(f"Could not save progress: {e}")
        
        return save_progress
    
    def get_tournament(self, tournament_id: UUID) -> Optional[Tournament]:
        """Get a tournament by ID."""
        return self.active_tournaments.get(tournament_id)
    
    def list_tournaments(self) -> List[Tournament]:
        """List all tournaments."""
        return list(self.active_tournaments.values())
    
    async def get_live_standings(self, tournament_id: UUID) -> Optional[List[TournamentStandings]]:
        """Get live standings for a tournament."""
        tournament = self.get_tournament(tournament_id)
        if tournament:
            return tournament.standings
        return None


# Monkey patch the engine to handle transcripts
def _get_all_transcripts_patched(self, tournament: Tournament) -> List[Transcript]:
    """Patched method to get transcripts from stored data."""
    if hasattr(self, '_tournament_transcripts'):
        transcript_ids = set()
        for match in tournament.matches:
            transcript_ids.add(match.transcript1_id)
            transcript_ids.add(match.transcript2_id)
        
        return [self._tournament_transcripts[tid] for tid in transcript_ids if tid in self._tournament_transcripts]
    return []

TournamentEngine._get_all_transcripts = _get_all_transcripts_patched 