"""
SQLAlchemy Models & Pydantic Schemas for Context-Aware Intelligent Scheduler
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal

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
