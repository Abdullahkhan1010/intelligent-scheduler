"""
SQLAlchemy Models & Pydantic Schemas for Context-Aware Intelligent Scheduler
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal, List

# SQLAlchemy Base
Base = declarative_base()

# ===================== SQLAlchemy Models =====================

class UserContextDB(Base):
    """Stores historical sensor data from mobile device"""
    __tablename__ = "user_contexts"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    activity_type = Column(String, index=True)  # STILL, WALKING, IN_VEHICLE, etc.
    speed = Column(Float, default=0.0)  # Speed in km/h
    is_connected_to_car_bluetooth = Column(Integer, default=0)  # 0 or 1
    wifi_ssid = Column(String, nullable=True)  # Current WiFi network
    location_vector = Column(String, nullable=True)  # e.g., "home", "work", "leaving_home"
    additional_data = Column(JSON, nullable=True)  # For extensibility


class TaskRuleDB(Base):
    """Probabilistic rules that trigger task suggestions"""
    __tablename__ = "task_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String, index=True)
    task_description = Column(String, nullable=True)
    trigger_condition = Column(JSON)  # Conditions that must match
    current_probability_weight = Column(Float, default=0.7)  # Learning parameter
    calendar_event_id = Column(String, nullable=True, index=True)  # Link to calendar event
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Integer, default=1)  # Can disable rules


class FeedbackLogDB(Base):
    """Stores user feedback for reinforcement learning"""
    __tablename__ = "feedback_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, index=True)
    user_action = Column(String)  # "accepted" or "rejected"
    context_snapshot = Column(JSON, nullable=True)  # Context when feedback was given
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class BayesianTimingParametersDB(Base):
    """Stores Beta distribution parameters for Bayesian timing inference"""
    __tablename__ = "bayesian_timing_parameters"
    
    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String, index=True)  # Task category (e.g., "Get Fuel", "Dentist")
    context_key = Column(String, index=True)  # Context signature (e.g., "IN_VEHICLE_morning")
    timing_window = Column(Integer, index=True)  # Minutes before task (60, 30, 10)
    alpha = Column(Float, default=1.0)  # Beta distribution parameter (successes + 1)
    beta = Column(Float, default=1.0)  # Beta distribution parameter (failures + 1)
    total_triggers = Column(Integer, default=0)  # Total times this combination was triggered
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class CalendarEventDB(Base):
    """Stores parsed calendar events with inferred metadata"""
    __tablename__ = "calendar_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, index=True)  # Google Calendar event ID
    title = Column(String, index=True)
    description = Column(String, nullable=True)
    start_time = Column(DateTime, nullable=True, index=True)
    end_time = Column(DateTime, nullable=True)
    is_all_day = Column(Integer, default=0)
    
    # Classification
    task_type = Column(String)  # fixed_event or flexible_task
    priority = Column(String, index=True)  # high, medium, low
    time_critical = Column(Integer, default=0)
    
    # Location
    location = Column(String, nullable=True)
    location_category = Column(String, nullable=True)  # home, work, campus, etc.
    
    # Timing metadata
    preparation_time_minutes = Column(Integer, nullable=True)
    travel_time_minutes = Column(Integer, nullable=True)
    optimal_reminder_time = Column(DateTime, nullable=True, index=True)
    
    # Recurrence
    is_recurring = Column(Integer, default=0)
    recurrence_pattern = Column(String, nullable=True)
    recurrence_id = Column(String, nullable=True, index=True)
    
    # Reminder tracking
    last_reminded_at = Column(DateTime, nullable=True)
    reminder_count = Column(Integer, default=0)
    completed = Column(Integer, default=0)
    dismissed = Column(Integer, default=0)
    
    # Context hints
    suggested_contexts = Column(JSON, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime, default=datetime.utcnow)


# ===================== Pydantic Schemas =====================

class UserContextSchema(BaseModel):
    """Input schema for sensor data"""
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    activity_type: str = Field(..., description="Activity: STILL, WALKING, IN_VEHICLE, etc.")
    speed: float = Field(default=0.0, ge=0.0)
    is_connected_to_car_bluetooth: bool = Field(default=False)
    wifi_ssid: Optional[str] = None
    location_vector: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "activity_type": "IN_VEHICLE",
                "speed": 45.0,
                "is_connected_to_car_bluetooth": True,
                "wifi_ssid": None,
                "location_vector": "leaving_home"
            }
        }


class TaskRuleSchema(BaseModel):
    """Schema for creating/updating task rules"""
    task_name: str
    task_description: Optional[str] = None
    trigger_condition: Dict[str, Any]
    current_probability_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    is_active: bool = True


class NotificationDecisionRequest(BaseModel):
    """Request schema for notification decision endpoint"""
    task_type: str = Field(..., description="Type of task (e.g., 'Check Email', 'Gym Workout')")
    task_scheduled_time: Optional[datetime] = Field(None, description="When task is scheduled (if fixed time)")
    context: UserContextSchema = Field(..., description="Current user context")
    priority: str = Field(default="medium", description="Task priority: high, medium, or low")

    class Config:
        json_schema_extra = {
            "example": {
                "task_type": "Gym Workout",
                "task_scheduled_time": None,
                "context": {
                    "activity_type": "STILL",
                    "speed": 0.0,
                    "is_connected_to_car_bluetooth": False,
                    "wifi_ssid": "HomeNetwork",
                    "location_vector": "home"
                },
                "priority": "medium"
            }
        }


class NotificationDecisionResponse(BaseModel):
    """Response schema for notification decision endpoint"""
    notify_now: bool = Field(..., description="Whether to send notification immediately")
    confidence: float = Field(..., description="Confidence score (0.0-1.0)")
    optimal_timing_window: int = Field(..., description="Best timing window in minutes")
    suggested_delay_minutes: Optional[int] = Field(None, description="Suggested delay if not notifying now")
    explanation: str = Field(..., description="Human-readable explanation of decision")
    context_key: str = Field(..., description="Context signature used for inference")
    all_timing_options: list = Field(..., description="All evaluated timing windows with scores")
    decision_factors: Dict[str, Any] = Field(..., description="Factors that influenced the decision")

    class Config:
        json_schema_extra = {
            "example": {
                "notify_now": True,
                "confidence": 0.75,
                "optimal_timing_window": 30,
                "suggested_delay_minutes": None,
                "explanation": "High confidence (75%) based on 12 historical interactions.",
                "context_key": "STILL_evening_weekday_home",
                "all_timing_options": [
                    {"window": 60, "confidence": 0.6},
                    {"window": 30, "confidence": 0.75},
                    {"window": 10, "confidence": 0.4}
                ],
                "decision_factors": {
                    "time_of_day": "evening",
                    "location": "home",
                    "activity": "stationary",
                    "evidence_strength": 12
                }
            }
        }

    class Config:
        json_schema_extra = {
            "example": {
                "task_name": "Get Fuel",
                "task_description": "Stop at gas station on the way",
                "trigger_condition": {
                    "activity": "IN_VEHICLE",
                    "time_range": "08:00-09:00",
                    "location_vector": "leaving_home"
                },
                "current_probability_weight": 0.7
            }
        }


class TaskRuleResponse(TaskRuleSchema):
    """Response schema including database ID"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FeedbackSchema(BaseModel):
    """Feedback input for reinforcement learning"""
    rule_id: int
    outcome: Literal["positive", "negative"]
    context_snapshot: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "rule_id": 1,
                "outcome": "positive",
                "context_snapshot": {
                    "activity_type": "IN_VEHICLE",
                    "time": "08:30"
                }
            }
        }


