"""Command-line interface for the AI Sales Evaluation Arena."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, List
import sys

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import print as rprint

from .models import TournamentFormat, ArenaConfig, VisualizationConfig
from .tournament import TournamentManager
from .transcript_loader import create_sample_data
from .visualization import TournamentVisualizer
from .config import get_config

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--config-file', type=click.Path(), help='Path to configuration file')
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config_file: Optional[str]) -> None:
    """AI Sales Evaluation Arena - Tournament framework for sales pitch evaluation."""
    
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load configuration
    try:
        config = get_config()
        # Override with file config if provided
        if config_file:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
                config = ArenaConfig(**config_data)
    except ValueError as e:
        console.print(f"[red]Configuration Error: {e}[/red]")
        console.print("[yellow]Please set ANTHROPIC_API_KEY in your environment or .env file[/yellow]")
        raise click.Abort()
    
    ctx.ensure_object(dict)
    ctx.obj['config'] = config
    ctx.obj['verbose'] = verbose


@cli.command()
@click.option('--name', '-n', required=True, help='Tournament name')
@click.option('--description', '-d', help='Tournament description')
@click.option('--format', '-f', 'tournament_format', 
              type=click.Choice(['round_robin', 'single_elimination', 'double_elimination']),
              default='round_robin', help='Tournament format')
@click.option('--participants', '-p', type=int, default=8, 
              help='Number of participants (will generate sample data)')
@click.option('--output-dir', '-o', type=click.Path(), default='results',
              help='Output directory for results')
@click.option('--visualize/--no-visualize', default=True,
              help='Generate visualizations')
@click.pass_context
def create_tournament(
    ctx: click.Context,
    name: str,
    description: Optional[str],
    tournament_format: str,
    participants: int,
    output_dir: str,
    visualize: bool
) -> None:
    """Create and run a new tournament."""
    
    config = ctx.obj['config']
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Convert string format to enum
    format_map = {
        'round_robin': TournamentFormat.ROUND_ROBIN,
        'single_elimination': TournamentFormat.SINGLE_ELIMINATION,
        'double_elimination': TournamentFormat.DOUBLE_ELIMINATION
    }
    tournament_fmt = format_map[tournament_format]
    
    async def run_tournament():
        """Async function to run the tournament."""
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            # Load sample data
            task1 = progress.add_task("Loading sample data...", total=None)
            participant_list, transcript_list = create_sample_data(participants)
            progress.update(task1, completed=True)
            
            # Create tournament manager
            task2 = progress.add_task("Setting up tournament...", total=None)
            manager = TournamentManager(config)
            progress.update(task2, completed=True)
            
            # Run tournament
            task3 = progress.add_task("Running AI evaluations...", total=None)
            tournament = await manager.create_and_run_tournament(
                name=name,
                description=description,
                participants=participant_list,
                transcripts=transcript_list,
                tournament_format=tournament_fmt
            )
            progress.update(task3, completed=True)
            
            # Save results
            task4 = progress.add_task("Saving results...", total=None)
            tournament_data = tournament.dict()
            
            with open(output_path / f"{name.replace(' ', '_')}_results.json", 'w') as f:
                json.dump(tournament_data, f, indent=2, default=str)
            
            progress.update(task4, completed=True)
            
            # Generate visualizations
            if visualize:
                task5 = progress.add_task("Creating visualizations...", total=None)
                viz_config = VisualizationConfig()
                visualizer = TournamentVisualizer(viz_config)
                
                exported_files = visualizer.export_visualizations(
                    tournament, 
                    output_path / "visualizations"
                )
                progress.update(task5, completed=True)
                
                rprint(f"\n[green]✓[/green] Visualizations saved to: {output_path / 'visualizations'}")
            
        # Display results
        _display_tournament_results(tournament)
        
        rprint(f"\n[green]✓[/green] Tournament completed! Results saved to: {output_path}")
    
    # Run the async function
    try:
        asyncio.run(run_tournament())
    except KeyboardInterrupt:
        rprint("\n[red]Tournament cancelled by user[/red]")
        sys.exit(1)
    except Exception as e:
        rprint(f"\n[red]Error running tournament: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--count', '-c', type=int, default=8, help='Number of participants to generate')
@click.option('--output-dir', '-o', type=click.Path(), default='data',
              help='Output directory for generated data')
@click.option('--format', '-f', type=click.Choice(['json', 'csv']), default='json',
              help='Output format')
@click.pass_context
def generate_data(ctx: click.Context, count: int, output_dir: str, format: str) -> None:
    """Load sample participant and transcript data from real transcript files."""
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        task = progress.add_task(f"Loading {count} participants...", total=None)
        
        participants, transcripts = create_sample_data(count)
        
        if format == 'json':
            # Save as JSON
            participants_data = [p.dict() for p in participants]
            transcripts_data = [t.dict() for t in transcripts]
            
            with open(output_path / 'participants.json', 'w') as f:
                json.dump(participants_data, f, indent=2, default=str)
            
            with open(output_path / 'transcripts.json', 'w') as f:
                json.dump(transcripts_data, f, indent=2, default=str)
                
        elif format == 'csv':
            # Save as CSV
            import pandas as pd
            
            participants_df = pd.DataFrame([p.dict() for p in participants])
            transcripts_df = pd.DataFrame([t.dict() for t in transcripts])
            
            participants_df.to_csv(output_path / 'participants.csv', index=False)
            transcripts_df.to_csv(output_path / 'transcripts.csv', index=False)
        
        progress.update(task, completed=True)
    
    rprint(f"\n[green]✓[/green] Loaded {count} participants and transcripts")
    rprint(f"[green]✓[/green] Data saved to: {output_path}")


@cli.command()
@click.argument('tournament_file', type=click.Path(exists=True))
@click.option('--output-dir', '-o', type=click.Path(), default='visualizations',
              help='Output directory for visualizations')
@click.option('--formats', '-f', multiple=True, 
              type=click.Choice(['html', 'png', 'pdf', 'svg']),
              default=['html', 'png'], help='Export formats')
@click.pass_context
def visualize(
    ctx: click.Context, 
    tournament_file: str, 
    output_dir: str, 
    formats: List[str]
) -> None:
    """Create visualizations from tournament results."""
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Load tournament data
    with open(tournament_file, 'r') as f:
        tournament_data = json.load(f)
    
    # Note: In a real implementation, you'd need to properly deserialize
    # the tournament object. For now, this is a placeholder.
    rprint(f"[yellow]Note: Visualization from file not fully implemented in demo[/yellow]")
    rprint(f"Loaded tournament data from: {tournament_file}")
    rprint(f"Would create visualizations in: {output_path}")


@cli.command()
@click.option('--count', '-c', type=int, default=1, help='Number of tournaments to run')
@click.option('--participants', '-p', type=int, default=6, help='Participants per tournament')
@click.option('--output-dir', '-o', type=click.Path(), default='benchmark_results',
              help='Output directory for benchmark results')
@click.pass_context
def benchmark(ctx: click.Context, count: int, participants: int, output_dir: str) -> None:
    """Run benchmark tournaments to test system performance."""
    
    config = ctx.obj['config']
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    async def run_benchmarks():
        """Run benchmark tournaments."""
        
        results = []
        
        with Progress(console=console) as progress:
            main_task = progress.add_task("Running benchmarks...", total=count)
            
            for i in range(count):
                tournament_task = progress.add_task(f"Tournament {i+1}", total=None)
                
                # Load data
                participant_list, transcript_list = create_sample_data(participants)
                
                # Run tournament
                manager = TournamentManager(config)
                import time
                start_time = time.time()
                
                tournament = await manager.create_and_run_tournament(
                    name=f"Benchmark Tournament {i+1}",
                    participants=participant_list,
                    transcripts=transcript_list
                )
                
                end_time = time.time()
                duration = end_time - start_time
                
                results.append({
                    'tournament_id': str(tournament.id),
                    'participants': participants,
                    'matches': len(tournament.matches),
                    'duration_seconds': duration,
                    'matches_per_second': len(tournament.matches) / duration if duration > 0 else 0
                })
                
                progress.update(tournament_task, completed=True)
                progress.update(main_task, advance=1)
        
        # Save benchmark results
        with open(output_path / 'benchmark_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        # Display summary
        _display_benchmark_results(results)
    
    try:
        asyncio.run(run_benchmarks())
        rprint(f"\n[green]✓[/green] Benchmark completed! Results saved to: {output_path}")
    except Exception as e:
        rprint(f"\n[red]Benchmark failed: {e}[/red]")
        sys.exit(1)


@cli.command()
def info() -> None:
    """Display system information and status."""
    
    panel_content = """
