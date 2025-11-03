# Hawtcher Quick Start Guide

Get up and running with Hawtcher in 5 minutes.

## Prerequisites

- LM Studio installed with devstral model loaded
- Claude Code running (in any directory)
- Python 3.11+

## Installation (5 steps)

### 1. Setup Hawtcher

```bash
cd /mnt/f/hawtch-hawtcher
./setup.sh
```

### 2. Configure Environment

```bash
# Edit .env if needed (defaults should work)
nano .env
```

### 3. Start LM Studio

- Launch LM Studio
- Load devstral model
- Ensure server running on port 1234

### 4. Test First (Recommended)

Verify devstral integration before installing hook:

```bash
source venv/bin/activate
python test-hawtcher.py
```

This tests:
- LM Studio connection
- Off-task detection
- Intervention file writing

### 5. Install Claude Code Hook (CRITICAL!)

This enables Hawtcher to send messages TO Claude Code:

```bash
./install-claude-hook.sh
```

Verify:
```bash
cat ~/.claude/settings.json | grep -A2 hooks
```

### 6. Run Hawtcher

```bash
source venv/bin/activate
python hawtcher.py "Your task description"
```

## How It Works

1. **You give Claude Code a task** in another terminal
2. **Hawtcher watches** Claude Code's activity via `~/.claude/history.jsonl`
3. **If Claude Code goes off-task**, Hawtcher sends intervention
4. **Claude Code receives** intervention via hook as if you sent it
5. **Claude Code corrects** and continues working

## Key Points

- Hawtcher runs **separately** from Claude Code
- Uses **hooks** to inject messages into Claude Code
- Hook file: `/tmp/hawtcher-intervention.txt`
- Monitors: `~/.claude/history.jsonl`

## Test It

Try having Claude Code say "I'll monitor this later" and watch Hawtcher intervene!

## Troubleshooting

**Not intervening?**
- Check LM Studio is running
- Lower `INTERVENTION_THRESHOLD` in .env to 0.5

**Interventions not reaching Claude Code?**
```bash
# Verify hook
cat ~/.claude/settings.json | grep hooks

# Test manually
echo "Test intervention" > /tmp/hawtcher-intervention.txt
# Then send any message to Claude Code
```

**No events showing?**
- Ensure Claude Code is actually running
- Check history path: `ls ~/.claude/history.jsonl`

## Files Overview

```
hawtcher.py              - Main app (run this)
claude-code-hook.sh      - Hook that injects interventions
install-claude-hook.sh   - Installs the hook
.env                     - Configuration
```

## Support

See README.md for full documentation.