class InferredTask(BaseModel):
    """Schema for tasks returned by inference engine"""
    rule_id: int
    task_name: str
    task_description: Optional[str]
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str  # Explanation of why this was triggered
    matched_conditions: Dict[str, Any]
    optimal_timing_window: Optional[int] = None  # Minutes before task
    timing_confidence: Optional[float] = None  # Bayesian confidence for timing


class InferenceResponse(BaseModel):
    """Response containing suggested tasks"""
    timestamp: datetime
    context_summary: Dict[str, Any]
    suggested_tasks: list[InferredTask]
    total_rules_evaluated: int


class ChatInputSchema(BaseModel):
    """Natural language input for creating tasks"""
    user_message: str
    context: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "user_message": "I have a dentist appointment on the way home at 5 PM",
                "context": {"current_location": "work"}
            }
        }


class ChatResponse(BaseModel):
    """Response from chat/NLP endpoint"""
    understood: bool
    interpretation: str
    created_rule: Optional[TaskRuleResponse] = None
    message: str


class ParsedTaskRequest(BaseModel):
    """Request to parse natural language into structured task"""
    user_input: str = Field(..., description="Natural language task description")
    current_context: Optional[Dict[str, Any]] = Field(None, description="Current user context for hints")

    class Config:
        json_schema_extra = {
            "example": {
                "user_input": "Remind me to call mom at 6 PM tomorrow",
                "current_context": {"location": "home"}
            }
        }


