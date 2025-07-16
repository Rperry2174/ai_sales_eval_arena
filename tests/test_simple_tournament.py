"""
Unified Tournament Test System

This test can run tournaments with:
- ANY transcript directory (data/transcripts, data/test_transcripts, etc.)
- CUSTOM rubric and comparison instructions 
- REAL production tournament system
- Complete visualizations including GIF with all participants

Usage:
    pipenv run python -m pytest tests/test_simple_tournament.py::test_tournament_with_data_dir -v -s
    pipenv run python -m pytest tests/test_simple_tournament.py::test_tournament_with_test_data -v -s
"""

import pytest
import asyncio
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from pathlib import Path
from typing import Optional, Dict, Any

from ai_sales_eval_arena.models import (
    TournamentFormat, ArenaConfig
)
from ai_sales_eval_arena.transcript_loader import TranscriptLoader
from ai_sales_eval_arena.tournament import TournamentManager
from ai_sales_eval_arena.grading import GradingPrompts
from ai_sales_eval_arena.visualization import TournamentVisualizer


async def run_tournament_with_custom_instructions(
    transcript_dir: Path,
    output_dir: Path,
    arena_config: ArenaConfig,
    tournament_name: str = "Custom Tournament",
    rubric: Optional[str] = None,
    comparison_instructions: Optional[str] = None,
    tournament_format: TournamentFormat = TournamentFormat.ROUND_ROBIN,
    verbose_logging: bool = False
):
    """
    Run a tournament with any transcript directory and custom evaluation instructions.
    
    Args:
        transcript_dir: Directory containing transcript files (any .txt files)
        output_dir: Directory to save results and visualizations
        arena_config: Arena configuration with API keys
        tournament_name: Name for the tournament
        rubric: Custom rubric for evaluation (if None, uses default Pyroscope rubric)
        comparison_instructions: Custom instructions for comparisons
        tournament_format: Tournament format (round-robin, elimination, etc.)
        verbose_logging: Whether to log each API call
    
    Returns:
        Tournament: Completed tournament object
    """
    
    print(f"\n🏆 Running Tournament: {tournament_name}")
    print(f"=" * 60)
    
    # Load transcripts from any directory
    print(f"📁 Loading transcripts from: {transcript_dir}")
    
    if not transcript_dir.exists():
        raise FileNotFoundError(f"Transcript directory not found: {transcript_dir}")
    
    loader = TranscriptLoader(str(transcript_dir))
    participants, transcripts = loader.load_all_transcripts()
    
    print(f"✅ Loaded {len(participants)} participants:")
    for p in sorted(participants, key=lambda x: x.name):
        print(f"   - {p.name}")
    
    # Calculate expected matches
    if tournament_format == TournamentFormat.ROUND_ROBIN:
        expected_matches = len(participants) * (len(participants) - 1) // 2
        print(f"📊 Tournament: {tournament_format.value} with {expected_matches} matches")
    
    # Display evaluation criteria
    if rubric or comparison_instructions:
        print(f"📋 Using CUSTOM evaluation criteria:")
        if rubric:
            print(f"   Custom rubric: {len(rubric)} characters")
            print(f"   Preview: {rubric[:100]}...")
        if comparison_instructions:
            print(f"   Custom instructions: {len(comparison_instructions)} characters")
            print(f"   Preview: {comparison_instructions[:100]}...")
    else:
        print(f"📋 Using DEFAULT Pyroscope sales pitch rubric:")
        prompts = GradingPrompts()
        print(f"   Criteria: ICP Alignment, PBO Messaging, Profiling Explanation, etc.")
    
    # Create tournament manager - PRODUCTION SYSTEM
    manager = TournamentManager(arena_config)
    
    # Override prompts if custom instructions provided
    if rubric or comparison_instructions:
        original_grader = manager.engine.grader
        
        # Create custom prompt versions
        if rubric:
            original_grader.prompts.RUBRIC = rubric
        if comparison_instructions:
            original_grader.prompts.COMPARATIVE_EVALUATION = comparison_instructions
    
    # Optional: Add verbose logging wrapper
    api_call_count = 0
    if verbose_logging:
        original_compare = manager.engine.grader.compare_transcripts
        
        async def logged_compare_transcripts(transcript_a, participant_a, transcript_b, participant_b):
            nonlocal api_call_count
            api_call_count += 1
            
            print(f"\n🔄 API Call #{api_call_count}: {participant_a.name} vs {participant_b.name}")
            print(f"   Transcript A: \"{transcript_a.content[:50]}...\"")
            print(f"   Transcript B: \"{transcript_b.content[:50]}...\"")
            
            result = await original_compare(transcript_a, participant_a, transcript_b, participant_b)
            
            winner_name = participant_a.name if result[0] == str(participant_a.id) else participant_b.name
            print(f"   🏆 Winner: {winner_name}")
            print(f"   💬 Reasoning: {result[1][:100]}...")
            
            return result
        
        manager.engine.grader.compare_transcripts = logged_compare_transcripts
        manager.engine.batch_grader.grader.compare_transcripts = logged_compare_transcripts
    
    # Create output directory
    output_dir.mkdir(exist_ok=True)
    
    print(f"\n⚡ Running tournament using PRODUCTION tournament system...")
    print(f"   📝 Each match uses real Anthropic Claude API")
    print(f"   🎯 Applying specified evaluation criteria")
    print(f"   📊 Processing {expected_matches} matches...")
    
    # Run the tournament - EXACT SAME METHOD AS PRODUCTION
    tournament = await manager.create_and_run_tournament(
        name=tournament_name,
        participants=participants,
        transcripts=transcripts,
        tournament_format=tournament_format,
        description=f"Tournament from {transcript_dir} with custom instructions"
    )
    
    # Verify tournament completed
    assert tournament.is_completed, "Tournament should complete successfully"
    assert tournament.winner_id is not None, "Tournament should have a winner"
    
    completed_matches = [m for m in tournament.matches if m.status.value == "completed"]
    assert len(completed_matches) == len(tournament.matches), "All matches should complete"
    
    if verbose_logging:
        print(f"\n✅ Tournament completed successfully!")
        print(f"   📞 Total API calls made: {api_call_count}")
        print(f"   ✅ Matches completed: {len(completed_matches)}")
    
    # Display results
    winner = next(p for p in participants if p.id == tournament.winner_id)
    winner_standing = next(s for s in tournament.standings if s.participant_id == winner.id)
    
    print(f"\n🏆 Tournament Results:")
    print(f"   Winner: {winner.name}")
    print(f"   Winner's record: {winner_standing.wins}W-{winner_standing.losses}L")
    print(f"   Total matches: {len(tournament.matches)}")
    
    # Print standings
    print(f"\n📊 Final Standings:")
    sorted_standings = sorted(tournament.standings, key=lambda s: s.rank)
    for standing in sorted_standings:
        participant_name = next(p.name for p in participants if p.id == standing.participant_id)
        print(f"   {standing.rank}. {participant_name}: {standing.wins}W-{standing.losses}L")
    
    # Generate visualizations using the same system
    try:
        print(f"\n🎨 Generating visualizations...")
        
        visualizer = TournamentVisualizer(arena_config.visualization)
        output_viz_dir = output_dir / "visualizations"
        output_viz_dir.mkdir(exist_ok=True)
        
        # Leaderboard
        leaderboard_fig = visualizer.create_leaderboard_chart(tournament)
        leaderboard_html = output_viz_dir / "leaderboard.html"
        leaderboard_fig.write_html(str(leaderboard_html))
        print(f"   📊 Leaderboard: {leaderboard_html}")
        
        # Tournament bracket
        bracket_fig = visualizer.create_tournament_bracket(tournament)
        bracket_html = output_viz_dir / "bracket.html"
        bracket_fig.write_html(str(bracket_html))
        print(f"   📊 Tournament bracket: {bracket_html}")
        
        # Tournament progression GIF with ALL participants including Number 11
        progression_gif = create_tournament_progression_gif(tournament, output_dir)
        if progression_gif:
            print(f"   🎬 Tournament progression GIF: {progression_gif}")
        
    except Exception as e:
        print(f"   ❌ Visualization error: {e}")
    
    print(f"\n📁 All results saved to: {output_dir}")
    
    return tournament


