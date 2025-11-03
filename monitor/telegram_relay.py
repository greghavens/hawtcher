"""
Telegram bot relay for forwarding Claude Code's questions to user.
"""

import asyncio
import threading
from typing import Optional, Callable
from queue import Queue, Empty
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)


class TelegramRelay:
    """Relays questions from Claude Code to user via Telegram bot."""

    def __init__(
        self,
        bot_token: str,
        chat_id: Optional[str] = None,
        response_timeout: int = 300,  # 5 minutes
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.response_timeout = response_timeout

        # Queue for question/answer coordination
        self.answer_queue: Queue[str] = Queue()
        self.waiting_for_answer = False
        self.current_question_id = 0

        # Bot application
        self.app: Optional[Application] = None
        self.bot_thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None

        # Callback for when chat_id is first detected
        self.on_chat_id_detected: Optional[Callable[[str], None]] = None

    def start(self):
        """Start the Telegram bot in a background thread."""
        self.bot_thread = threading.Thread(target=self._run_bot, daemon=True)
        self.bot_thread.start()

    def _run_bot(self):
        """Run the bot in its own event loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.app = Application.builder().token(self.bot_token).build()

        # Add handlers
        self.app.add_handler(CommandHandler("start", self._handle_start))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        self.app.add_handler(CallbackQueryHandler(self._handle_button))

        # Run bot
        self.loop.run_until_complete(self.app.initialize())
        self.loop.run_until_complete(self.app.start())
        self.loop.run_until_complete(self.app.updater.start_polling())

        # Keep running
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.loop.run_until_complete(self.app.stop())

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user_chat_id = str(update.effective_chat.id)

        if not self.chat_id:
            # First time setup - capture chat ID
            self.chat_id = user_chat_id
            if self.on_chat_id_detected:
                self.on_chat_id_detected(user_chat_id)

            await update.message.reply_text(
                "✅ Hawtcher connected!\n\n"
                f"Your chat ID: `{user_chat_id}`\n\n"
                "I'll forward questions from Claude Code to you here.",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "✅ Hawtcher is already connected!\n\n"
                "I'll forward questions from Claude Code to you here."
            )

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (answers to questions)."""
        if not self.waiting_for_answer:
            await update.message.reply_text(
                "I'm not currently waiting for an answer. "
                "I'll send you a question when Claude Code needs input."
            )
            return

        # Put answer in queue
        self.answer_queue.put(update.message.text)
        await update.message.reply_text("✅ Answer received! Sending to Claude Code...")

    async def _handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button clicks."""
        query = update.callback_query
        await query.answer()

        if not self.waiting_for_answer:
            await query.edit_message_text(
                "This question has already been answered or timed out."
            )
            return

        # Extract answer from callback data
        answer = query.data

        # Put answer in queue
        self.answer_queue.put(answer)
        await query.edit_message_text(
            f"✅ Answer received: {answer}\n\nSending to Claude Code..."
        )

    def ask_question(
        self,
        question: str,
        task_description: str,
        devstral_suggestion: Optional[str] = None,
        devstral_confidence: Optional[float] = None,
        context: Optional[str] = None,
    ) -> Optional[str]:
        """
        Forward a question to the user and wait for response.

        Args:
            question: The question Claude Code is asking
            task_description: Current task description
            devstral_suggestion: devstral's suggested answer (if any)
            devstral_confidence: devstral's confidence in the suggestion
            context: Additional context

        Returns:
            User's answer, or None if timeout
        """
        if not self.chat_id:
            print("Warning: Telegram chat_id not configured")
            return None

        self.current_question_id += 1
        self.waiting_for_answer = True

        # Clear any old answers from queue
        while not self.answer_queue.empty():
            try:
                self.answer_queue.get_nowait()
            except Empty:
                break

        # Send question via Telegram
        asyncio.run_coroutine_threadsafe(
            self._send_question(
                question,
                task_description,
                devstral_suggestion,
                devstral_confidence,
                context,
            ),
            self.loop
        )

        # Wait for answer (blocking)
        try:
            answer = self.answer_queue.get(timeout=self.response_timeout)
            self.waiting_for_answer = False
            return answer
        except Empty:
            self.waiting_for_answer = False
            print(f"Timeout waiting for answer from Telegram ({self.response_timeout}s)")
            return None

    async def _send_question(
        self,
        question: str,
        task_description: str,
        devstral_suggestion: Optional[str],
        devstral_confidence: Optional[float],
        context: Optional[str],
    ):
        """Send question to user via Telegram."""
        # Build message
        message_parts = [
            f"📨 *Claude Code Question #{self.current_question_id}*",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"*Task:* {task_description[:100]}",
            "",
            f"*Question:*\n{question}",
        ]

        if context:
            message_parts.append(f"\n*Context:*\n{context[:200]}")

        if devstral_suggestion:
            confidence_pct = f"{devstral_confidence * 100:.0f}%" if devstral_confidence else "?"
            message_parts.extend([
                "",
                f"*devstral's suggestion ({confidence_pct} confident):*",
                f"_{devstral_suggestion[:150]}_",
            ])

        message_parts.extend([
            "",
            "💬 *Your answer:*",
        ])

        message_text = "\n".join(message_parts)

        # Build inline keyboard
        keyboard = []
        if devstral_suggestion:
            keyboard.append([
                InlineKeyboardButton("✅ Use devstral's answer", callback_data=devstral_suggestion[:100])
            ])

        # Add common quick responses if question looks like yes/no
        question_lower = question.lower()
        if any(word in question_lower for word in ["should i", "do you want", "would you like"]):
            keyboard.append([
                InlineKeyboardButton("Yes", callback_data="Yes"),
                InlineKeyboardButton("No", callback_data="No"),
            ])

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        # Send message
        await self.app.bot.send_message(
            chat_id=self.chat_id,
            text=message_text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )

    async def _send_notification_async(self, message: str):
        """Send a fire-and-forget notification."""
        if not self.chat_id:
            return

        await self.app.bot.send_message(
            chat_id=self.chat_id,
            text=message,
            parse_mode="Markdown",
        )

    def send_notification(self, message: str):
        """Send a notification without expecting a response."""
        if not self.loop or not self.app:
            return

        asyncio.run_coroutine_threadsafe(
            self._send_notification_async(message),
            self.loop
        )

    def stop(self):
        """Stop the Telegram bot."""
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.bot_thread:
            self.bot_thread.join(timeout=5)