class ParsedTaskResponse(BaseModel):
    """Response with parsed task details and confidence"""
    success: bool
    confidence: float = Field(..., ge=0.0, le=1.0, description="Parsing confidence (0.0-1.0)")
    parsed_task_name: Optional[str] = Field(None, description="Extracted task name")
    parsed_description: Optional[str] = Field(None, description="Full description")
    parsed_time: Optional[str] = Field(None, description="Extracted time (ISO format or description)")
    parsed_date: Optional[str] = Field(None, description="Extracted date")
    parsed_location: Optional[str] = Field(None, description="Extracted location context")
    parsed_priority: Optional[str] = Field(None, description="Inferred priority (high/medium/low)")
    parsed_duration_minutes: Optional[int] = Field(None, description="Estimated task duration")
    extraction_details: Dict[str, Any] = Field(default_factory=dict, description="What was extracted and how")
    confidence_breakdown: Dict[str, float] = Field(default_factory=dict, description="Confidence per field")
    requires_confirmation: bool = Field(True, description="Whether user should confirm details")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions for ambiguous parts")
    original_input: str = Field(..., description="Original user input")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "confidence": 0.85,
                "parsed_task_name": "Call mom",
                "parsed_description": "Remind me to call mom at 6 PM tomorrow",
                "parsed_time": "18:00",
                "parsed_date": "2025-12-20",
                "parsed_location": None,
                "parsed_priority": "medium",
                "parsed_duration_minutes": 15,
                "extraction_details": {
                    "task_name": "Found keyword 'call' → 'Call mom'",
                    "time": "Extracted '6 PM' → 18:00",
                    "date": "Detected 'tomorrow' → 2025-12-20"
                },
                "confidence_breakdown": {
                    "task_name": 0.9,
                    "time": 0.95,
                    "date": 0.85,
                    "priority": 0.7
                },
                "requires_confirmation": True,
                "suggestions": [],
                "original_input": "Remind me to call mom at 6 PM tomorrow"
            }
        }


class TaskCreationRequest(BaseModel):
    """Request to create a confirmed task"""
    task_name: str
    task_description: str
    scheduled_time: Optional[datetime] = None
    location_context: Optional[str] = None
    priority: str = Field(default="medium", description="high, medium, or low")
    duration_minutes: Optional[int] = None
    trigger_conditions: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "task_name": "Call mom",
                "task_description": "Remind me to call mom at 6 PM tomorrow",
                "scheduled_time": "2025-12-20T18:00:00",
                "location_context": "home",
                "priority": "medium",
                "duration_minutes": 15
            }
        }


class CalendarEventSchema(BaseModel):
    """Schema for calendar event from Flutter"""
    event_id: str
    summary: str
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    is_all_day: bool = False
    recurrence: Optional[List[str]] = None
    recurring_event_id: Optional[str] = None
    attendees: Optional[List[Dict[str, Any]]] = None


class CalendarSyncRequest(BaseModel):
    """Request to sync calendar events"""
    events: List[CalendarEventSchema]
    
    class Config:
        json_schema_extra = {
            "example": {
                "events": [
                    {
                        "event_id": "abc123",
                        "summary": "Team Meeting",
                        "description": "Weekly sync with team",
                        "start_time": "2025-12-21T10:00:00",
                        "end_time": "2025-12-21T11:00:00",
                        "location": "Conference Room A",
                        "is_all_day": False
                    }
                ]
            }
        }


class CalendarSyncResponse(BaseModel):
    """Response from calendar sync"""
    success: bool
    events_processed: int
    events_created: int
    events_updated: int
    tasks_generated: int
    message: str


# ===================== Database Setup =====================

def get_database():
    """Create database engine and session"""
    SQLALCHEMY_DATABASE_URL = "sqlite:///./scheduler.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal

def get_db():
    """Dependency for FastAPI routes"""
    SessionLocal = get_database()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
