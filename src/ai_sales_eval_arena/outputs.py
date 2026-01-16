"""Helpers for exporting tournament outputs and history."""

import json
import logging
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Optional, Dict, Any, List

from .models import Tournament

logger = logging.getLogger(__name__)


def create_tournament_progression_gif(tournament: Tournament, output_dir: Path) -> Optional[str]:
    """Create an animated GIF showing tournament progression over time."""
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

    current_wins = {p.id: 0 for p in tournament.participants}
    for i, match in enumerate(completed_matches, start=1):
        if match.winner_id:
            current_wins[match.winner_id] += 1
        for p_id in participant_wins:
            participant_wins[p_id].append(current_wins[p_id])
        match_labels.append(f"Match {i}")

    fig, ax = plt.subplots(figsize=(10, 14))
    num_participants = len(tournament.participants)
    colors = plt.cm.tab20(range(max(num_participants, 1)))

    def animate(frame: int) -> None:
        ax.clear()
        participants_with_wins = [
            (p, participant_wins[p.id][frame]) for p in tournament.participants
        ]
        sorted_participants = sorted(
            participants_with_wins,
            key=lambda x: (x[1], participant_names[x[0].id]),
            reverse=True
        )

        participants_to_plot = [participant_names[p.id] for p, _ in sorted_participants]
        wins_to_plot = [wins for _, wins in sorted_participants]
        colors_to_plot = [colors[i % len(colors)] for i in range(len(sorted_participants))]

        bars = ax.barh(participants_to_plot, wins_to_plot, color=colors_to_plot, alpha=0.8)
        ax.set_xlabel("Wins", fontsize=16)
        ax.set_title(f"Tournament Progression - {match_labels[frame]}", fontsize=18, fontweight="bold")
        ax.set_xlim(0, max(max(wins) for wins in participant_wins.values()) + 1)
        plt.setp(ax.get_yticklabels(), fontsize=12)

        for bar, wins in zip(bars, wins_to_plot):
            if wins > 0:
                ax.text(
                    bar.get_width() + 0.05,
                    bar.get_y() + bar.get_height() / 2.0,
                    f"{wins}",
                    ha="left",
                    va="center",
                    fontweight="bold",
                    fontsize=10
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
