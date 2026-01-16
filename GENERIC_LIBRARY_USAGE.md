# AI Sales Evaluation Arena - Generic Library Usage

This library is designed to be used generically with **any** corpus of transcripts and **any** evaluation rubric. There are no hardcoded product-specific criteria.

## Quick Start

### 1. Prepare Your Rubric

Create a markdown file with your evaluation criteria:

```markdown
# My Evaluation Rubric

## Scoring Scale
- 4 (Excellent): Exceptional performance
- 3 (Very Good): Strong performance
- 2 (Good): Adequate performance
- 1 (Needs Improvement): Below expectations

## Criteria

### 1. Product Knowledge
- Understanding of features and benefits
- Accuracy of technical explanations

### 2. Objection Handling
- Addresses concerns effectively
- Provides compelling rebuttals

### 3. Value Communication
- Connects features to business outcomes
- Quantifies impact where possible
```

### 2. Prepare Your Transcripts

Place plain text files in a directory, one file per participant:

```
transcripts/
├── alice_smith.txt    # Alice's pitch transcript
├── bob_jones.txt      # Bob's pitch transcript
└── carol_white.txt    # Carol's pitch transcript
```

**Filename becomes participant name:** `alice_smith.txt` → "Alice Smith"

### 3. Run the Tournament

```bash
cd ai_sales_eval_arena

pipenv run arena run-corpus \
  --name "Q1 Pitch Competition" \
  --transcripts-dir ../transcripts \
  --rubric-file ../my_rubric.md \
  --output-dir ../results/q1_competition
```

## Programmatic Usage

```python
import asyncio
from pathlib import Path

from ai_sales_eval_arena.models import ArenaConfig, TournamentFormat
from ai_sales_eval_arena.tournament import TournamentManager
from ai_sales_eval_arena.transcript_loader import TranscriptLoader

# Load your custom rubric
with open("my_rubric.md", "r") as f:
    rubric_text = f.read()

# Configure with custom rubric and context
config = ArenaConfig(
    anthropic_api_key="your-api-key",
    rubric_text=rubric_text,
    evaluation_context_text="""
    You are evaluating sales pitches for Cursor, an AI-powered code editor.
    Key differentiators: model agnosticity, semantic indexing, enterprise time-to-value.
    """
)

# Load transcripts (plain text files, one per participant)
loader = TranscriptLoader(Path("transcripts"))
participants, transcripts = loader.load_all_transcripts()

# Run tournament
async def run():
    manager = TournamentManager(config)
    tournament = await manager.create_and_run_tournament(
        name="Q1 Pitch Competition",
        participants=participants,
        transcripts=transcripts,
        tournament_format=TournamentFormat.ROUND_ROBIN
    )
    
    # Print results
    for standing in tournament.standings:
        participant = next(p for p in participants if p.id == standing.participant_id)
        print(f"{standing.rank}. {participant.name}: {standing.wins} wins")

asyncio.run(run())
```

## Configuration Options

### ArenaConfig Fields

| Field | Type | Description |
|-------|------|-------------|
| `anthropic_api_key` | str | Your Anthropic API key |
| `anthropic_model` | str | Model to use (required, set in .env) |
| `rubric_text` | str | Custom rubric markdown/text |
| `evaluation_context_text` | str | Context about what's being evaluated |
| `individual_prompt_template` | str | Full custom prompt for individual grading |
| `comparative_prompt_template` | str | Full custom prompt for comparisons |
| `max_concurrent_matches` | int | Parallel API calls (default: 5) |

## Outputs

Each tournament run produces:

```
results/q1_competition/20260116_143022/
├── tournament_results.json      # Full tournament data
├── visualizations/
│   ├── leaderboard.html        # Interactive leaderboard
│   ├── leaderboard.png         # Static image
│   ├── tournament_bracket.html # Match results matrix
│   └── ...
└── tournament_progression.gif   # Animated progression

results/q1_competition/
└── history.jsonl               # Appended run summaries
```

## Key Design Principles

1. **No hardcoded criteria** - All evaluation criteria come from your rubric
2. **No hardcoded product context** - Provide your own evaluation context
3. **Generic input format** - Plain text files, one per participant
4. **Preprocessing is external** - Any format conversion happens outside the library
5. **Consistent outputs** - Same visualization format regardless of input
6. **History tracking** - Track tournament runs over time with rubric hashes
