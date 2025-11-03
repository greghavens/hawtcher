"""
Analyzer that maintains context and triggers analysis.
"""

from collections import deque
from typing import Callable, Optional

from monitor.models import (
    AnalysisResult,
    ClaudeHistoryEvent,
    InterventionDecision,
    TaskContext,
)
from monitor.llm_client import DevstralClient


class TaskAnalyzer:
    """
    Analyzes Claude Code activity to ensure task adherence.
    """

    def __init__(
        self,
        llm_client: DevstralClient,
        context_window_size: int,
        intervention_threshold: float,
        on_intervention: Optional[Callable[[InterventionDecision], None]] = None,
    ):
        self.llm_client = llm_client
        self.context_window_size = context_window_size
        self.intervention_threshold = intervention_threshold
        self.on_intervention = on_intervention

        self.user_instruction: Optional[str] = None
        self.current_todos: list[str] = []
        self.completed_todos: list[str] = []
        self.recent_events: deque[ClaudeHistoryEvent] = deque(
            maxlen=context_window_size
        )
        self.event_count = 0
        self.check_frequency = 3  # Check every N events

    def set_user_instruction(self, instruction: str) -> None:
        """Set the current user instruction being worked on."""
        self.user_instruction = instruction
        self.current_todos = []
        self.completed_todos = []

    def update_todos(
        self,
        current: Optional[list[str]] = None,
        completed: Optional[list[str]] = None,
    ) -> None:
        """Update the todo lists."""
        if current is not None:
            self.current_todos = current
        if completed is not None:
            self.completed_todos = completed

    def process_event(self, event: ClaudeHistoryEvent) -> None:
        """
        Process a new Claude Code event.

        Args:
            event: New event from history.jsonl
        """
        self.recent_events.append(event)
        self.event_count += 1

        # Auto-detect user instructions from events
        if not self.user_instruction:
            self.user_instruction = event.display

        # Check for suspicious patterns immediately
        if self._is_suspicious_activity(event.display):
            self._trigger_analysis(event.display, force=True)
        # Otherwise check periodically
        elif self.event_count % self.check_frequency == 0:
            self._trigger_analysis(event.display)

    def _is_suspicious_activity(self, activity: str) -> bool:
        """
        Detect patterns that warrant immediate analysis.

        Args:
            activity: The current activity text

        Returns:
            True if activity looks suspicious
        """
        suspicious_patterns = [
            "i'll monitor",
            "i will monitor",
            "i'll check",
            "i will check",
            "later on",
            "in the future",
            "i'll watch",
            "i will watch",
            "i'll track",
            "i will track",
            "continuously",
            "ongoing",
        ]

        activity_lower = activity.lower()
        return any(pattern in activity_lower for pattern in suspicious_patterns)

    def _trigger_analysis(self, current_activity: str, force: bool = False) -> None:
        """
        Trigger analysis of current state.

        Args:
            current_activity: Most recent activity
            force: Force analysis even if threshold not met
        """
        if not self.user_instruction:
            return

        context = TaskContext(
            user_instruction=self.user_instruction,
            recent_events=list(self.recent_events),
            current_todos=self.current_todos,
            completed_todos=self.completed_todos,
        )

        analysis = self.llm_client.analyze_task_adherence(context, current_activity)

        # Determine if intervention is needed
        should_intervene = (
            not analysis.is_on_task
            and analysis.confidence >= self.intervention_threshold
        ) or force

        if should_intervene:
            severity = self._determine_severity(analysis)
            intervention = InterventionDecision(
                should_intervene=True,
                severity=severity,
                intervention_message=self._build_intervention_message(analysis),
                analysis=analysis,
            )

            if self.on_intervention:
                self.on_intervention(intervention)

    def _determine_severity(self, analysis: AnalysisResult) -> str:
        """Determine intervention severity based on analysis."""
        if analysis.confidence >= 0.9:
            return "critical"
        elif analysis.confidence >= 0.8:
            return "high"
        elif analysis.confidence >= 0.7:
            return "medium"
        else:
            return "low"

    def _build_intervention_message(self, analysis: AnalysisResult) -> str:
        """Build a user-friendly intervention message."""
        message_parts = [
            "CLAUDE CODE APPEARS TO BE OFF-TASK",
            "",
            f"Reasoning: {analysis.reasoning}",
            "",
        ]

        if analysis.detected_issues:
            message_parts.append("Detected Issues:")
            for issue in analysis.detected_issues:
                message_parts.append(f"  - {issue}")
            message_parts.append("")

        if analysis.recommended_action:
            message_parts.append("Recommended Action:")
            message_parts.append(f"  {analysis.recommended_action}")
            message_parts.append("")

        message_parts.append(
            "Consider redirecting Claude Code back to the original task."
        )

        return "\n".join(message_parts)
