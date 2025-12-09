"""
FastAPI Main Application - Context-Aware Intelligent Scheduler
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from models import (
    get_db, 
    UserContextSchema, 
    UserContextDB,
    TaskRuleSchema, 
    TaskRuleResponse,
    TaskRuleDB,
    FeedbackSchema,
    FeedbackLogDB,
    InferenceResponse,
    ChatInputSchema,
    ChatResponse,
    InferredTask
)
from inference import InferenceEngine, NaturalLanguageParser

app = FastAPI(
    title="Context-Aware Intelligent Scheduler",
    description="AI-powered scheduler using inductive reasoning and reinforcement learning",
    version="1.0.0"
)

# CORS Configuration for Flutter frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Flutter app's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===================== HEALTH CHECK =====================

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Context-Aware Intelligent Scheduler",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


# ===================== CONTEXT INGESTION =====================

@app.post("/context", status_code=status.HTTP_201_CREATED)
def receive_context(context: UserContextSchema, db: Session = Depends(get_db)):
    """
    Receive sensor data from Flutter app
    Stores context in database for historical analysis
    """
    # Store context in database
    db_context = UserContextDB(
        timestamp=context.timestamp,
        activity_type=context.activity_type,
        speed=context.speed,
        is_connected_to_car_bluetooth=int(context.is_connected_to_car_bluetooth),
        wifi_ssid=context.wifi_ssid,
        location_vector=context.location_vector,
        additional_data=context.additional_data
    )
    
    db.add(db_context)
    db.commit()
    
    return {
        "success": True,
        "message": "Context received and stored",
        "timestamp": context.timestamp
    }


# ===================== INFERENCE ENDPOINT =====================

@app.post("/infer", response_model=InferenceResponse)
def infer_schedule(context: UserContextSchema, db: Session = Depends(get_db)):
    """
    Main inference endpoint: Receives context and returns suggested tasks
    This is the core of the inductive reasoning engine
    """
    # Store incoming context
    db_context = UserContextDB(
        timestamp=context.timestamp,
        activity_type=context.activity_type,
        speed=context.speed,
        is_connected_to_car_bluetooth=int(context.is_connected_to_car_bluetooth),
        wifi_ssid=context.wifi_ssid,
        location_vector=context.location_vector,
        additional_data=context.additional_data
    )
    db.add(db_context)
    db.commit()
    
    # Run inference engine
    engine = InferenceEngine(db)
    suggested_tasks = engine.infer_tasks(context)
    
    # Count total active rules
    total_rules = db.query(TaskRuleDB).filter(TaskRuleDB.is_active == 1).count()
    
    return InferenceResponse(
        timestamp=datetime.utcnow(),
        context_summary={
            "activity": context.activity_type,
            "location": context.location_vector,
            "car_connected": context.is_connected_to_car_bluetooth,
            "wifi": context.wifi_ssid or "disconnected"
        },
        suggested_tasks=suggested_tasks,
        total_rules_evaluated=total_rules
    )


# ===================== FEEDBACK LOOP (REINFORCEMENT LEARNING) =====================

@app.post("/feedback")
def provide_feedback(feedback: FeedbackSchema, db: Session = Depends(get_db)):
    """
    Reinforcement Learning Endpoint
    User feedback adjusts probability weights:
    - Positive: +0.05 (reward)
    - Negative: -0.10 (penalty)
    """
    # Log the feedback
    feedback_log = FeedbackLogDB(
        rule_id=feedback.rule_id,
        user_action=feedback.outcome,
        context_snapshot=feedback.context_snapshot,
        timestamp=datetime.utcnow()
    )
    db.add(feedback_log)
    db.commit()
    
    # Apply reinforcement learning
    engine = InferenceEngine(db)
    result = engine.apply_feedback(feedback.rule_id, feedback.outcome)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    
    return result


# ===================== TASK RULE MANAGEMENT =====================

@app.get("/rules", response_model=List[TaskRuleResponse])
def get_all_rules(db: Session = Depends(get_db)):
    """Retrieve all task rules"""
    rules = db.query(TaskRuleDB).all()
    return rules


@app.get("/rules/{rule_id}", response_model=TaskRuleResponse)
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    """Get a specific rule by ID"""
    rule = db.query(TaskRuleDB).filter(TaskRuleDB.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@app.post("/rules", response_model=TaskRuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(rule: TaskRuleSchema, db: Session = Depends(get_db)):
    """Create a new task rule"""
    db_rule = TaskRuleDB(
        task_name=rule.task_name,
        task_description=rule.task_description,
        trigger_condition=rule.trigger_condition,
        current_probability_weight=rule.current_probability_weight,
        is_active=int(rule.is_active)
    )
    
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    
    return db_rule


@app.put("/rules/{rule_id}", response_model=TaskRuleResponse)
def update_rule(rule_id: int, rule: TaskRuleSchema, db: Session = Depends(get_db)):
    """Update an existing rule"""
    db_rule = db.query(TaskRuleDB).filter(TaskRuleDB.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    db_rule.task_name = rule.task_name
    db_rule.task_description = rule.task_description
    db_rule.trigger_condition = rule.trigger_condition
    db_rule.current_probability_weight = rule.current_probability_weight
    db_rule.is_active = int(rule.is_active)
    db_rule.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_rule)
    
    return db_rule


@app.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """Delete a task rule"""
    db_rule = db.query(TaskRuleDB).filter(TaskRuleDB.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    db.delete(db_rule)
    db.commit()
    
    return {"success": True, "message": f"Rule {rule_id} deleted"}


# ===================== NATURAL LANGUAGE CHAT INPUT =====================

@app.post("/chat-input", response_model=ChatResponse)
def chat_input(chat: ChatInputSchema, db: Session = Depends(get_db)):
    """
    Natural Language Processing Endpoint
    Converts user text into task rules
    Example: "I have a dentist appointment on the way home at 5 PM"
    """
    parser = NaturalLanguageParser(db)
    
    try:
        result = parser.parse_user_input(chat.user_message, chat.context)
        
        # Convert DB model to response schema
        created_rule = None
        if result.get("created_rule"):
            rule_db = result["created_rule"]
            created_rule = TaskRuleResponse(
                id=rule_db.id,
                task_name=rule_db.task_name,
                task_description=rule_db.task_description,
                trigger_condition=rule_db.trigger_condition,
                current_probability_weight=rule_db.current_probability_weight,
                is_active=bool(rule_db.is_active),
                created_at=rule_db.created_at,
                updated_at=rule_db.updated_at
            )
        
        return ChatResponse(
            understood=result["understood"],
            interpretation=result["interpretation"],
            created_rule=created_rule,
            message=f"✓ Task created: {result['task_name']}"
        )
    
    except Exception as e:
        return ChatResponse(
            understood=False,
            interpretation="I couldn't understand that request.",
            created_rule=None,
            message=f"Error: {str(e)}"
        )


# ===================== ANALYTICS & FEEDBACK HISTORY =====================

@app.get("/feedback-history")
def get_feedback_history(limit: int = 50, db: Session = Depends(get_db)):
    """Retrieve recent feedback logs for analysis"""
    logs = db.query(FeedbackLogDB).order_by(
        FeedbackLogDB.timestamp.desc()
    ).limit(limit).all()
    
    return {
        "total": len(logs),
        "feedback_logs": [
            {
                "id": log.id,
                "rule_id": log.rule_id,
                "action": log.user_action,
                "timestamp": log.timestamp,
                "context": log.context_snapshot
            }
            for log in logs
        ]
    }


@app.get("/analytics/rule-performance")
def rule_performance_analytics(db: Session = Depends(get_db)):
    """
    Analytics: Show which rules get the most positive/negative feedback
    """
    rules = db.query(TaskRuleDB).all()
    analytics = []
    
    for rule in rules:
        positive_count = db.query(FeedbackLogDB).filter(
            FeedbackLogDB.rule_id == rule.id,
            FeedbackLogDB.user_action == "accepted"
        ).count()
        
        negative_count = db.query(FeedbackLogDB).filter(
            FeedbackLogDB.rule_id == rule.id,
            FeedbackLogDB.user_action == "rejected"
        ).count()
        
        total_feedback = positive_count + negative_count
        acceptance_rate = (positive_count / total_feedback * 100) if total_feedback > 0 else 0
        
        analytics.append({
            "rule_id": rule.id,
            "task_name": rule.task_name,
            "probability_weight": rule.current_probability_weight,
            "positive_feedback": positive_count,
            "negative_feedback": negative_count,
            "acceptance_rate": round(acceptance_rate, 1),
            "is_active": bool(rule.is_active)
        })
    
    # Sort by acceptance rate
    analytics.sort(key=lambda x: x["acceptance_rate"], reverse=True)
    
    return {"analytics": analytics}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
