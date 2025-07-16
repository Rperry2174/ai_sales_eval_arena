"""Core data models for the AI Sales Evaluation Arena."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class TournamentFormat(str, Enum):
    """Tournament format types."""
    ROUND_ROBIN = "round_robin"
    SINGLE_ELIMINATION = "single_elimination"
    DOUBLE_ELIMINATION = "double_elimination"


class MatchStatus(str, Enum):
    """Match status types."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class GradingCriterion(str, Enum):
    """Sales pitch grading criteria."""
    ICP_ALIGNMENT = "icp_alignment"
    PBO_MESSAGING = "pbo_messaging"
    PROFILING_EXPLANATION = "profiling_explanation"
    OBSERVABILITY_CONTEXT = "observability_context"
    TALK_TRACK_ALIGNMENT = "talk_track_alignment"


class Participant(BaseModel):
    """A sales representative participating in the arena."""
    
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=100)
    email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    department: Optional[str] = None
    experience_years: Optional[int] = Field(None, ge=0, le=50)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class Transcript(BaseModel):
    """A sales pitch transcript."""
    
    id: UUID = Field(default_factory=uuid4)
    participant_id: UUID
    content: str = Field(..., min_length=50)
    duration_minutes: Optional[float] = Field(None, gt=0)
    word_count: int = Field(..., gt=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('word_count', pre=True, always=True)
    def calculate_word_count(cls, v: int, values: Dict[str, Any]) -> int:
        """Calculate word count from content if not provided."""
        if v is None and 'content' in values:
            return len(values['content'].split())
        return v


class CriterionGrade(BaseModel):
    """Grade for a specific criterion."""
    
    criterion: GradingCriterion
    score: float = Field(..., ge=1.0, le=4.0)
    explanation: str = Field(..., min_length=10)
    feedback: Optional[str] = None


class Grade(BaseModel):
    """Overall grade for a transcript."""
    
    id: UUID = Field(default_factory=uuid4)
    transcript_id: UUID
    participant_id: UUID
    criterion_grades: List[CriterionGrade]
    overall_score: float = Field(..., ge=1.0, le=4.0)
    overall_feedback: str = Field(..., min_length=10)
    grader_model: str = Field(default="gpt-4o-mini")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('overall_score', pre=True, always=True)
    def calculate_overall_score(cls, v: float, values: Dict[str, Any]) -> float:
        """Calculate overall score from criterion grades if not provided."""
        if v is None and 'criterion_grades' in values:
            scores = [grade.score for grade in values['criterion_grades']]
            return sum(scores) / len(scores) if scores else 1.0
        return v


class Match(BaseModel):
    """A match between two participants."""
    
    id: UUID = Field(default_factory=uuid4)
    tournament_id: UUID
    participant1_id: UUID
    participant2_id: UUID
    transcript1_id: UUID
    transcript2_id: UUID
    winner_id: Optional[UUID] = None
    grade1: Optional[Grade] = None
    grade2: Optional[Grade] = None
    comparison_feedback: Optional[str] = None
    status: MatchStatus = MatchStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    @validator('winner_id')
    def validate_winner(cls, v: Optional[UUID], values: Dict[str, Any]) -> Optional[UUID]:
        """Validate that winner is one of the participants."""
        if v is not None:
            participant1_id = values.get('participant1_id')
            participant2_id = values.get('participant2_id')
            if v not in [participant1_id, participant2_id]:
                raise ValueError("Winner must be one of the match participants")
        return v


class TournamentStandings(BaseModel):
    """Tournament standings for a participant."""
    
    participant_id: UUID
    wins: int = 0
    losses: int = 0
    draws: int = 0
    total_matches: int = 0
    average_score: float = 0.0
    win_percentage: float = 0.0
    rank: int = 0
    
    @validator('win_percentage', pre=True, always=True)
    def calculate_win_percentage(cls, v: float, values: Dict[str, Any]) -> float:
        """Calculate win percentage from wins and total matches."""
        total = values.get('total_matches', 0)
        wins = values.get('wins', 0)
        return (wins / total * 100) if total > 0 else 0.0


class Tournament(BaseModel):
    """A tournament containing multiple matches."""
    
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    format: TournamentFormat = TournamentFormat.ROUND_ROBIN
    participants: List[Participant] = Field(default_factory=list)
    matches: List[Match] = Field(default_factory=list)
    standings: List[TournamentStandings] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    winner_id: Optional[UUID] = None
    
    @property
    def is_completed(self) -> bool:
        """Check if tournament is completed."""
        return all(match.status == MatchStatus.COMPLETED for match in self.matches)
    
    @property
    def completion_percentage(self) -> float:
        """Calculate tournament completion percentage."""
        if not self.matches:
            return 0.0
        completed = sum(1 for match in self.matches if match.status == MatchStatus.COMPLETED)
        return (completed / len(self.matches)) * 100


class VisualizationConfig(BaseModel):
    """Configuration for tournament visualizations."""
    
    title: str = "AI Sales Evaluation Arena"
    theme: str = "plotly_white"
    color_scheme: List[str] = Field(default=[
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", 
        "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"
    ])
    width: int = Field(1200, gt=0)
    height: int = Field(800, gt=0)
    font_family: str = "Arial, sans-serif"
    show_logo: bool = True
    export_formats: List[str] = Field(default=["html", "png", "pdf"])


class ArenaConfig(BaseModel):
    """Main configuration for the arena system."""
    
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    max_concurrent_matches: int = Field(5, gt=0, le=20)
    grading_timeout_seconds: int = Field(60, gt=0)
    visualization: VisualizationConfig = Field(default_factory=VisualizationConfig)
    data_directory: str = "data"
    results_directory: str = "results"
    enable_real_time_updates: bool = True
    
    class Config:
        """Pydantic configuration."""
        env_prefix = "ARENA_" 