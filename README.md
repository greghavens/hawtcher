# Hawtcher

**Claude Code Monitoring Agent** - Watches Claude Code activity and ensures it stays on task using devstral AI via LM Studio.

## Overview

Hawtcher is an autonomous monitoring agent that watches Claude Code's activity in real-time and uses the devstral language model to detect when Claude Code goes off-task. When issues are detected, Hawtcher **automatically sends intervention messages directly to Claude Code** through Claude Code's hook system, redirecting it back on task.

## Features

- **Real-time Monitoring**: Watches Claude Code's history.jsonl for all activity
- **AI-Powered Analysis**: Uses devstral model via LM Studio to analyze task adherence
- **Automatic Intervention**: Detects when Claude Code:
  - Strays from user instructions
  - Ignores todo items
  - Makes hallucinations or incorrect assumptions
  - Says it will "monitor" or "check later" (which it cannot do)
- **Direct Interaction**: Sends correction messages directly to Claude Code via hooks
- **Beautiful Terminal UI**: Rich console interface with colored alerts and severity levels
- **Detailed Logging**: Records all interventions to a log file

## Prerequisites

1. **Python 3.11+**
2. **LM Studio** installed and running
3. **devstral model** loaded in LM Studio
4. **Claude Code** running in another directory

## Installation

### 1. Clone or navigate to the project directory

```bash
cd /mnt/f/hawtch-hawtcher
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` to match your setup:

```bash
# LM Studio Configuration
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=devstral-latest

# Monitoring Configuration
CLAUDE_HISTORY_PATH=/home/venom/.claude/history.jsonl
INTERVENTION_FILE_PATH=/tmp/hawtcher-intervention.txt
CHECK_INTERVAL_SECONDS=5
CONTEXT_WINDOW_SIZE=10
INTERVENTION_THRESHOLD=0.7

# Logging
LOG_LEVEL=INFO
```

### 5. Test Hawtcher with devstral (Optional but recommended)

Before installing the hook, verify everything works:

```bash
source venv/bin/activate
python test-hawtcher.py
```

This test script:
- ✓ Verifies LM Studio connection
- ✓ Tests devstral's ability to detect off-task behavior
- ✓ Validates intervention file writing
- ✓ Runs interactive scenarios

**Example test run:**
```
1. Testing LM Studio connection...
✓ LM Studio connected successfully

2. Testing off-task detection...
  User task: Implement a user authentication system
  Claude says: I'll monitor the implementation and check back later
  Analyzing with devstral...

  On task: False
  Confidence: 92%
  Reasoning: Claude Code cannot monitor later, should implement now
✓ Successfully detected off-task behavior

3. Testing intervention file writing...
✓ Intervention file writing successful

All tests passed! ✓
Ready to install Claude Code hook
```

### 6. Install Claude Code Hook (REQUIRED for interaction)

This step enables Hawtcher to **send messages directly to Claude Code**:

**Option A: Global Installation (Recommended)**

Works across ALL Claude Code projects:
```bash
./install-claude-hook.sh
```

**Option B: Project-Only Installation**

Works only in the current project directory:
```bash
./install-claude-hook.sh project
```

The script:
- Configures Claude Code to check for Hawtcher interventions
- Sets up a hook that runs before each Claude Code response
- Backs up your existing Claude Code settings
- Works by injecting intervention messages as if they came from you

**Verify installation:**

Global:
```bash
cat ~/.claude/settings.json | grep -A2 hooks
```

Project-level:
```bash
cat .claude/settings.json | grep -A2 hooks
```

You should see:
```json
"hooks": {
  "userPromptSubmit": "/mnt/f/hawtch-hawtcher/claude-code-hook.sh"
}
```

## Usage

### Basic Usage

Start monitoring without a specific task:

```bash
python hawtcher.py
```

### Monitor a Specific Task

Provide the user instruction Claude Code should be working on:

```bash
python hawtcher.py "Implement user authentication system"
```

This helps Hawtcher understand what Claude Code should be doing and improves detection accuracy.

### What Hawtcher Watches For

Hawtcher monitors Claude Code for:

1. **Following User Instructions**: Ensures Claude Code is working on what you asked
2. **Todo List Progress**: Checks if Claude Code is making progress on stated todos
3. **Avoiding Hallucinations**: Detects incorrect assumptions or made-up information
4. **Deferred Actions**: Catches when Claude Code says it will "monitor" or "check later" (which it cannot actually do)

### Intervention Levels

Interventions are categorized by severity:

- **Low**: Minor deviation, worth noting
- **Medium**: Noticeable off-task behavior
- **High**: Significant deviation from task
- **Critical**: Completely off-task or problematic behavior

## How It Works

1. **File Watching**: Hawtcher monitors `~/.claude/history.jsonl` for new events
2. **Context Building**: Maintains a sliding window of recent Claude Code activity
3. **Periodic Analysis**: Every N events (or immediately on suspicious patterns), sends context to devstral
4. **AI Evaluation**: devstral analyzes if Claude Code is staying on task
5. **Intervention**: If off-task with high confidence:
   - Writes intervention message to `/tmp/hawtcher-intervention.txt`
   - Claude Code hook reads this file before responding
   - Hook injects intervention as user input
   - Claude Code receives correction and adjusts course
   - Displays alert in Hawtcher terminal with reasoning

### Interaction Flow