def create_tournament_progression_gif(tournament, output_dir: Path) -> str:
    """Create an animated GIF showing tournament progression over time with ALL participants."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.animation as animation
        
        # Create participant mapping
        participant_names = {p.id: p.name for p in tournament.participants}
        
        # Debug: Print all participants to verify everyone is included
        print(f"🔍 GIF Debug: Creating GIF for {len(tournament.participants)} participants:")
        for p in sorted(tournament.participants, key=lambda x: x.name):
            print(f"   - {p.name}")
        
        # Sort matches by completion time to show progression
        completed_matches = [m for m in tournament.matches if m.status.value == "completed" and m.completed_at]
        completed_matches.sort(key=lambda m: m.completed_at)
        
        if not completed_matches:
            print("❌ No completed matches found for progression GIF")
            return None
        
        # Track wins over time
        participant_wins = {p.id: [] for p in tournament.participants}
        match_times = []
        
        # Initialize with zeros
        for p_id in participant_wins:
            participant_wins[p_id].append(0)
        match_times.append("Start")
        
        # Add wins progressively
        current_wins = {p.id: 0 for p in tournament.participants}
        
        for i, match in enumerate(completed_matches):
            if match.winner_id:
                current_wins[match.winner_id] += 1
            
            # Record state after this match
            for p_id in participant_wins:
                participant_wins[p_id].append(current_wins[p_id])
            match_times.append(f"Match {i+1}")
        
        # Create the animated plot (optimized for horizontal bars)
        fig, ax = plt.subplots(figsize=(10, 14))  # Taller to accommodate horizontal bars with participant names
        
        # Colors for each participant (expand beyond 10 if needed)
        num_participants = len(tournament.participants)
        if num_participants <= 10:
            colors = plt.cm.tab10(range(num_participants))
        else:
            # Use a larger colormap for more than 10 participants
            colors = plt.cm.tab20(range(num_participants))
        
        def animate(frame):
            ax.clear()
            
            # Plot data up to current frame
            participants_to_plot = []
            wins_to_plot = []
            colors_to_plot = []
            
            # Sort participants by current wins (descending) for better visual impact with horizontal bars
            # This puts the current leader at the top of the chart
            participants_with_wins = [(p, participant_wins[p.id][frame]) for p in tournament.participants]
            sorted_participants = sorted(participants_with_wins, key=lambda x: (x[1], participant_names[x[0].id]), reverse=True)
            sorted_participants = [p[0] for p in sorted_participants]  # Extract just the participants
            
            for i, participant in enumerate(sorted_participants):
                participant_name = participant_names[participant.id]
                wins_at_frame = participant_wins[participant.id][frame]
                
                participants_to_plot.append(participant_name)
                wins_to_plot.append(wins_at_frame)
                colors_to_plot.append(colors[i % len(colors)])  # Handle more than 20 participants
            
            # Create horizontal bar chart (vertical layout)
            bars = ax.barh(participants_to_plot, wins_to_plot, color=colors_to_plot, alpha=0.8)
            
            # Customize the plot
            ax.set_xlabel('Wins', fontsize=16)
            ax.set_title(f'Tournament Progression - {match_times[frame]}', fontsize=18, fontweight='bold')
            ax.set_xlim(0, max(max(wins) for wins in participant_wins.values()) + 1)
            
            # Y-axis labels are readable without rotation for horizontal bars
            plt.setp(ax.get_yticklabels(), fontsize=12)
            
            # Add value labels on bars
            for bar, wins in zip(bars, wins_to_plot):
                if wins > 0:
                    ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2.,
                           f'{wins}', ha='left', va='center', fontweight='bold', fontsize=10)
            
            ax.grid(axis='x', alpha=0.3)
            plt.tight_layout()
        
        # Create animation
        anim = animation.FuncAnimation(
            fig, animate, frames=len(match_times), interval=800, repeat=True
        )
        
        # Save as GIF
        gif_path = output_dir / "tournament_progression.gif"
        anim.save(str(gif_path), writer='pillow', fps=1.2)
        plt.close(fig)
        
        print(f"✅ Created tournament progression GIF: {gif_path}")
        return str(gif_path)
        
    except ImportError as e:
        print(f"❌ Cannot create GIF: Missing dependency {e}")
        return None
    except Exception as e:
        print(f"❌ Error creating progression GIF: {e}")
        return None


# Fixtures
@pytest.fixture
def arena_config():
    """Arena configuration for testing."""
    return ArenaConfig(
        anthropic_api_key="test-key-for-tournament",
        anthropic_model="claude-3-5-sonnet-20241022",
        max_concurrent_matches=3,
        grading_timeout_seconds=60
    )


# Test cases for different scenarios
@pytest.mark.asyncio
async def test_tournament_with_data_dir(arena_config):
    """
    Test tournament with data/transcripts directory using default Pyroscope rubric.
    
    This would be used for real sales pitch tournaments.
    """
    
    # Skip if no real API key
    if not arena_config.anthropic_api_key or "test-key" in arena_config.anthropic_api_key:
        pytest.skip("No real Anthropic API key provided - skipping real tournament test")
    
    transcript_dir = Path("data/transcripts")
    
    if not transcript_dir.exists():
        pytest.skip(f"No data directory found at {transcript_dir}")
    
    output_dir = Path("tournament_results_data")
    
    tournament = await run_tournament_with_custom_instructions(
        transcript_dir=transcript_dir,
        output_dir=output_dir,
        arena_config=arena_config,
        tournament_name="Sales Pitch Tournament (Data Directory)",
        # Uses default Pyroscope rubric - no custom rubric/instructions
        tournament_format=TournamentFormat.ROUND_ROBIN,
        verbose_logging=True
    )
    
    print(f"✅ Data directory tournament completed with {len(tournament.participants)} participants")


@pytest.mark.asyncio
async def test_tournament_with_test_data(arena_config):
    """
    Test tournament with data/test_transcripts using numbered comparison instructions.
    
    This demonstrates custom rubric for simple numerical comparison testing.
    """
    
    # Skip if no real API key
    if not arena_config.anthropic_api_key or "test-key" in arena_config.anthropic_api_key:
        pytest.skip("No real Anthropic API key provided - skipping real tournament test")
    
    transcript_dir = Path("data/test_transcripts")
    
    if not transcript_dir.exists():
        pytest.skip(f"No test data directory found at {transcript_dir}")
    
    output_dir = Path("tournament_results_test_data")
    
    # Custom instructions for numbered transcript evaluation
    numbered_comparison_instructions = """
