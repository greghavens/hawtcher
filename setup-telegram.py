#!/usr/bin/env python3
"""
Telegram bot setup helper for Hawtcher.
"""

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

console = Console()


def main():
    """Interactive Telegram bot setup."""
    console.clear()

    # Display banner
    banner_text = """[bold green]Hawtcher Telegram Setup[/bold green]

This will help you set up Telegram notifications for Claude Code questions.
"""
    console.print(Panel(banner_text, expand=False))
    console.print()

    # Step 1: Instructions for creating bot
    console.print("[bold cyan]Step 1: Create a Telegram Bot[/bold cyan]")
    console.print()
    console.print("1. Open Telegram and search for @BotFather")
    console.print("2. Send the command: /newbot")
    console.print("3. Follow the prompts to name your bot")
    console.print("4. Copy the bot token (long string like: 123456:ABC-DEF...)")
    console.print()

    if not Confirm.ask("Have you created your bot and have the token?"):
        console.print("[yellow]Please create a bot first, then run this script again.[/yellow]")
        return

    # Get bot token
    console.print()
    bot_token = Prompt.ask("[green]Paste your bot token here[/green]").strip()

    if not bot_token or ":" not in bot_token:
        console.print("[red]Invalid bot token format[/red]")
        return

    # Step 2: Get chat ID
    console.print()
    console.print("[bold cyan]Step 2: Get Your Chat ID[/bold cyan]")
    console.print()
    console.print("Your chat ID will be detected automatically when you send /start to your bot.")
    console.print()
    console.print("We'll start a temporary bot listener...")
    console.print()

    # Try to start bot and detect chat ID
    try:
        import asyncio
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes

        detected_chat_id = None

        async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            nonlocal detected_chat_id
            detected_chat_id = str(update.effective_chat.id)
            await update.message.reply_text(
                "✅ Connected! Your chat ID has been detected.\n\n"
                "You can now close this and configure Hawtcher."
            )
            # Stop the application
            await context.application.stop()

        async def run_bot():
            app = Application.builder().token(bot_token).build()
            app.add_handler(CommandHandler("start", start_handler))

            console.print("[yellow]Waiting for you to send /start to your bot...[/yellow]")
            console.print("[dim](Open Telegram, find your bot, and send /start)[/dim]")
            console.print()

            await app.initialize()
            await app.start()
            await app.updater.start_polling()

            # Wait for chat ID detection (max 60 seconds)
            for _ in range(60):
                if detected_chat_id:
                    break
                await asyncio.sleep(1)

            await app.stop()
            return detected_chat_id

        chat_id = asyncio.run(run_bot())

        if not chat_id:
            console.print()
            console.print("[yellow]No /start message received. You can manually add your chat ID later.[/yellow]")
            chat_id = ""

    except Exception as e:
        console.print(f"[red]Error starting bot: {e}[/red]")
        console.print("[yellow]You can manually add your chat ID to .env later[/yellow]")
        chat_id = ""

    # Step 3: Update .env file
    console.print()
    console.print("[bold cyan]Step 3: Update Configuration[/bold cyan]")
    console.print()

    env_path = Path(".env")
    env_example_path = Path(".env.example")

    # Create .env from .env.example if it doesn't exist
    if not env_path.exists() and env_example_path.exists():
        console.print("Creating .env file from .env.example...")
        env_path.write_text(env_example_path.read_text())

    if env_path.exists():
        env_content = env_path.read_text()

        # Update or add Telegram settings
        lines = env_content.split("\n")
        new_lines = []
        found_token = False
        found_chat_id = False
        found_enabled = False

        for line in lines:
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                new_lines.append(f"TELEGRAM_BOT_TOKEN={bot_token}")
                found_token = True
            elif line.startswith("TELEGRAM_CHAT_ID="):
                new_lines.append(f"TELEGRAM_CHAT_ID={chat_id}")
                found_chat_id = True
            elif line.startswith("ENABLE_TELEGRAM_RELAY="):
                new_lines.append("ENABLE_TELEGRAM_RELAY=true")
                found_enabled = True
            else:
                new_lines.append(line)

        # Add missing settings
        if not found_token:
            new_lines.append(f"TELEGRAM_BOT_TOKEN={bot_token}")
        if not found_chat_id:
            new_lines.append(f"TELEGRAM_CHAT_ID={chat_id}")
        if not found_enabled:
            new_lines.append("ENABLE_TELEGRAM_RELAY=true")

        env_path.write_text("\n".join(new_lines))
        console.print("[green]✅ .env file updated[/green]")
    else:
        console.print("[yellow]No .env file found. Please create one manually.[/yellow]")

    # Done
    console.print()
    console.print(Panel(
        "[bold green]Setup Complete![/bold green]\n\n"
        "Your Telegram bot is configured.\n\n"
        "Next steps:\n"
        "1. Run: python hawtcher.py\n"
        "2. When Claude Code asks questions with low confidence,\n"
        "   you'll receive them in Telegram!\n\n"
        f"Bot Token: {bot_token[:20]}...\n"
        f"Chat ID: {chat_id if chat_id else '(send /start to your bot to get it)'}",
        title="🎉 Success",
        border_style="green"
    ))


if __name__ == "__main__":
    main()
