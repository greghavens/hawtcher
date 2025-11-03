#!/usr/bin/env python3
"""
Hawtcher - Claude Code Monitoring Agent

Watches Claude Code activity and ensures it stays on task using devstral AI.
"""

import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from monitor.analyzer import TaskAnalyzer
from monitor.interventor import Interventor
from monitor.llm_client import DevstralClient
from monitor.models import ClaudeHistoryEvent, InterventionDecision, AnalysisResult
from monitor.watcher import HistoryMonitor
from monitor.question_detector import QuestionDetector
from monitor.question_answerer import QuestionAnswerer, AnswerAttempt
from monitor.telegram_relay import TelegramRelay


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_model: str = "devstral-latest"
    claude_history_path: str = "/home/venom/.claude/history.jsonl"
    intervention_file_path: str = "/tmp/hawtcher-intervention.txt"
    check_interval_seconds: int = 5
    context_window_size: int = 10
    intervention_threshold: float = 0.7
    log_level: str = "INFO"

    # Telegram settings
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    enable_telegram_relay: bool = False
    question_confidence_threshold: float = 0.95
    telegram_response_timeout: int = 300

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class HawtcherApp:
    """Main application for monitoring Claude Code."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.console = Console()
        self.running = False

        # Initialize components
        self.llm_client = DevstralClient(
            base_url=settings.lm_studio_base_url,
            model=settings.lm_studio_model,
        )

        self.interventor = Interventor(
            console=self.console,
            intervention_file=Path(settings.intervention_file_path),
            log_path=Path("interventions.log"),
        )

        # Initialize question handling components
        self.question_detector = QuestionDetector()
        self.question_answerer = QuestionAnswerer(
            llm_client=self.llm_client,
            confidence_threshold=settings.question_confidence_threshold,
        )

        # Initialize Telegram relay if enabled
        self.telegram_relay: Optional[TelegramRelay] = None
        if settings.enable_telegram_relay and settings.telegram_bot_token:
            self.telegram_relay = TelegramRelay(
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id if settings.telegram_chat_id else None,
                response_timeout=settings.telegram_response_timeout,
            )
            self.telegram_relay.on_chat_id_detected = self._save_chat_id

        self.analyzer = TaskAnalyzer(
            llm_client=self.llm_client,
            context_window_size=settings.context_window_size,
            intervention_threshold=settings.intervention_threshold,
            on_intervention=self._handle_intervention,
            question_detector=self.question_detector,
            question_answerer=self.question_answerer,
            on_question=self._handle_question,
        )

        self.monitor: Optional[HistoryMonitor] = None

    def _handle_intervention(self, decision: InterventionDecision) -> None:
        """Handle intervention decisions from analyzer."""
        self.interventor.intervene(decision)

    def _handle_event(self, event: ClaudeHistoryEvent) -> None:
        """Handle new Claude Code events."""
        self.interventor.display_event(event.display)
        self.analyzer.process_event(event)

    def _handle_question(self, question: str, answer_attempt: AnswerAttempt) -> Optional[str]:
        """
        Handle a question from Claude Code.

        Args:
            question: The question Claude Code is asking
            answer_attempt: devstral's attempt to answer

        Returns:
            The answer to send to Claude Code
        """
        self.console.print()
        self.console.print(f"[bold yellow]📨 Claude Code Question Detected[/bold yellow]")
        self.console.print(f"[cyan]Q: {question}[/cyan]")
        self.console.print()

        # Display devstral's attempt
        if answer_attempt.answer:
            self.console.print(f"[dim]devstral's answer ({answer_attempt.confidence:.1%} confident):[/dim]")
            self.console.print(f"[dim]  {answer_attempt.answer}[/dim]")
            self.console.print(f"[dim]  Reasoning: {answer_attempt.reasoning}[/dim]")
            self.console.print()

        # Decide whether to use devstral's answer or ask user
        if answer_attempt.should_ask_user:
            self.console.print(f"[yellow]⚠ Confidence below threshold ({self.settings.question_confidence_threshold:.1%})[/yellow]")

            # Try Telegram if enabled
            if self.telegram_relay:
                self.console.print("[cyan]Forwarding question to Telegram...[/cyan]")
                user_answer = self.telegram_relay.ask_question(
                    question=question,
                    task_description=self.analyzer.user_instruction or "Unknown task",
                    devstral_suggestion=answer_attempt.answer if answer_attempt.answer else None,
                    devstral_confidence=answer_attempt.confidence if answer_attempt.answer else None,
                )

                if user_answer:
                    self.console.print(f"[green]✅ Answer received from Telegram: {user_answer}[/green]")
                    answer = user_answer
                else:
                    self.console.print("[yellow]No response from Telegram, using devstral's answer[/yellow]")
                    answer = answer_attempt.answer or "Please clarify your question."
            else:
                # No Telegram, use devstral's best guess
                self.console.print("[yellow]No Telegram relay configured, using devstral's answer[/yellow]")
                answer = answer_attempt.answer or "Please clarify your question."
        else:
            # High confidence, use devstral's answer
            self.console.print(f"[green]✅ Using devstral's answer (high confidence)[/green]")
            answer = answer_attempt.answer

        # Send answer to Claude Code via intervention file
        self.interventor._write_intervention_file(
            InterventionDecision(
                should_intervene=True,
                severity="low",
                intervention_message=f"Answer to your question:\n{answer}",
                analysis=AnalysisResult(
                    is_on_task=True,
                    confidence=1.0,
                    reasoning="Answering Claude Code's question",
                    detected_issues=[],
                ),
            )
        )

        self.console.print(f"[bold green]Answer sent to Claude Code[/bold green]")
        self.console.print()

        return answer

    def _save_chat_id(self, chat_id: str) -> None:
        """Save detected chat ID to .env file."""
        self.console.print(f"[green]Telegram chat ID detected: {chat_id}[/green]")
        self.console.print("[yellow]Add this to your .env file: TELEGRAM_CHAT_ID={chat_id}[/yellow]")

    def _display_banner(self) -> None:
        """Display startup banner."""
        banner = Text()
        banner.append("Hawtcher", style="bold green")
        banner.append("\n")
        banner.append("Claude Code Monitoring Agent", style="dim")
        banner.append("\n\n")
        banner.append("Powered by ", style="dim")
        banner.append("devstral", style="bold cyan")
        banner.append(" via LM Studio", style="dim")

        panel = Panel(
            banner,
            border_style="green",
            expand=False,
        )

        self.console.clear()
        self.console.print()
        self.console.print(panel)
        self.console.print()

    def _display_config(self) -> None:
        """Display current configuration."""
        config_lines = [
            f"LM Studio: {self.settings.lm_studio_base_url}",
            f"Model: {self.settings.lm_studio_model}",
            f"History: {self.settings.claude_history_path}",
            f"Threshold: {self.settings.intervention_threshold:.1%}",
            f"Context: {self.settings.context_window_size} events",
        ]

        self.console.print("[bold]Configuration:[/bold]")
        for line in config_lines:
            self.console.print(f"  [dim]{line}[/dim]")
        self.console.print()

    def _test_lm_studio_connection(self) -> bool:
        """Test connection to LM Studio."""
        try:
            self.interventor.display_status("Testing LM Studio connection...", "yellow")

            # Simple test prompt
            from monitor.models import TaskContext

            test_context = TaskContext(
                user_instruction="Test connection",
                recent_events=[],
            )

            result = self.llm_client.analyze_task_adherence(
                test_context,
                "Testing connection",
            )

            if result.confidence >= 0:  # If we got any response
                self.interventor.display_status(
                    "LM Studio connection successful", "green"
                )
                return True
            else:
                self.interventor.display_status(
                    "LM Studio connection failed", "red"
                )
                return False

        except Exception as e:
            self.interventor.display_status(
                f"LM Studio connection error: {e}", "red"
            )
            return False

    def start(self, user_instruction: Optional[str] = None) -> None:
        """
        Start monitoring Claude Code.

        Args:
            user_instruction: Optional initial user instruction
        """
        self._display_banner()
        self._display_config()

        # Test LM Studio connection
        if not self._test_lm_studio_connection():
            self.console.print()
            self.console.print(
                "[red]Failed to connect to LM Studio. "
                "Please ensure LM Studio is running and the devstral model is loaded.[/red]"
            )
            self.console.print()
            self.console.print(
                "[yellow]Tip: Start LM Studio and load the devstral model, "
                "then try again.[/yellow]"
            )
            return

        # Start Telegram bot if enabled
        if self.telegram_relay:
            self.interventor.display_status("Starting Telegram relay...", "green")
            self.telegram_relay.start()
            if not self.settings.telegram_chat_id:
                self.console.print()
                self.console.print("[yellow]Note: Send /start to your bot to link your Telegram account[/yellow]")
                self.console.print()

        # Set user instruction if provided
        if user_instruction:
            self.analyzer.set_user_instruction(user_instruction)
            self.interventor.display_status(
                f"Tracking task: {user_instruction}", "green"
            )

        # Start monitoring
        self.interventor.display_status("Starting Claude Code monitor...", "green")
        self.console.print()
        self.console.print("[bold]Watching for Claude Code activity...[/bold]")
        self.console.print("[dim](Press Ctrl+C to stop)[/dim]")
        self.console.print()

        self.running = True
        self.monitor = HistoryMonitor(
            history_path=self.settings.claude_history_path,
            on_new_event=self._handle_event,
            poll_interval=self.settings.check_interval_seconds,
        )

        try:
            # Use polling mode for better compatibility
            self.monitor.start(use_polling=True)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Stop monitoring."""
        self.console.print()
        self.interventor.display_status("Stopping monitor...", "yellow")

        if self.monitor:
            self.monitor.stop()

        if self.telegram_relay:
            self.telegram_relay.stop()

        self.console.print()
        self.console.print(
            f"[green]Session complete. "
            f"{self.interventor.intervention_count} interventions triggered.[/green]"
        )
        self.console.print()


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()

    # Load settings
    settings = Settings()

    # Create and start app
    app = HawtcherApp(settings)

    # Check for user instruction in command line
    user_instruction = None
    if len(sys.argv) > 1:
        user_instruction = " ".join(sys.argv[1:])

    app.start(user_instruction)


if __name__ == "__main__":
    main()
