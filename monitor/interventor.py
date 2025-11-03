"""
Intervention system for alerting and correcting Claude Code behavior.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from monitor.models import InterventionDecision


class Interventor:
    """Handles interventions when Claude Code goes off-task."""

    def __init__(
        self,
        console: Console,
        intervention_file: Path,
        log_path: Optional[Path] = None,
    ):
        self.console = console
        self.intervention_file = intervention_file
        self.log_path = log_path
        self.intervention_count = 0

    def intervene(self, decision: InterventionDecision) -> None:
        """
        Execute an intervention.

        Args:
            decision: The intervention decision with details
        """
        self.intervention_count += 1

        # Write intervention for Claude Code to read
        self._write_intervention_file(decision)

        # Display to console
        self._display_intervention(decision)

        # Log to file if configured
        if self.log_path:
            self._log_intervention(decision)

    def _display_intervention(self, decision: InterventionDecision) -> None:
        """Display intervention in the terminal."""
        # Determine color based on severity
        severity_colors = {
            "low": "yellow",
            "medium": "orange1",
            "high": "red",
            "critical": "bright_red",
        }
        color = severity_colors.get(decision.severity, "yellow")

        # Create title with severity indicator
        title = Text()
        title.append("INTERVENTION #", style="bold")
        title.append(str(self.intervention_count), style="bold")
        title.append(" - ", style="bold")
        title.append(decision.severity.upper(), style=f"bold {color}")

        # Create panel content
        content = Text()
        content.append(decision.intervention_message)
        content.append("\n\n")
        content.append(f"Confidence: {decision.analysis.confidence:.1%}", style="dim")
        content.append("\n")
        content.append(
            f"Timestamp: {decision.timestamp.strftime('%H:%M:%S')}",
            style="dim",
        )

        # Display panel
        panel = Panel(
            content,
            title=title,
            border_style=color,
            expand=False,
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

        # Ring the terminal bell for high severity
        if decision.severity in ["high", "critical"]:
            self.console.bell()

    def _log_intervention(self, decision: InterventionDecision) -> None:
        """Log intervention to file."""
        if not self.log_path:
            return

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"INTERVENTION #{self.intervention_count}\n")
                f.write(f"Timestamp: {decision.timestamp}\n")
                f.write(f"Severity: {decision.severity}\n")
                f.write(f"Confidence: {decision.analysis.confidence:.1%}\n")
                f.write(f"\n{decision.intervention_message}\n")
                f.write(f"{'='*80}\n")
        except Exception as e:
            self.console.print(f"[red]Failed to log intervention: {e}[/red]")

    def _write_intervention_file(self, decision: InterventionDecision) -> None:
        """
        Write intervention to shared file for Claude Code hook to read.
        This is how we INTERACT with Claude Code - the hook will inject this as user input.
        """
        try:
            # Build a concise, directive message for Claude Code
            message_parts = [
                "STOP - Hawtcher Intervention Required",
                "",
                f"Issue detected: {decision.analysis.reasoning}",
                ""
            ]

            if decision.analysis.detected_issues:
                message_parts.append("Problems:")
                for issue in decision.analysis.detected_issues:
                    message_parts.append(f"- {issue}")
                message_parts.append("")

            if decision.analysis.recommended_action:
                message_parts.append(f"Action required: {decision.analysis.recommended_action}")
            else:
                message_parts.append("Action required: Return to the original task immediately.")

            message = "\n".join(message_parts)

            # Write to intervention file (atomic write)
            temp_file = self.intervention_file.with_suffix('.tmp')
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(message)

            # Atomic rename to avoid race conditions
            temp_file.replace(self.intervention_file)

            self.console.print(
                f"[bold green]Intervention sent to Claude Code via {self.intervention_file}[/bold green]"
            )

        except Exception as e:
            self.console.print(f"[red]Failed to write intervention file: {e}[/red]")

    def display_status(self, status: str, style: str = "green") -> None:
        """Display a status message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console.print(f"[dim]{timestamp}[/dim] [{style}]{status}[/{style}]")

    def display_event(self, event_text: str) -> None:
        """Display a Claude Code event."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        # Truncate long events
        display_text = event_text[:100] + "..." if len(event_text) > 100 else event_text
        self.console.print(f"[dim]{timestamp}[/dim] [cyan]Event:[/cyan] {display_text}")