You are evaluating numbered sales pitches for testing purposes.

## Your Task
Compare these two sales pitches and determine which represents a "higher number" or "better" pitch.

## Evaluation Approach
- Look for numerical content in the sales pitches
- Higher numbers should generally be considered "better" sales pitches
- Consider factors like confidence, ambition, and scope implied by the numbers
- The participant with the higher number should typically win

## Participant A: {participant_a_name}
{transcript_a}

## Participant B: {participant_b_name}  
{transcript_b}

## Instructions
Determine which participant delivered the "better" sales pitch based on the implied numerical value and confidence.

Respond ONLY with valid JSON in this exact format:
{{
  "winner_name": "{participant_a_name}",
  "winner_reasoning": "Detailed explanation of why this participant won",
  "participant_a_strengths": ["Clear numerical value", "Confident delivery"],
  "participant_a_weaknesses": ["Could be more specific"],
  "participant_b_strengths": ["Good structure"],
  "participant_b_weaknesses": ["Lower numerical value", "Less ambitious"],
  "key_differentiators": ["Numerical value", "Confidence level"],
  "improvement_suggestions": {{
    "{participant_a_name}": "Maintain strong numerical positioning",
    "{participant_b_name}": "Consider higher numerical targets"
  }}
}}
"""
    
    tournament = await run_tournament_with_custom_instructions(
        transcript_dir=transcript_dir,
        output_dir=output_dir,
        arena_config=arena_config,
        tournament_name="Numbered Test Tournament (Test Data)",
        comparison_instructions=numbered_comparison_instructions,
        tournament_format=TournamentFormat.ROUND_ROBIN,
        verbose_logging=True
    )
    
    # Analyze how well the custom instructions worked with numbered content
    print(f"\n🔍 Numbered Tournament Analysis:")
    print(f"   Question: Did the LLM correctly rank numbered content?")
    
    standing_data = []
    for standing in tournament.standings:
        participant_name = next(p.name for p in tournament.participants if p.id == standing.participant_id)
        try:
            number = int(participant_name.split()[-1])
            standing_data.append((number, standing.wins, standing.rank))
        except (ValueError, IndexError):
            print(f"   Warning: Could not extract number from {participant_name}")
    
    standing_data.sort(key=lambda x: x[0])  # Sort by number
    
    print(f"   Results by number:")
    for number, wins, rank in standing_data:
        expected_strong = number >= 8
        actual_strong = rank <= 3
        match_icon = "✅" if expected_strong == actual_strong else "❓"
        performance = "Strong" if actual_strong else "Weak"
        print(f"     Number {number:2d}: {wins} wins, rank {rank} - {performance} {match_icon}")
    
    print(f"✅ Test data tournament completed with {len(tournament.participants)} participants")


@pytest.mark.asyncio
async def test_tournament_basic_loading():
    """
    Basic test to verify transcript loading works without API calls.
    """
    
    test_dir = Path("data/test_transcripts")
    
    if not test_dir.exists():
        pytest.skip(f"No test data directory found at {test_dir}")
    
    loader = TranscriptLoader(str(test_dir))
    participants, transcripts = loader.load_all_transcripts()
    
    assert len(participants) >= 10, f"Expected at least 10 participants, got {len(participants)}"
    assert len(transcripts) >= 10, f"Expected at least 10 transcripts, got {len(transcripts)}"
    
    # Check content format
    for transcript in transcripts:
        assert len(transcript.content) >= 50
        assert transcript.word_count > 0
    
    print(f"✅ Successfully loaded {len(participants)} participants from {test_dir}")
    for p in sorted(participants, key=lambda x: x.name):
        print(f"   - {p.name}")


if __name__ == "__main__":
    """
    Run tournaments directly for testing and development.
    
    Usage:
        pipenv run python tests/test_simple_tournament.py
        
    With arguments:
        pipenv run python tests/test_simple_tournament.py \
          --transcript-dir test_data/transcripts \
          --output-dir my_tournament_results \
          --custom-instructions "Your custom evaluation prompt here..." \
          --tournament-name "My Custom Tournament" \
          --verbose
    """
    
    import argparse
    import sys
    
    async def main():
        parser = argparse.ArgumentParser(
            description="Run AI Sales Evaluation Arena Tournament with custom instructions",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Basic run with test data and built-in numbered instructions
  pipenv run python tests/test_simple_tournament.py --transcript-dir data/test_transcripts
  
  # Custom tournament with your own evaluation criteria
  pipenv run python tests/test_simple_tournament.py \\
    --transcript-dir data/transcripts \\
    --output-dir data/sales_results \\
    --tournament-name "Q4 Sales Pitch Championship" \\
    --custom-instructions "Evaluate based on technical depth and customer focus..." \\
    --verbose
  
  # Use custom rubric file
  pipenv run python tests/test_simple_tournament.py \\
    --transcript-dir custom_pitches/ \\
    --rubric-file my_custom_rubric.txt \\
    --verbose
            """
        )
        
        parser.add_argument(
            "--transcript-dir",
            type=str,
            default="data/test_transcripts",
            help="Directory containing transcript files (.txt files)"
        )
        
        parser.add_argument(
            "--output-dir", 
            type=str,
            default="data/test_output",
            help="Directory to save results and visualizations"
        )
        
        parser.add_argument(
            "--tournament-name",
            type=str,
            default="Custom Tournament",
            help="Name for the tournament"
        )
        
        parser.add_argument(
            "--custom-instructions",
            type=str,
            help="Custom comparison instructions for evaluating transcripts"
        )
        
        parser.add_argument(
            "--rubric-file",
            type=str,
            help="Path to file containing custom rubric"
        )
        
        parser.add_argument(
            "--anthropic-api-key",
            type=str,
            help="Anthropic API key (if not set in environment)"
        )
        
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose logging of API calls"
        )
        
        parser.add_argument(
            "--tournament-format",
            choices=["round-robin", "single-elimination"],
            default="round-robin",
            help="Tournament format"
        )
        
        args = parser.parse_args()
        
        # Determine transcript directory
        transcript_dir = Path(args.transcript_dir)
        if not transcript_dir.exists():
            print(f"❌ Error: Transcript directory not found: {transcript_dir}")
            print(f"💡 Please create the directory or use --transcript-dir to specify a different path")
            sys.exit(1)
        
        # Determine output directory  
        output_dir = Path(args.output_dir)
        
        # Load custom rubric from file if provided
        custom_rubric = None
        if args.rubric_file:
            rubric_path = Path(args.rubric_file)
            if rubric_path.exists():
                custom_rubric = rubric_path.read_text()
                print(f"📋 Loaded custom rubric from: {rubric_path}")
            else:
                print(f"❌ Error: Rubric file not found: {rubric_path}")
                sys.exit(1)
        
        # Determine custom instructions
        custom_instructions = args.custom_instructions
        
        # Use built-in numbered instructions for test_transcripts if no custom instructions provided
        if not custom_instructions and transcript_dir.name == "test_transcripts" and transcript_dir.parent.name == "data":
            print(f"🔢 Using built-in numbered evaluation instructions for test_transcripts")
            custom_instructions = """
You are evaluating numbered sales pitches for testing purposes.

## Your Task
Compare these two sales pitches and determine which represents a "higher number" or "better" pitch.

## Evaluation Approach
- Look for numerical content in the sales pitches
- Higher numbers should generally be considered "better" sales pitches
- Consider factors like confidence, ambition, and scope implied by the numbers
- The participant with the higher number should typically win

## Participant A: {participant_a_name}
{transcript_a}

## Participant B: {participant_b_name}  
{transcript_b}

## Instructions
Determine which participant delivered the "better" sales pitch based on the implied numerical value and confidence.

Respond ONLY with valid JSON in this exact format:
{{
  "winner_name": "{participant_a_name}",
  "winner_reasoning": "Detailed explanation of why this participant won",
  "participant_a_strengths": ["Clear numerical value", "Confident delivery"],
  "participant_a_weaknesses": ["Could be more specific"],
  "participant_b_strengths": ["Good structure"],
  "participant_b_weaknesses": ["Lower numerical value", "Less ambitious"],
  "key_differentiators": ["Numerical value", "Confidence level"],
  "improvement_suggestions": {{
    "{participant_a_name}": "Maintain strong numerical positioning",
    "{participant_b_name}": "Consider higher numerical targets"
  }}
}}
"""
        
        # Configure tournament format
        tournament_format = TournamentFormat.ROUND_ROBIN if args.tournament_format == "round-robin" else TournamentFormat.SINGLE_ELIMINATION
        
        # Setup API key
        api_key = args.anthropic_api_key
        if not api_key:
            import os
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                print(f"❌ Error: No Anthropic API key provided")
                print(f"💡 Set ANTHROPIC_API_KEY environment variable or use --anthropic-api-key")
                print(f"💡 Example: export ANTHROPIC_API_KEY='your-key-here'")
                sys.exit(1)
        
        # Create configuration
        config = ArenaConfig(
            anthropic_api_key=api_key,
            anthropic_model="claude-3-5-sonnet-20241022",
            max_concurrent_matches=3
        )
        
        # Run the tournament
        try:
            tournament = await run_tournament_with_custom_instructions(
                transcript_dir=transcript_dir,
                output_dir=output_dir,
                arena_config=config,
                tournament_name=args.tournament_name,
                rubric=custom_rubric,
                comparison_instructions=custom_instructions,
                tournament_format=tournament_format,
                verbose_logging=args.verbose
            )
            
            print(f"\n🎉 Tournament completed successfully!")
            print(f"📁 Results saved to: {output_dir}")
            print(f"🏆 Winner: {tournament.name}")
            print(f"📊 Participants: {len(tournament.participants)}")
            print(f"🔥 Matches: {len(tournament.matches)}")
            
        except Exception as e:
            print(f"❌ Tournament failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # Run the main function
    asyncio.run(main()) 