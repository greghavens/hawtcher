"""
LM Studio client for devstral model integration.
"""

from typing import Optional
from openai import OpenAI

from monitor.models import AnalysisResult, TaskContext


class DevstralClient:
    """Client for communicating with devstral model via LM Studio."""

    def __init__(self, base_url: str, model: str):
        self.client = OpenAI(
            base_url=base_url,
            api_key="not-needed",  # LM Studio doesn't require API key
        )
        self.model = model

    def analyze_task_adherence(
        self,
        context: TaskContext,
        current_activity: str,
    ) -> AnalysisResult:
        """
        Analyze whether Claude Code is staying on task.

        Args:
            context: Current task context with user instructions and history
            current_activity: Most recent Claude Code activity

        Returns:
            AnalysisResult with determination and reasoning
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_analysis_prompt(context, current_activity)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            content = response.choices[0].message.content
            return self._parse_analysis_response(content)

        except Exception as e:
            print(f"Error calling LM Studio: {e}")
            return AnalysisResult(
                is_on_task=True,  # Default to no intervention on error
                confidence=0.0,
                reasoning=f"Analysis failed: {str(e)}",
                detected_issues=[],
            )

    def _build_system_prompt(self) -> str:
        """Build the system prompt for devstral."""
        return """You are a monitoring agent that watches Claude Code (an AI coding assistant) to ensure it stays on task.

Your job is to analyze Claude Code's recent activity and determine if it is:
1. Following the user's instructions
2. Making progress on stated todo items
3. Avoiding hallucinations or incorrect assumptions
4. Actually executing tasks rather than just saying it will "monitor" or "check later" (which it cannot do)

Respond in the following JSON format:
{
  "is_on_task": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of your determination",
  "detected_issues": ["list", "of", "specific", "problems"],
  "recommended_action": "What should be done if off-task (null if on-task)"
}

Be strict but fair. Claude Code should be actively working on the user's request."""

    def _build_analysis_prompt(
        self,
        context: TaskContext,
        current_activity: str,
    ) -> str:
        """Build the analysis prompt with context."""
        recent_history = "\n".join(
            f"- [{event.timestamp}] {event.display[:100]}"
            for event in context.recent_events[-5:]
        )

        todos_section = ""
        if context.current_todos:
            todos_section = f"\n\nCurrent TODOs:\n" + "\n".join(
                f"- {todo}" for todo in context.current_todos
            )

        completed_section = ""
        if context.completed_todos:
            completed_section = f"\n\nCompleted TODOs:\n" + "\n".join(
                f"- {todo}" for todo in context.completed_todos
            )

        return f"""Analyze Claude Code's activity:

USER INSTRUCTION:
{context.user_instruction}
{todos_section}
{completed_section}

RECENT ACTIVITY:
{recent_history}

CURRENT ACTIVITY:
{current_activity}

Is Claude Code staying on task? Respond in JSON format as specified."""

    def _parse_analysis_response(self, content: str) -> AnalysisResult:
        """Parse the JSON response from devstral."""
        import json

        try:
            # Try to extract JSON from response
            content = content.strip()
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0]
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            return AnalysisResult(**data)

        except Exception as e:
            print(f"Error parsing response: {e}")
            print(f"Response was: {content}")
            # Return a safe default
            return AnalysisResult(
                is_on_task=True,
                confidence=0.0,
                reasoning=f"Failed to parse response: {str(e)}",
                detected_issues=[],
            )