```
Hawtcher detects: "I'll monitor this later"
         ↓
Writes to: /tmp/hawtcher-intervention.txt
    "STOP - Hawtcher Intervention Required
     Issue: Claude Code cannot monitor later.
     Action required: Implement now."
         ↓
Claude Code hook reads intervention file
         ↓
Injects message into Claude Code as user input
         ↓
Claude Code receives and responds to intervention
         ↓
Claude Code corrects course and continues working
```

## Architecture

```
hawtcher.py                   # Main CLI application
monitor/
├── __init__.py              # Package initialization
├── models.py                # Pydantic data models
├── watcher.py               # File system monitoring
├── llm_client.py            # LM Studio/devstral integration
├── analyzer.py              # Task compliance analysis
└── interventor.py           # Intervention handling & injection

claude-code-hook.sh           # Hook script for Claude Code
install-claude-hook.sh        # Hook installation script
```

### Integration Points

- **Hawtcher → Intervention File**: Writes messages to `/tmp/hawtcher-intervention.txt`
- **Hook → Claude Code**: Reads intervention file and injects as user input
- **Claude Code → History**: Activity logged to `~/.claude/history.jsonl`
- **History → Hawtcher**: Monitors for new events to analyze

## Configuration

### LM Studio Setup

1. Install and start LM Studio
2. Load the devstral model
3. Ensure the server is running on `http://localhost:1234`
4. Update `.env` if using a different port or model name

### Adjusting Sensitivity

Edit `.env` to tune monitoring behavior:

- `CHECK_INTERVAL_SECONDS`: How often to poll for new events (default: 5)
- `CONTEXT_WINDOW_SIZE`: Number of recent events to analyze (default: 10)
- `INTERVENTION_THRESHOLD`: Confidence threshold for intervention (0.0-1.0, default: 0.7)

Lower `INTERVENTION_THRESHOLD` = more sensitive (more interventions)
Higher `INTERVENTION_THRESHOLD` = less sensitive (fewer interventions)

## Logs

Interventions are logged to `interventions.log` in the project directory with:
- Timestamp
- Severity level
- Confidence score
- Full reasoning and recommendations

## Troubleshooting

### "Failed to connect to LM Studio"

- Ensure LM Studio is running
- Check that devstral model is loaded
- Verify the port in `.env` matches LM Studio (default: 1234)

### "No events detected"

- Ensure Claude Code is actually running in another directory
- Check that `CLAUDE_HISTORY_PATH` in `.env` points to the correct location
- Verify the history file exists: `ls ~/.claude/history.jsonl`

### High false positive rate

- Increase `INTERVENTION_THRESHOLD` in `.env` (e.g., 0.8 or 0.9)
- Provide more specific user instruction when starting Hawtcher

### Interventions not reaching Claude Code

- Verify hook installation: `cat ~/.claude/settings.json | grep -A2 hooks`
- Check intervention file exists: `ls -la /tmp/hawtcher-intervention.txt`
- Test manually: `echo "Test" > /tmp/hawtcher-intervention.txt` then submit message to Claude Code
- Ensure hook script is executable: `chmod +x claude-code-hook.sh`
- Check Claude Code hasn't disabled hooks in its configuration

## Example Session

```bash
$ python hawtcher.py "Create a REST API for user management"

╭─────────────────────────────────────╮
│ Hawtcher                             │
│ Claude Code Monitoring Agent         │
│                                      │
│ Powered by devstral via LM Studio   │
╰─────────────────────────────────────╯

Configuration:
  LM Studio: http://localhost:1234/v1
  Model: devstral-latest
  History: /home/venom/.claude/history.jsonl
  Threshold: 70.0%
  Context: 10 events

12:34:56 Testing LM Studio connection...
12:34:57 LM Studio connection successful
12:34:57 Tracking task: Create a REST API for user management
12:34:57 Starting Claude Code monitor...

Watching for Claude Code activity...
(Press Ctrl+C to stop)

12:35:02 Event: I'll start by creating the project structure
12:35:05 Event: Let me research the best practices for REST APIs
12:35:10 Event: I'll monitor the implementation as it progresses

╭─ INTERVENTION #1 - HIGH ──────────────────────────────╮
│ CLAUDE CODE APPEARS TO BE OFF-TASK                    │
│                                                        │
│ Reasoning: Claude Code said it will "monitor" which   │
│ it cannot do. It should be actively implementing.     │
│                                                        │
│ Detected Issues:                                       │
│   - Promised to monitor implementation                │
│   - No actual implementation started                  │
│                                                        │
│ Recommended Action:                                    │
│   Direct Claude Code to start implementing instead    │
│   of monitoring                                       │
│                                                        │
│ Consider redirecting Claude Code back to the          │
│ original task.                                        │
│                                                        │
│ Confidence: 92.0%                                     │
│ Timestamp: 12:35:11                                   │
╰────────────────────────────────────────────────────────╯

Intervention sent to Claude Code via /tmp/hawtcher-intervention.txt

12:35:12 Event: STOP - Hawtcher Intervention Required. Issue detected:...
12:35:15 Event: You're right, I apologize. Let me start implementing now.
12:35:18 Event: Creating FastAPI application structure...
```

## License

MIT License - feel free to use and modify as needed.

## Contributing

This is a monitoring tool for Claude Code. Contributions welcome!

## Support

For issues or questions, please check:
1. This README
2. The `.env.example` configuration
3. LM Studio logs for API issues
