#!/bin/bash
# Claude Code Hook for Hawtcher Integration
# This hook checks for interventions from Hawtcher and injects them as user messages

INTERVENTION_FILE="${HAWTCHER_INTERVENTION_FILE:-/tmp/hawtcher-intervention.txt}"

# Check if intervention file exists and has content
if [ -f "$INTERVENTION_FILE" ] && [ -s "$INTERVENTION_FILE" ]; then
    # Read the intervention message
    INTERVENTION_MESSAGE=$(cat "$INTERVENTION_FILE")

    # Clear the file immediately to prevent re-processing
    > "$INTERVENTION_FILE"

    # Output the intervention message
    # Claude Code will receive this as if it came from the user
    echo "$INTERVENTION_MESSAGE"

    exit 0
fi

# No intervention needed
exit 0
