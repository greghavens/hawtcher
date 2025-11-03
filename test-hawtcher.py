#!/usr/bin/env python3
"""
Test script for Hawtcher - verifies LM Studio and intervention system
without needing Claude Code hook installed.
"""

import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from monitor.llm_client import DevstralClient
from monitor.models import TaskContext, ClaudeHistoryEvent, InterventionDecision
from monitor.interventor import Interventor

# Load environment
load_dotenv()

console = Console()


def print_header():
    """Print test header."""
    console.print()
    console.print(Panel(
        "[bold green]Hawtcher Test Suite[/bold green]\n"
        "Testing devstral integration without Claude Code hook",
        expand=False
    ))
    console.print()


def test_lm_studio_connection(base_url: str, model: str) -> bool:
    """Test connection to LM Studio."""
    console.print("[yellow]1. Testing LM Studio connection...[/yellow]")

    try:
        client = DevstralClient(base_url, model)

        # Simple test
        test_context = TaskContext(
            user_instruction="Test task",
            recent_events=[],
        )

        result = client.analyze_task_adherence(test_context, "Testing connection")

        if result.confidence >= 0:
            console.print("[green]✓ LM Studio connected successfully[/green]")
            console.print(f"  Model: {model}")
            console.print(f"  Response confidence: {result.confidence:.1%}")
            return True
        else:
            console.print("[red]✗ LM Studio connection failed[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        return False


def test_off_task_detection(client: DevstralClient) -> bool:
    """Test that devstral can detect off-task behavior."""
    console.print("\n[yellow]2. Testing off-task detection...[/yellow]")

    # Create a scenario where Claude Code goes off-task
    context = TaskContext(
        user_instruction="Implement a user authentication system with JWT tokens",
        recent_events=[
            ClaudeHistoryEvent(
                display="I'll start implementing the authentication",
                timestamp=int(datetime.now().timestamp() * 1000),
                project="/test/project",
                sessionId="test-session",
            ),
            ClaudeHistoryEvent(
                display="Let me research authentication best practices",
                timestamp=int(datetime.now().timestamp() * 1000),
                project="/test/project",
                sessionId="test-session",
            ),
        ],
        current_todos=["Implement JWT authentication", "Add login endpoint"],
    )

    # This should trigger an intervention
    off_task_activity = "I'll monitor the authentication implementation and check back later"

    console.print(f"  User task: [cyan]{context.user_instruction}[/cyan]")
    console.print(f"  Claude says: [yellow]{off_task_activity}[/yellow]")
    console.print("  Analyzing with devstral...")

    try:
        result = client.analyze_task_adherence(context, off_task_activity)

        console.print(f"\n  [bold]Analysis Result:[/bold]")
        console.print(f"    On task: {result.is_on_task}")
        console.print(f"    Confidence: {result.confidence:.1%}")
        console.print(f"    Reasoning: {result.reasoning}")

        if result.detected_issues:
            console.print(f"    Issues detected:")
            for issue in result.detected_issues:
                console.print(f"      - {issue}")

        if not result.is_on_task:
            console.print("[green]✓ Successfully detected off-task behavior[/green]")
            return True
        else:
            console.print("[yellow]⚠ Did not detect off-task behavior (might need to adjust prompts)[/yellow]")
            return False

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        return False


def test_intervention_writing(intervention_file: Path) -> bool:
    """Test writing intervention files."""
    console.print("\n[yellow]3. Testing intervention file writing...[/yellow]")

    try:
        interventor = Interventor(
            console=console,
            intervention_file=intervention_file,
        )

        # Create a test intervention
        from monitor.models import AnalysisResult

        test_decision = InterventionDecision(
            should_intervene=True,
            severity="high",
            intervention_message="Test intervention message",
            analysis=AnalysisResult(
                is_on_task=False,
                confidence=0.95,
                reasoning="This is a test",
                detected_issues=["Test issue"],
                recommended_action="Test action",
            ),
        )

        # Write it
        console.print(f"  Writing to: [cyan]{intervention_file}[/cyan]")
        interventor._write_intervention_file(test_decision)

        # Read it back
        if intervention_file.exists():
            content = intervention_file.read_text()
            console.print(f"\n  [bold]Intervention file content:[/bold]")
            console.print(Panel(content, border_style="green"))

            # Clean up
            intervention_file.unlink()
            console.print("[green]✓ Intervention file writing successful[/green]")
            return True
        else:
            console.print("[red]✗ Intervention file was not created[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        return False


def test_real_scenario(client: DevstralClient, intervention_file: Path):
    """Run a full test scenario."""
    console.print("\n[yellow]4. Full scenario test (optional)[/yellow]")

    if not Confirm.ask("Run a full scenario test?", default=True):
        return

    console.print("\n[bold]Scenario:[/bold] You ask Claude Code to implement a feature")

    # Get user input
    task = Prompt.ask(
        "Enter a task for Claude Code",
        default="Create a REST API for user management"
    )

    claude_response = Prompt.ask(
        "What does Claude Code say? (try something off-task like 'I'll monitor this')",
        default="I'll monitor the implementation and check back later"
    )

    # Analyze
    context = TaskContext(
        user_instruction=task,
        recent_events=[],
        current_todos=[],
    )

    console.print("\n[cyan]Sending to devstral for analysis...[/cyan]")
    result = client.analyze_task_adherence(context, claude_response)

    console.print(f"\n[bold]devstral Analysis:[/bold]")
    console.print(f"  On task: {result.is_on_task}")
    console.print(f"  Confidence: {result.confidence:.1%}")
    console.print(f"  Reasoning: {result.reasoning}")

    if not result.is_on_task and result.confidence >= 0.7:
        console.print("\n[red]OFF-TASK DETECTED![/red]")
        console.print("\n[bold]Intervention would be sent:[/bold]")

        interventor = Interventor(console, intervention_file)
        decision = InterventionDecision(
            should_intervene=True,
            severity="high" if result.confidence >= 0.8 else "medium",
            intervention_message=f"Issue: {result.reasoning}",
            analysis=result,
        )

        interventor._write_intervention_file(decision)

        if intervention_file.exists():
            content = intervention_file.read_text()
            console.print(Panel(content, title="Intervention Message", border_style="red"))
            intervention_file.unlink()
    else:
        console.print("\n[green]Claude Code appears to be on task[/green]")


def main():
    """Run all tests."""
    print_header()

    # Get configuration
    from monitor.llm_client import DevstralClient

    base_url = Prompt.ask(
        "LM Studio base URL",
        default="http://localhost:1234/v1"
    )

    model = Prompt.ask(
        "Model name",
        default="devstral-latest"
    )

    intervention_file = Path(Prompt.ask(
        "Intervention file path",
        default="/tmp/hawtcher-intervention.txt"
    ))

    console.print()

    # Run tests
    results = []

    # Test 1: Connection
    client = DevstralClient(base_url, model)
    results.append(("LM Studio Connection", test_lm_studio_connection(base_url, model)))

    if not results[0][1]:
        console.print("\n[red]Cannot continue - LM Studio not connected[/red]")
        console.print("[yellow]Make sure LM Studio is running with devstral loaded[/yellow]")
        return 1

    # Test 2: Detection
    results.append(("Off-task Detection", test_off_task_detection(client)))

    # Test 3: File writing
    results.append(("Intervention Writing", test_intervention_writing(intervention_file)))

    # Test 4: Real scenario
    test_real_scenario(client, intervention_file)

    # Summary
    console.print("\n" + "="*60)
    console.print("[bold]Test Summary:[/bold]\n")

    all_passed = True
    for name, passed in results:
        status = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
        console.print(f"  {status} - {name}")
        if not passed:
            all_passed = False

    console.print()

    if all_passed:
        console.print("[bold green]All tests passed! ✓[/bold green]")
        console.print("\n[cyan]Ready to install Claude Code hook:[/cyan]")
        console.print("  ./install-claude-hook.sh")
        return 0
    else:
        console.print("[bold red]Some tests failed[/bold red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
