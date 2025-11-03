# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hawtcher is an autonomous monitoring agent that watches Claude Code's activity in real-time and uses the devstral AI model (via LM Studio) to detect when Claude Code goes off-task. When issues are detected, Hawtcher automatically sends intervention messages directly back to Claude Code through Claude Code's hook system.

**Key Concept**: This is a meta-monitoring system - it watches OTHER instances of Claude Code and intervenes when they stray from their tasks.

## Development Commands

### Setup
```bash
./setup.sh                    # One-time setup: creates venv, installs deps, creates .env
source venv/bin/activate      # Activate virtual environment
```

### Testing
```bash
python test-hawtcher.py       # Run full test suite (LM Studio connection, detection, file I/O)
```

The test suite validates:
1. LM Studio connectivity and devstral model availability
2. Off-task detection accuracy (tests suspicious patterns like "I'll monitor later")
3. Intervention file writing/reading (IPC mechanism)
4. Interactive scenario testing

### Running
```bash
python hawtcher.py                              # Monitor without specific task context
python hawtcher.py "Implement user auth API"    # Monitor with task context (better detection)
```

### Hook Installation
```bash
./install-claude-hook.sh          # Global installation (~/.claude/settings.json)
./install-claude-hook.sh project  # Project-specific installation (./.claude/settings.json)
```

## Architecture

### Communication Flow
The system uses a file-based IPC mechanism to bridge two separate processes:

```
Claude Code → ~/.claude/history.jsonl → Hawtcher (monitors)
                                            ↓ (analyzes via devstral)
                                            ↓ (detects off-task)
                                            ↓
                            /tmp/hawtcher-intervention.txt
                                            ↓
                      claude-code-hook.sh (reads file)
                                            ↓
                      Claude Code ← (receives as user input)
```

**Critical Design**: The intervention file acts as a message queue. The hook script atomically reads and clears it to prevent duplicate interventions.

### Core Components

**monitor/models.py** - Type-safe data models using Pydantic:
- `ClaudeHistoryEvent`: Parses JSONL entries from history.jsonl (note: timestamp is Unix milliseconds)
- `TaskContext`: Bundles user instruction, recent events, and todo state for analysis
- `AnalysisResult`: Structured output from devstral (confidence, reasoning, issues, action)
- `InterventionDecision`: Combines analysis with severity level for intervention logic

**monitor/watcher.py** - File monitoring with dual modes:
- Observer mode (default): Uses watchdog for filesystem events
- Polling mode: Fallback for filesystems without inotify support
- Maintains file position cursor to only process new JSONL entries

**monitor/llm_client.py** - LM Studio integration:
- Uses OpenAI-compatible API (LM Studio mimics OpenAI endpoint)
- Builds system prompt that instructs devstral to detect: hallucinations, deferred actions ("I'll monitor"), deviation from user instructions
- Expects JSON response: `{is_on_task, confidence, reasoning, detected_issues, recommended_action}`
- Handles non-JSON responses gracefully (strips markdown code blocks)

**monitor/analyzer.py** - Decision engine:
- Maintains sliding window of recent events (deque with maxlen)
- Triggers analysis every N events OR immediately on suspicious patterns
- Suspicious patterns: "monitor", "check later", "watch", "track" (phrases Claude Code cannot actually perform)
- Intervention threshold: Only triggers if confidence >= threshold (default 0.7)
- Severity mapping: confidence 0.9+ = critical, 0.8+ = high, 0.7+ = medium

**monitor/interventor.py** - Intervention execution:
- Writes intervention messages to shared file using atomic write (temp file + rename)
- Formats messages for Claude Code consumption (directive, not explanatory)
- Rich console UI with severity-based coloring and terminal bell for high/critical
- Dual output: screen display (for user) + intervention file (for Claude Code)

### Hook Integration

**claude-code-hook.sh** - Bash script executed by Claude Code:
- Configured via `~/.claude/settings.json`: `"hooks": {"userPromptSubmit": "/path/to/claude-code-hook.sh"}`
- Runs BEFORE Claude Code processes each user prompt
- Checks for intervention file, reads content, clears file, outputs message (which Claude Code receives as user input)
- Must be idempotent and fast (runs on every prompt submission)

**install-claude-hook.sh** - Installation automation:
- Uses `jq` for JSON manipulation (falls back to manual instructions)
- Creates backup of existing settings before modification
- Supports both global and project-level installation

## Configuration

Environment variables in `.env`:
- `LM_STUDIO_BASE_URL`: OpenAI-compatible endpoint (default: http://localhost:1234/v1)
- `LM_STUDIO_MODEL`: Model identifier for devstral
- `CLAUDE_HISTORY_PATH`: Location of Claude Code's activity log (default: ~/.claude/history.jsonl)
- `INTERVENTION_FILE_PATH`: Shared file for IPC (default: /tmp/hawtcher-intervention.txt)
- `CONTEXT_WINDOW_SIZE`: How many recent events to analyze (default: 10)
- `INTERVENTION_THRESHOLD`: Confidence threshold for triggering intervention (0.0-1.0, default: 0.7)
- `CHECK_INTERVAL_SECONDS`: Polling frequency in polling mode (default: 5)

## Development Notes

### Adding New Detection Patterns
Edit `monitor/analyzer.py::_is_suspicious_activity()` to add patterns that should trigger immediate analysis.

### Adjusting LLM Prompts
The system prompt in `monitor/llm_client.py::_build_system_prompt()` controls how devstral evaluates Claude Code's behavior. Key aspects:
- Define what "on-task" means
- List specific anti-patterns to detect
- Specify JSON output format (must be parseable)

### Testing Interventions
Use the test script's interactive mode to simulate scenarios:
```bash
python test-hawtcher.py
# Select option 4 for full scenario test
# Input custom task and Claude Code responses
```

### Prerequisites for Development
1. Python 3.11+ (uses modern type hints: `list[str]` instead of `List[str]`)
2. LM Studio running locally with devstral model loaded
3. Access to Claude Code's history file (requires Claude Code to be installed)

## Known Limitations

- Intervention file is world-writable in `/tmp` (acceptable for single-user systems)
- No detection of Claude Code actually responding to interventions (no feedback loop)
- Analysis is reactive (every N events) not proactive
- Devstral model quality directly impacts detection accuracy
- Hook only triggers on user prompt submissions, not on Claude Code's autonomous actions
