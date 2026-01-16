"""Helpers for exporting tournament outputs and history."""

import json
import logging
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID

from .models import Tournament, Participant

logger = logging.getLogger(__name__)


def create_participant_color_mapping(participants: List[Participant]) -> Dict[UUID, Tuple[float, float, float, float]]:
    """Create a static color mapping for participants that persists across all visualizations.
    
    Each participant gets a unique color that stays the same regardless of their
    position in the standings, allowing viewers to track individual progress over time.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available for color mapping")
        return {}
    
    # Use tab20 colormap for up to 20 distinct colors
    num_participants = len(participants)
    colors = plt.cm.tab20(range(max(num_participants, 1)))
    
    color_mapping = {}
    for i, participant in enumerate(participants):
        color_mapping[participant.id] = colors[i % len(colors)]
    
    return color_mapping


def create_progression_snapshot(
    tournament: Tournament,
    match_num: int,
    total_matches: int,
    color_mapping: Dict[UUID, Tuple[float, float, float, float]],
    output_path: Path
) -> Optional[str]:
    """Create a single snapshot image of the tournament progression.
    
    Args:
        tournament: The tournament object with current standings
        match_num: Current match number (for title)
        total_matches: Total number of matches (for progress calculation)
        color_mapping: Static color mapping for each participant
        output_path: Path to save the snapshot image
    
    Returns:
        Path to the saved image, or None if failed
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        logger.warning(f"Cannot create progression snapshot: missing dependency {exc}")
        return None
    
    participant_names = {p.id: p.name for p in tournament.participants}
    
    # Get current standings sorted by wins (descending)
    standings_with_names = []
    for standing in tournament.standings:
        name = participant_names.get(standing.participant_id, "Unknown")
        standings_with_names.append((standing.participant_id, name, standing.wins))
    
    # Sort by wins descending, then by name for consistent ordering
    standings_with_names.sort(key=lambda x: (-x[2], x[1]))
    
    # Prepare data for plotting
    names = [item[1] for item in standings_with_names]
    wins = [item[2] for item in standings_with_names]
    colors = [color_mapping.get(item[0], (0.5, 0.5, 0.5, 1.0)) for item in standings_with_names]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, max(8, len(names) * 0.5)))
    
    # Create horizontal bar chart
    bars = ax.barh(names, wins, color=colors, alpha=0.85)
    
    # Configure axes
    ax.set_xlabel("Wins", fontsize=14)
    ax.set_title(f"Tournament Progression - Match {match_num}", fontsize=18, fontweight="bold")
    
    # Set x-axis limit based on maximum possible wins
    max_wins = max(wins) if wins else 0
    ax.set_xlim(0, max(max_wins + 1, total_matches // len(tournament.participants) + 2))
    
    # Add win count labels on bars
    for bar, win_count in zip(bars, wins):
        if win_count > 0:
            ax.text(
                bar.get_width() + 0.1,
                bar.get_y() + bar.get_height() / 2.0,
                f"{win_count}",
                ha="left",
                va="center",
                fontweight="bold",
                fontsize=11
            )
    
    # Style adjustments
    ax.invert_yaxis()  # Highest wins at top
    ax.grid(axis="x", alpha=0.3)
    plt.setp(ax.get_yticklabels(), fontsize=11)
    plt.tight_layout()
    
    # Save figure
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=100, bbox_inches='tight')
    plt.close(fig)
    
    logger.info(f"Created progression snapshot: {output_path}")
    return str(output_path)


def create_gif_from_milestone_images(
    output_dir: Path,
    gif_filename: str = "tournament_progression.gif",
    frame_duration_ms: int = 500
) -> Optional[str]:
    """Create animated GIF from snapshot images.
    
    Looks for snapshot images (match_XXXX.png) in the visualizations subdirectory
    and combines them into an animated GIF. Also supports legacy format
    (leaderboard_XXpct.png) for backwards compatibility.
    
    Args:
        output_dir: Base output directory containing visualizations/
        gif_filename: Name for the output GIF file
        frame_duration_ms: Duration of each frame in milliseconds (default 500ms)
    
    Returns:
        Path to the created GIF, or None if no snapshot images found
    """
    try:
        from PIL import Image
        import glob
    except ImportError as exc:
        logger.warning(f"Cannot create GIF: missing dependency {exc}")
        return None
    
    output_dir = Path(output_dir)
    viz_dir = output_dir / "visualizations"
    
    # Look for snapshot images - try new format first (match_XXXX.png)
    match_images = sorted(viz_dir.glob("match_*.png"))
    
    if match_images:
        images = match_images
        logger.info(f"Found {len(images)} match snapshot images")
    else:
        # Fall back to legacy format (leaderboard_XXpct.png)
        milestones = ["25", "50", "75", "100"]
        images = []
        for pct in milestones:
            img_path = viz_dir / f"leaderboard_{pct}pct.png"
            if img_path.exists():
                images.append(img_path)
        
        if images:
            logger.info(f"Found {len(images)} legacy milestone images")
    
    if not images:
        logger.warning(f"No snapshot images found in {viz_dir}")
        return None
    
    # Load images
    frames = []
    for img_path in images:
        try:
            img = Image.open(img_path)
            frames.append(img.copy())
            img.close()
        except Exception as e:
            logger.warning(f"Could not load image {img_path}: {e}")
    
    if not frames:
        logger.warning("No valid frames loaded for GIF")
        return None
    
    # Calculate frame duration - faster for more frames
    # Default: 500ms per frame, but adjust if many frames
    if len(frames) > 20:
        frame_duration_ms = max(200, frame_duration_ms // 2)  # Speed up for many frames
    
    # Save as GIF
    gif_path = output_dir / gif_filename
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=frame_duration_ms,
        loop=0
    )
    
    logger.info(f"Created tournament progression GIF with {len(frames)} frames: {gif_path}")
    return str(gif_path)


def create_tournament_progression_gif(tournament: Tournament, output_dir: Path) -> Optional[str]:
    """Create an animated GIF showing tournament progression over time.
    
    This creates frames for each match showing cumulative wins with static colors
    per participant (colors don't change as standings change).
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.animation as animation
    except ImportError as exc:
        logger.warning(f"Cannot create progression GIF: missing dependency {exc}")
        return None

    completed_matches = [
        m for m in tournament.matches
        if m.status.value == "completed" and m.completed_at
    ]
    completed_matches.sort(key=lambda m: m.completed_at)

    if not completed_matches:
        logger.warning("No completed matches found for progression GIF")
        return None

    participant_names = {p.id: p.name for p in tournament.participants}
    participant_wins: Dict[Any, List[int]] = {p.id: [0] for p in tournament.participants}
    match_labels = ["Start"]

    # Create STATIC color mapping - each participant keeps their color throughout
    color_mapping = create_participant_color_mapping(tournament.participants)

    current_wins = {p.id: 0 for p in tournament.participants}
    for i, match in enumerate(completed_matches, start=1):
        if match.winner_id:
            current_wins[match.winner_id] += 1
        for p_id in participant_wins:
            participant_wins[p_id].append(current_wins[p_id])
        match_labels.append(f"Match {i}")

    fig, ax = plt.subplots(figsize=(12, max(8, len(tournament.participants) * 0.5)))

    def animate(frame: int) -> None:
        ax.clear()
        participants_with_wins = [
            (p, participant_wins[p.id][frame]) for p in tournament.participants
        ]
        # Sort by wins descending, then by name for consistent ordering
        sorted_participants = sorted(
            participants_with_wins,
            key=lambda x: (-x[1], participant_names[x[0].id])
        )

        participants_to_plot = [participant_names[p.id] for p, _ in sorted_participants]
        wins_to_plot = [wins for _, wins in sorted_participants]
        # Use STATIC colors based on participant ID, not sorted position
        colors_to_plot = [color_mapping.get(p.id, (0.5, 0.5, 0.5, 1.0)) for p, _ in sorted_participants]

        bars = ax.barh(participants_to_plot, wins_to_plot, color=colors_to_plot, alpha=0.85)
        ax.set_xlabel("Wins", fontsize=14)
        ax.set_title(f"Tournament Progression - {match_labels[frame]}", fontsize=18, fontweight="bold")
        ax.set_xlim(0, max(max(wins) for wins in participant_wins.values()) + 1)
        ax.invert_yaxis()  # Highest wins at top
        plt.setp(ax.get_yticklabels(), fontsize=11)

        for bar, wins in zip(bars, wins_to_plot):
            if wins > 0:
                ax.text(
                    bar.get_width() + 0.1,
                    bar.get_y() + bar.get_height() / 2.0,
                    f"{wins}",
                    ha="left",
                    va="center",
                    fontweight="bold",
                    fontsize=11
                )

        ax.grid(axis="x", alpha=0.3)
        plt.tight_layout()

    anim = animation.FuncAnimation(
        fig, animate, frames=len(match_labels), interval=800, repeat=True
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    gif_path = output_dir / "tournament_progression.gif"
    anim.save(str(gif_path), writer="pillow", fps=1.2)
    plt.close(fig)

    logger.info(f"Created tournament progression GIF: {gif_path}")
    return str(gif_path)


def append_history_entry(
    history_file: Path,
    tournament: Tournament,
    model: str,
    rubric_text: Optional[str],
    input_dir: str,
    input_format: str,
    output_dir: str
) -> None:
    """Append a summary entry for this tournament run."""
    history_file = Path(history_file)
    history_file.parent.mkdir(parents=True, exist_ok=True)

    participant_names = {p.id: p.name for p in tournament.participants}
    winner_name = None
    if tournament.winner_id:
        winner_name = participant_names.get(tournament.winner_id, "Unknown")

    top_standings = sorted(tournament.standings, key=lambda s: s.rank)[:3]
    top_three = [
        participant_names.get(standing.participant_id, "Unknown")
        for standing in top_standings
    ]

    rubric_hash = None
    if rubric_text is not None:
        rubric_hash = sha256(rubric_text.encode("utf-8")).hexdigest()

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "tournament_id": str(tournament.id),
        "tournament_name": tournament.name,
        "format": tournament.format.value,
        "participants": len(tournament.participants),
        "matches": len(tournament.matches),
        "winner_id": str(tournament.winner_id) if tournament.winner_id else None,
        "winner_name": winner_name,
        "top_three": top_three,
        "model": model,
        "rubric_hash": rubric_hash,
        "input_dir": input_dir,
        "input_format": input_format,
        "output_dir": output_dir
    }

    with open(history_file, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