[bold blue]AI Sales Evaluation Arena[/bold blue]

[bold]Features:[/bold]
• AI-powered sales pitch evaluation using GPT-4
• Multiple tournament formats (Round Robin, Elimination)
• Interactive visualizations with Plotly
• Comprehensive performance analytics
• RESTful API with FastAPI
• Modern web interface

[bold]Components:[/bold]
• Transcript Loader: Load real sales pitch transcripts from files
• AI Grading: Structured evaluation against sales criteria
• Tournament Engine: Round-robin and elimination formats
• Visualization: Interactive charts and dashboards
• Web App: Modern interface for viewing results

[bold]Usage:[/bold]
• Run 'arena create-tournament' to start a new tournament
• Use 'arena generate-data' to create sample data
• Try 'arena benchmark' to test system performance
    """
    
    console.print(Panel(panel_content, title="System Information", border_style="blue"))


def _display_tournament_results(tournament) -> None:
    """Display tournament results in a formatted table."""
    
    # Tournament info
    rprint(f"\n[bold blue]Tournament: {tournament.name}[/bold blue]")
    if tournament.description:
        rprint(f"Description: {tournament.description}")
    
    rprint(f"Format: {tournament.format.value.replace('_', ' ').title()}")
    rprint(f"Participants: {len(tournament.participants)}")
    rprint(f"Matches: {len(tournament.matches)}")
    
    if tournament.winner_id:
        winner_name = next(
            (p.name for p in tournament.participants if p.id == tournament.winner_id),
            "Unknown"
        )
        rprint(f"[bold green]Winner: {winner_name}[/bold green]")
    
    # Standings table
    if tournament.standings:
        table = Table(title="Final Standings")
        table.add_column("Rank", style="cyan", no_wrap=True)
        table.add_column("Participant", style="magenta")
        table.add_column("Wins", justify="right", style="green")
        table.add_column("Losses", justify="right", style="red")
        table.add_column("Win %", justify="right", style="blue")
        table.add_column("Avg Score", justify="right", style="yellow")
        
        participant_names = {p.id: p.name for p in tournament.participants}
        
        for standing in tournament.standings:
            participant_name = participant_names.get(standing.participant_id, "Unknown")
            
            table.add_row(
                str(standing.rank),
                participant_name,
                str(standing.wins),
                str(standing.losses),
                f"{standing.win_percentage:.1f}%",
                f"{standing.average_score:.2f}"
            )
        
        console.print(table)


def _display_benchmark_results(results: List[dict]) -> None:
    """Display benchmark results."""
    
    table = Table(title="Benchmark Results")
    table.add_column("Tournament", style="cyan")
    table.add_column("Participants", justify="right", style="magenta")
    table.add_column("Matches", justify="right", style="blue")
    table.add_column("Duration (s)", justify="right", style="green")
    table.add_column("Matches/sec", justify="right", style="yellow")
    
    for i, result in enumerate(results, 1):
        table.add_row(
            f"#{i}",
            str(result['participants']),
            str(result['matches']),
            f"{result['duration_seconds']:.2f}",
            f"{result['matches_per_second']:.2f}"
        )
    
    console.print(table)
    
    # Summary statistics
    avg_duration = sum(r['duration_seconds'] for r in results) / len(results)
    avg_matches_per_sec = sum(r['matches_per_second'] for r in results) / len(results)
    
    rprint(f"\n[bold]Summary:[/bold]")
    rprint(f"Average duration: {avg_duration:.2f} seconds")
    rprint(f"Average throughput: {avg_matches_per_sec:.2f} matches/second")


def main() -> None:
    """Main entry point for the CLI."""
    cli()


if __name__ == '__main__':
    main() 