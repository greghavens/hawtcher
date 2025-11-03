"""
Pydantic models for Claude Code monitoring.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class ClaudeHistoryEvent(BaseModel):
    """Model for a Claude Code history.jsonl entry."""

    display: str
    timestamp: int
    project: str
    session_id: str = Field(alias="sessionId")
    pasted_contents: Optional[dict[str, Any]] = Field(default=None, alias="pastedContents")

    @field_validator("timestamp")
    @classmethod
    def convert_timestamp(cls, v: int) -> datetime:
        """Convert Unix milliseconds to datetime."""
        return datetime.fromtimestamp(v / 1000.0)

    class Config:
        populate_by_name = True


class TaskContext(BaseModel):
    """Current task context for analysis."""

    user_instruction: str
    recent_events: list[ClaudeHistoryEvent]
    current_todos: list[str] = Field(default_factory=list)
    completed_todos: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Result from devstral analysis."""

    is_on_task: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    detected_issues: list[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None


class InterventionDecision(BaseModel):
    """Decision about whether and how to intervene."""

    should_intervene: bool
    severity: str = Field(pattern="^(low|medium|high|critical)$")
    intervention_message: str
    analysis: AnalysisResult
    timestamp: datetime = Field(default_factory=datetime.now)


class MonitorConfig(BaseModel):
    """Configuration for the monitoring agent."""

    lm_studio_base_url: str
    lm_studio_model: str
    claude_history_path: str
    intervention_file_path: str
    check_interval_seconds: int
    context_window_size: int
    intervention_threshold: float
    log_level: str
