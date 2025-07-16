# AI Sales Evaluation Arena - Data Directory

This directory contains all transcript data for the AI Sales Evaluation Arena tournament system.

## Directory Structure

```
data/
├── transcripts/           # Real sales pitch transcripts
│   ├── participant_1.txt  # Actual sales presentation recordings
│   ├── participant_2.txt  # Transcribed from MP4 videos 
│   └── ...               # Production sales pitch data
├── test_transcripts/      # Numbered test data for system validation
│   ├── number_1.txt      # "This is my sales pitch and I am number 1..."
│   ├── number_2.txt      # "This is my sales pitch and I am number 2..."
│   ├── ...               # Simple numbered content for testing
│   └── number_11.txt     # Test data includes all participants (1-11)
├── output/               # Tournament results and visualizations
└── test_output/          # Test tournament outputs
```

## Usage

### Real Sales Tournaments (Production Data)
```bash
pipenv run python tests/test_simple_tournament.py \
  --transcript-dir data/transcripts \
  --tournament-name "Q4 Sales Championship" \
  --verbose
```

### Test Tournaments (Numbered Test Data)  
```bash
pipenv run python tests/test_simple_tournament.py \
  --tournament-name "System Validation Test" \
  --verbose
```

### Custom Directory Support
```bash
pipenv run python tests/test_simple_tournament.py \
  --transcript-dir path/to/any/transcripts \
  --custom-instructions "Your evaluation criteria..." \
  --verbose
```

## Test Data Features

The `test_transcripts/` directory contains:
- **11 numbered participants** (Number 1 through Number 11)
- **Consistent format** for predictable testing
- **Built-in evaluation instructions** that rank higher numbers as better
- **Complete tournament validation** (55 matches in round-robin)
- **GIF generation testing** with all participants including Number 11

## Evaluation Modes

### Default Mode (Production Rubric)
When using `data/transcripts`, the system applies the full Pyroscope sales pitch rubric:
- ICP Alignment
- PBO Messaging 
- Profiling Explanation
- Observability Context
- Talk Track Alignment

### Test Mode (Numbered Instructions)
When using `data/test_transcripts`, the system automatically applies custom numbered evaluation:
- Higher numbers = "better" sales pitches
- Tests LLM following custom instructions
- Validates tournament logic and visualizations
- Demonstrates system flexibility

## Output Structure

Tournament results are saved to the specified output directory (defaults to `data/test_output`):
```
data/test_output/
├── tournament_progression.gif    # Animated progression showing wins over time
├── visualizations/
│   ├── leaderboard.html         # Interactive leaderboard chart
│   └── bracket.html             # Tournament bracket visualization
└── detailed_results.json        # Complete tournament data
```

## Architecture Benefits

1. **Unified Data Management**: All transcript data in one location
2. **Clear Separation**: Production vs test data clearly organized
3. **Flexible Input**: Any directory structure supported via CLI
4. **Consistent Output**: Same visualization system for all tournaments
5. **Easy Testing**: Built-in test data for rapid validation

This structure ensures clean separation between real sales data and test data while maintaining the flexibility to run tournaments with any transcript directory. 