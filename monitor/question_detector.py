"""
Question detector for identifying when Claude Code asks the user questions.
"""

import re
from typing import Optional


class QuestionDetector:
    """Detects when Claude Code is asking the user a question."""

    # Patterns that indicate Claude is asking for user input
    QUESTION_PATTERNS = [
        r'\?$',  # Ends with question mark
        r'^Should I\b',
        r'^Which\b',
        r'^Do you want',
        r'^Would you like',
        r'^Can I\b',
        r'^May I\b',
        r'^Could you\b',
        r'^Would you\b',
        r'^Please (?:confirm|choose|select|specify|clarify)',
        r'\bconfirm\?',
        r'\bchoose\b.*\?',
        r'\bprefer\b.*\?',
        r'\bor\b.*\?',  # "Should I do X or Y?"
    ]

    # Patterns that look like questions but probably aren't user prompts
    RHETORICAL_PATTERNS = [
        r'^What (?:is|are|was|were|does|did)',  # "What is this?" (analyzing code)
        r'^How (?:does|did|can|should) (?:this|that|it)',  # "How does this work?" (analyzing)
        r'^Why (?:is|are|does|did)',  # "Why is this failing?"
        r"^Let me (?:check|see|verify|analyze)",  # Planning, not asking
    ]

    def __init__(self):
        self.question_patterns = [re.compile(p, re.IGNORECASE | re.MULTILINE)
                                  for p in self.QUESTION_PATTERNS]
        self.rhetorical_patterns = [re.compile(p, re.IGNORECASE | re.MULTILINE)
                                    for p in self.RHETORICAL_PATTERNS]

    def is_question(self, text: str) -> bool:
        """
        Determine if the text contains a question for the user.

        Args:
            text: Text to analyze

        Returns:
            True if this appears to be a question for the user
        """
        if not text or len(text.strip()) == 0:
            return False

        # Check for rhetorical patterns first (exclude these)
        for pattern in self.rhetorical_patterns:
            if pattern.search(text):
                return False

        # Check for question patterns
        for pattern in self.question_patterns:
            if pattern.search(text):
                return True

        return False

    def extract_question(self, text: str) -> Optional[str]:
        """
        Extract the question text from a larger message.

        Args:
            text: Text containing a question

        Returns:
            The question text, or None if no question found
        """
        if not self.is_question(text):
            return None

        # Split by newlines and find question sentences
        lines = text.split('\n')
        questions = []

        for line in lines:
            line = line.strip()
            if self.is_question(line):
                questions.append(line)

        if not questions:
            # Fallback: return the whole text if it contains a question mark
            if '?' in text:
                return text.strip()
            return None

        # Return the first significant question
        return questions[0]

    def get_question_context(self, text: str) -> tuple[str, str]:
        """
        Extract both the question and surrounding context.

        Args:
            text: Text containing the question

        Returns:
            Tuple of (question, context)
        """
        question = self.extract_question(text)
        if not question:
            return ("", text)

        # Context is everything except the question line
        lines = text.split('\n')
        context_lines = [line for line in lines if line.strip() != question]
        context = '\n'.join(context_lines).strip()

        return (question, context)
