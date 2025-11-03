#!/bin/bash
# Installation script for Claude Code hook integration
# This configures Claude Code to receive interventions from Hawtcher

set -e

echo "Hawtcher - Claude Code Hook Installation"
echo "=========================================="
echo ""

# Get the absolute path to this script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SCRIPT="$SCRIPT_DIR/claude-code-hook.sh"
INTERVENTION_FILE="${HAWTCHER_INTERVENTION_FILE:-/tmp/hawtcher-intervention.txt}"

# Determine installation scope
if [ "$1" == "project" ]; then
    CLAUDE_SETTINGS="./.claude/settings.json"
    echo "Installing hook for CURRENT PROJECT only"
    echo "Settings: $CLAUDE_SETTINGS"
else
    CLAUDE_SETTINGS="$HOME/.claude/settings.json"
    echo "Installing hook GLOBALLY (all projects)"
    echo "Settings: $CLAUDE_SETTINGS"
    echo ""
    echo "Tip: Use './install-claude-hook.sh project' to install per-project"
fi
echo ""

# Check if hook script exists
if [ ! -f "$HOOK_SCRIPT" ]; then
    echo "Error: Hook script not found at $HOOK_SCRIPT"
    exit 1
fi

# Make hook script executable
chmod +x "$HOOK_SCRIPT"
echo "Hook script ready: $HOOK_SCRIPT"

# Check if Claude Code settings file exists
if [ ! -f "$CLAUDE_SETTINGS" ]; then
    echo "Warning: Claude Code settings file not found at $CLAUDE_SETTINGS"
    echo "Creating default settings file..."
    mkdir -p "$(dirname "$CLAUDE_SETTINGS")"
    echo '{}' > "$CLAUDE_SETTINGS"

    if [ "$1" == "project" ]; then
        echo "Note: Created project-level .claude directory"
    fi
fi

# Backup existing settings
BACKUP_FILE="${CLAUDE_SETTINGS}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$CLAUDE_SETTINGS" "$BACKUP_FILE"
echo "Backed up existing settings to: $BACKUP_FILE"

# Check if jq is available for JSON manipulation
if command -v jq &> /dev/null; then
    echo "Using jq to update settings..."

    # Add or update the hook in settings.json
    jq --arg hook_path "$HOOK_SCRIPT" \
       '.hooks.userPromptSubmit = $hook_path' \
       "$CLAUDE_SETTINGS" > "${CLAUDE_SETTINGS}.tmp" && \
       mv "${CLAUDE_SETTINGS}.tmp" "$CLAUDE_SETTINGS"

    echo "Hook installed successfully!"
else
    echo ""
    echo "Note: jq not found. Manual configuration required."
    echo ""
    echo "Please add the following to your Claude Code settings file:"
    echo "$CLAUDE_SETTINGS"
    echo ""
    echo "{"
    echo "  \"hooks\": {"
    echo "    \"userPromptSubmit\": \"$HOOK_SCRIPT\""
    echo "  }"
    echo "}"
    echo ""
fi

echo ""
echo "=========================================="
echo "Installation Complete!"
echo ""
echo "Configuration:"
echo "  Hook script: $HOOK_SCRIPT"
echo "  Intervention file: $INTERVENTION_FILE"
echo "  Settings file: $CLAUDE_SETTINGS"
echo ""
echo "How it works:"
echo "  1. Hawtcher detects off-task behavior"
echo "  2. Writes intervention to: $INTERVENTION_FILE"
echo "  3. Claude Code hook reads and injects as user message"
echo "  4. Claude Code receives correction and adjusts"
echo ""
echo "To verify installation:"
echo "  cat $CLAUDE_SETTINGS | grep -A2 hooks"
echo ""
echo "To test the hook:"
echo "  echo 'Test intervention' > $INTERVENTION_FILE"
echo "  # Then submit a message to Claude Code"
echo ""
