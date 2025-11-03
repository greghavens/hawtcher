"""
Question answerer using devstral to attempt answering Claude Code's questions.
"""

import json
from typing import Optional
from dataclasses import dataclass

from monitor.llm_client import DevstralClient
from monitor.models import TaskContext


@dataclass
class AnswerAttempt:
    """Result of attempting to answer a question."""
    answer: str
    confidence: float  # 0.0 to 1.0
    reasoning: str
    should_ask_user: bool  # True if confidence below threshold


class QuestionAnswerer:
    """Attempts to answer Claude Code's questions using devstral."""

    def __init__(
        self,
        llm_client: DevstralClient,
        confidence_threshold: float = 0.95,
    ):
        self.llm_client = llm_client
        self.confidence_threshold = confidence_threshold

    def try_answer(
        self,
        question: str,
        context: TaskContext,
        additional_context: str = "",
    ) -> AnswerAttempt:
        """
        Attempt to answer a question from Claude Code.

        Args:
            question: The question Claude Code is asking
            context: Current task context
            additional_context: Additional context from the message

        Returns:
            AnswerAttempt with answer and confidence level
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_question_prompt(question, context, additional_context)

        try:
            response = self.llm_client.client.chat.completions.create(
                model=self.llm_client.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            content = response.choices[0].message.content
            return self._parse_answer_response(content)

        except Exception as e:
            print(f"Error getting answer from devstral: {e}")
            # Return low-confidence result that triggers user question
            return AnswerAttempt(
                answer="",
                confidence=0.0,
                reasoning=f"Failed to get answer: {str(e)}",
                should_ask_user=True,
            )

    def _build_system_prompt(self) -> str:
        """Build the system prompt for question answering."""
        return """You are an AI assistant helping to answer questions that Claude Code asks users.

Your job is to analyze the question in the context of the current task and provide:
1. Your best answer to the question
2. Your confidence level (0.0 to 1.0) in that answer
3. Brief reasoning for your answer

If you're not confident in your answer (< 0.95), the question will be forwarded to the human user.

Respond in JSON format:
{
  "answer": "Your answer to the question",
  "confidence": 0.85,
  "reasoning": "Why you chose this answer and what makes you uncertain"
}

Be conservative with confidence - only give high confidence (>0.95) if you're very certain based on the task context."""

    def _build_question_prompt(
        self,
        question: str,
        context: TaskContext,
        additional_context: str,
    ) -> str:
        """Build the prompt with question and context."""
        recent_history = "\n".join(
            f"- [{event.timestamp}] {event.display[:150]}"
            for event in context.recent_events[-5:]
        )

        todos_section = ""
        if context.current_todos:
            todos_section = "\n\nCurrent TODOs:\n" + "\n".join(
                f"- {todo}" for todo in context.current_todos
            )

        context_section = ""
        if additional_context:
            context_section = f"\n\nAdditional Context:\n{additional_context}"

        return f"""Task: {context.user_instruction}

Recent Activity:
{recent_history}
{todos_section}
{context_section}

Claude Code is asking:
"{question}"

Please provide your answer, confidence level, and reasoning in JSON format."""

    def _parse_answer_response(self, content: str) -> AnswerAttempt:
        """Parse the JSON response from devstral."""
        try:
            # Try to extract JSON from response
            content = content.strip()
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0]
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())

            answer = data.get("answer", "")
            confidence = float(data.get("confidence", 0.0))
            reasoning = data.get("reasoning", "")

            # Ensure confidence is in valid range
            confidence = max(0.0, min(1.0, confidence))

            should_ask_user = confidence < self.confidence_threshold

            return AnswerAttempt(
                answer=answer,
                confidence=confidence,
                reasoning=reasoning,
                should_ask_user=should_ask_user,
            )

        except Exception as e:
            print(f"Error parsing answer response: {e}")
            print(f"Response was: {content}")
            # Return low-confidence result
            return AnswerAttempt(
                answer="",
                confidence=0.0,
                reasoning=f"Failed to parse response: {str(e)}",
                should_ask_user=True,
            )
