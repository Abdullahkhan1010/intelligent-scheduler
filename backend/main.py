"""
FastAPI Main Application - Context-Aware Intelligent Scheduler
"""
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional

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
    InferredTask,
    NotificationDecisionRequest,
    NotificationDecisionResponse,
    ParsedTaskRequest,
    ParsedTaskResponse,
    TaskCreationRequest,
    CalendarEventSchema,
    CalendarSyncRequest,
    CalendarSyncResponse,
    CalendarEventDB
)
from inference import InferenceEngine, NaturalLanguageParser
from learning_service import LearningService
from calendar_parser import parse_calendar_event

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
def infer_schedule(
    context: UserContextSchema, 
    db: Session = Depends(get_db),
    enable_search: bool = Query(
        True, 
        description="Enable A* search optimization for globally optimal task scheduling"
    )
):
    """
    Main inference endpoint: Receives context and returns suggested tasks
    
    This is the core of the inductive reasoning engine with two optimization modes:
    
    1. **Bayesian Inference (always enabled):**
       - Evaluates each task rule against current context
       - Uses Beta distributions to learn optimal notification timing
       - Calculates confidence scores based on historical feedback
    
    2. **A* Search Optimization (optional, default=True):**
       - Finds globally optimal combination of notification timings
       - Maximizes total expected reward across all tasks
       - Prevents notification conflicts and timing issues
       - Returns search metadata (nodes explored, search time, quality)
    
    **Query Parameters:**
    - `enable_search` (bool): Toggle A* search optimization (default: True)
      - True: Use A* for optimal global scheduling
      - False: Use greedy per-task optimization (faster, locally optimal)
    
    **Performance:**
    - Bayesian only: ~5-10ms
    - Bayesian + A* search: ~10-20ms (3-5 tasks)
    
    **Returns:**
    - Suggested tasks with optimal timing windows
    - Search metadata (if search enabled)
    - Context summary and total rules evaluated
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
    
    # Run inference engine with optional A* search
    engine = InferenceEngine(db, enable_search=enable_search)
    suggested_tasks = engine.infer_tasks(context)
    
    # Count total active rules
    total_rules = db.query(TaskRuleDB).filter(TaskRuleDB.is_active == 1).count()
    
    # Add optimization info to context summary
    context_summary = {
        "activity": context.activity_type,
        "location": context.location_vector,
        "car_connected": context.is_connected_to_car_bluetooth,
        "wifi": context.wifi_ssid or "disconnected",
        "optimization_mode": "A* search" if enable_search else "greedy"
    }
    
    return InferenceResponse(
        timestamp=datetime.utcnow(),
        context_summary=context_summary,
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


@app.post("/parse-task", response_model=ParsedTaskResponse)
def parse_task(request: ParsedTaskRequest, db: Session = Depends(get_db)):
    """
    Parse natural language into structured task with confidence scoring.
    Returns parsed details without creating the task yet.
    
    Example: "Remind me to call mom at 6 PM tomorrow"
    Returns: Structured task with confidence scores for each field
    """
    parser = NaturalLanguageParser(db)
    
    try:
        result = parser.parse_with_confidence(request.user_input, request.current_context)
        
        return ParsedTaskResponse(**result)
    
    except Exception as e:
        return ParsedTaskResponse(
            success=False,
            confidence=0.0,
            parsed_task_name=None,
            parsed_description=request.user_input,
            extraction_details={"error": str(e)},
            confidence_breakdown={},
            requires_confirmation=True,
            suggestions=["Could you rephrase that?"],
            original_input=request.user_input
        )


@app.post("/create-task", response_model=TaskRuleResponse)
def create_task(request: TaskCreationRequest, db: Session = Depends(get_db)):
    """
    Create a confirmed task from structured data.
    This is called after user confirms the parsed task details.
    """
    try:
        # Build trigger conditions
        trigger_condition = request.trigger_conditions or {}
        
        if request.location_context:
            trigger_condition["location_vector"] = request.location_context
        
        if request.scheduled_time:
            hour = request.scheduled_time.hour
            start_hour = max(0, hour - 1)
            end_hour = min(23, hour + 1)
            trigger_condition["time_range"] = f"{start_hour:02d}:00-{end_hour:02d}:00"
        
        # Determine initial probability weight based on priority
        priority_weights = {
            "high": 0.85,
            "medium": 0.75,
            "low": 0.65
        }
        initial_weight = priority_weights.get(request.priority, 0.75)
        
        # Create task rule
        new_rule = TaskRuleDB(
            task_name=request.task_name,
            task_description=request.task_description,
            trigger_condition=trigger_condition,
            current_probability_weight=initial_weight,
            is_active=1
        )
        
        db.add(new_rule)
        db.commit()
        db.refresh(new_rule)
        
        return TaskRuleResponse(
            id=new_rule.id,
            task_name=new_rule.task_name,
            task_description=new_rule.task_description,
            trigger_condition=new_rule.trigger_condition,
            current_probability_weight=new_rule.current_probability_weight,
            is_active=bool(new_rule.is_active),
            created_at=new_rule.created_at,
            updated_at=new_rule.updated_at
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create task: {str(e)}"
        )


# ===================== CALENDAR INTEGRATION =====================

@app.post("/calendar/sync", response_model=CalendarSyncResponse)
def sync_calendar_events(request: CalendarSyncRequest, db: Session = Depends(get_db)):
    """
    Sync calendar events from Google Calendar.
    Parses events, extracts priority and timing metadata, stores them,
    and creates task rules for intelligent reminders.
    """
    events_created = 0
    events_updated = 0
    tasks_generated = 0
    
    for event_data in request.events:
        try:
            # Convert to dict format expected by calendar_parser
            event_dict = {
                'id': event_data.event_id,
                'summary': event_data.summary,
                'description': event_data.description,
                'location': event_data.location,
                'start': {
                    'dateTime': event_data.start_time.isoformat() if event_data.start_time else None,
                    'date': event_data.start_time.date().isoformat() if event_data.is_all_day and event_data.start_time else None
                } if event_data.start_time else {},
                'end': {
                    'dateTime': event_data.end_time.isoformat() if event_data.end_time else None,
                    'date': event_data.end_time.date().isoformat() if event_data.is_all_day and event_data.end_time else None
                } if event_data.end_time else {},
                'attendees': event_data.attendees or [],
                'recurrence': event_data.recurrence,
                'recurringEventId': event_data.recurring_event_id
            }
            
            # Parse event using calendar_parser
            parsed_task = parse_calendar_event(event_dict)
            
            # Check if event already exists
            existing_event = db.query(CalendarEventDB).filter(
                CalendarEventDB.event_id == parsed_task.event_id
            ).first()
            
            if existing_event:
                # Update existing event
                existing_event.title = parsed_task.title
                existing_event.description = parsed_task.description
                existing_event.start_time = parsed_task.start_time
                existing_event.end_time = parsed_task.end_time
                existing_event.is_all_day = int(parsed_task.is_all_day)
                existing_event.task_type = parsed_task.task_type.value
                existing_event.priority = parsed_task.priority.value
                existing_event.time_critical = int(parsed_task.time_critical)
                existing_event.location = parsed_task.location
                existing_event.location_category = parsed_task.location_category
                existing_event.preparation_time_minutes = parsed_task.preparation_time_minutes
                existing_event.travel_time_minutes = parsed_task.travel_time_minutes
                existing_event.optimal_reminder_time = parsed_task.get_optimal_reminder_time()
                existing_event.is_recurring = int(parsed_task.is_recurring)
                existing_event.recurrence_pattern = parsed_task.recurrence_pattern
                existing_event.recurrence_id = parsed_task.recurrence_id
                existing_event.suggested_contexts = parsed_task.suggested_contexts
                existing_event.synced_at = datetime.utcnow()
                existing_event.updated_at = datetime.utcnow()
                events_updated += 1
            else:
                # Create new calendar event
                new_event = CalendarEventDB(
                    event_id=parsed_task.event_id,
                    title=parsed_task.title,
                    description=parsed_task.description,
                    start_time=parsed_task.start_time,
                    end_time=parsed_task.end_time,
                    is_all_day=int(parsed_task.is_all_day),
                    task_type=parsed_task.task_type.value,
                    priority=parsed_task.priority.value,
                    time_critical=int(parsed_task.time_critical),
                    location=parsed_task.location,
                    location_category=parsed_task.location_category,
                    preparation_time_minutes=parsed_task.preparation_time_minutes,
                    travel_time_minutes=parsed_task.travel_time_minutes,
                    optimal_reminder_time=parsed_task.get_optimal_reminder_time(),
                    is_recurring=int(parsed_task.is_recurring),
                    recurrence_pattern=parsed_task.recurrence_pattern,
                    recurrence_id=parsed_task.recurrence_id,
                    suggested_contexts=parsed_task.suggested_contexts
                )
                db.add(new_event)
                events_created += 1
            
            db.commit()
            
            # Create or update task rule for this calendar event
            # Only create rules for events that need reminders
            if parsed_task.start_time and not parsed_task.is_all_day:
                # Check if rule already exists
                existing_rule = db.query(TaskRuleDB).filter(
                    TaskRuleDB.calendar_event_id == parsed_task.event_id
                ).first()
                
                # Build trigger conditions based on event metadata
                trigger_conditions = {
                    'calendar_event': True,
                    'priority': parsed_task.priority.value,
                    'time_critical': parsed_task.time_critical
                }
                
                # Add context suggestions
                if parsed_task.suggested_contexts:
                    trigger_conditions['contexts'] = parsed_task.suggested_contexts
                
                # Add location if specified
                if parsed_task.location_category:
                    trigger_conditions['location_category'] = parsed_task.location_category
                
                if existing_rule:
                    # Update existing rule
                    existing_rule.task_name = parsed_task.title
                    existing_rule.task_description = parsed_task.description or parsed_task.title
                    existing_rule.trigger_condition = trigger_conditions
                    existing_rule.updated_at = datetime.utcnow()
                else:
                    # Create new rule with SAME Bayesian initial weights as chat tasks
                    # This ensures calendar tasks participate in the same learning system
                    priority_weights = {
                        'high': 0.85,    # Same as chat high priority
                        'medium': 0.75,  # Same as chat medium priority
                        'low': 0.65      # Same as chat low priority
                    }
                    initial_weight = priority_weights.get(parsed_task.priority.value, 0.75)
                    
                    new_rule = TaskRuleDB(
                        task_name=parsed_task.title,
                        task_description=parsed_task.description or parsed_task.title,
                        trigger_condition=trigger_conditions,
                        current_probability_weight=initial_weight,
                        calendar_event_id=parsed_task.event_id,
                        is_active=1
                    )
                    db.add(new_rule)
                    tasks_generated += 1
                
                db.commit()
        
        except Exception as e:
            print(f"Error processing calendar event {event_data.event_id}: {e}")
            continue
    
    return CalendarSyncResponse(
        success=True,
        events_processed=len(request.events),
        events_created=events_created,
        events_updated=events_updated,
        tasks_generated=tasks_generated,
        message=f"Successfully synced {len(request.events)} calendar events"
    )


@app.get("/calendar/upcoming")
def get_upcoming_calendar_tasks(hours_ahead: int = 24, db: Session = Depends(get_db)):
    """
    Get upcoming calendar events that need reminders.
    Returns events within the specified time window that haven't been completed or dismissed.
    """
    now = datetime.utcnow()
    time_ahead = now + timedelta(hours=hours_ahead)
    
    upcoming_events = db.query(CalendarEventDB).filter(
        CalendarEventDB.start_time != None,
        CalendarEventDB.start_time >= now,
        CalendarEventDB.start_time <= time_ahead,
        CalendarEventDB.completed == 0,
        CalendarEventDB.dismissed == 0
    ).order_by(CalendarEventDB.start_time).all()
    
    return {
        'success': True,
        'count': len(upcoming_events),
        'events': [
            {
                'event_id': event.event_id,
                'title': event.title,
                'description': event.description,
                'start_time': event.start_time.isoformat() if event.start_time else None,
                'end_time': event.end_time.isoformat() if event.end_time else None,
                'priority': event.priority,
                'location': event.location,
                'optimal_reminder_time': event.optimal_reminder_time.isoformat() if event.optimal_reminder_time else None,
                'preparation_time_minutes': event.preparation_time_minutes,
                'travel_time_minutes': event.travel_time_minutes
            }
            for event in upcoming_events
        ]
    }


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


# ===================== NOTIFICATION DECISION ENDPOINT =====================

@app.post("/notification/decision", response_model=NotificationDecisionResponse)
def decide_notification(
    request: NotificationDecisionRequest,
    db: Session = Depends(get_db)
):
    """
    Deterministic notification decision endpoint using Bayesian inference.
    
    Algorithm:
    1. Extract context features and generate context key
    2. Query Beta distributions for all timing windows
    3. Apply Upper Confidence Bound (UCB) for exploration/exploitation
    4. Determine if current time aligns with optimal window
    5. Return notification decision with confidence and explanation
    
    Stateless: No state changes, only reads from database.
    Deterministic: Same input always produces same output.
    """
    from inference import BayesianTimingOptimizer
    
    # Initialize Bayesian optimizer
    optimizer = BayesianTimingOptimizer(db)
    
    # Get optimal timing using Bayesian inference
    timing_result = optimizer.get_optimal_timing(
        task_type=request.task_type,
        context=request.context
    )
    
    optimal_window = timing_result['timing_window']
    confidence = timing_result['confidence']
    meets_threshold = timing_result['meets_threshold']
    context_key = timing_result['context_key']
    all_windows = timing_result['all_windows']
    
    # Decision logic: Notify now if confidence meets threshold
    # For scheduled tasks, check if we're within the optimal window
    notify_now = False
    suggested_delay = None
    
    if request.task_scheduled_time:
        # Fixed-time task: calculate minutes until task
        time_until_task = (request.task_scheduled_time - datetime.utcnow()).total_seconds() / 60
        
        if time_until_task < 0:
            # Task time has passed
            notify_now = False
            suggested_delay = None
            decision_reason = "Task scheduled time has passed"
        elif time_until_task <= optimal_window + 5:  # 5-minute tolerance
            # We're within the optimal notification window
            if meets_threshold:
                notify_now = True
                decision_reason = f"Within optimal {optimal_window}-minute window with {confidence:.1%} confidence"
            else:
                notify_now = False
                suggested_delay = max(0, int(time_until_task - optimal_window))
                decision_reason = f"Confidence ({confidence:.1%}) below threshold, waiting for better timing"
        else:
            # Too early - suggest delay
            notify_now = False
            suggested_delay = int(time_until_task - optimal_window)
            decision_reason = f"Too early - {int(time_until_task)} minutes until task, optimal window is {optimal_window} minutes"
    else:
        # Flexible task: notify if confidence is high enough
        if meets_threshold:
            notify_now = True
            decision_reason = f"Flexible task with {confidence:.1%} confidence (meets threshold)"
        else:
            notify_now = False
            # For flexible tasks, suggest checking again at a better time
            # Find the next best window
            sorted_windows = sorted(all_windows, key=lambda x: x['confidence'], reverse=True)
            next_best_window = sorted_windows[1] if len(sorted_windows) > 1 else sorted_windows[0]
            suggested_delay = next_best_window['window']
            decision_reason = f"Confidence ({confidence:.1%}) below threshold, try again in {suggested_delay} minutes"
    
    # Extract decision factors
    context_parts = context_key.split('_')
    decision_factors = {
        'activity': context_parts[0] if len(context_parts) > 0 else 'unknown',
        'time_of_day': context_parts[1] if len(context_parts) > 1 else 'unknown',
        'day_type': context_parts[2] if len(context_parts) > 2 else 'unknown',
        'location': context_parts[3] if len(context_parts) > 3 else 'unknown',
        'evidence_strength': all_windows[0]['evidence_strength'] if all_windows else 0,
        'priority': request.priority,
        'task_type': 'fixed' if request.task_scheduled_time else 'flexible'
    }
    
    # Build comprehensive explanation
    explanation_parts = [decision_reason]
    
    # Add context description
    explanation_parts.append(
        f"Context: {decision_factors['activity'].lower()} on {decision_factors['day_type']} {decision_factors['time_of_day']} at {decision_factors['location']}"
    )
    
    # Add evidence strength
    if decision_factors['evidence_strength'] == 0:
        explanation_parts.append("⚠️ No historical data - using uniform prior")
    elif decision_factors['evidence_strength'] < 5:
        explanation_parts.append(f"📊 Limited data ({decision_factors['evidence_strength']} samples)")
    else:
        explanation_parts.append(f"✓ Well-calibrated ({decision_factors['evidence_strength']} samples)")
    
    # Add priority consideration
    if request.priority == 'high':
        explanation_parts.append("🔴 High priority - bias toward notification")
    
    explanation = " • ".join(explanation_parts)
    
    # Simplify timing options for response
    simplified_windows = [
        {
            'window': w['window'],
            'confidence': w['confidence'],
            'uncertainty': w['uncertainty'],
            'evidence_strength': w['evidence_strength']
        }
        for w in all_windows
    ]
    
    return NotificationDecisionResponse(
        notify_now=notify_now,
        confidence=confidence,
        optimal_timing_window=optimal_window,
        suggested_delay_minutes=suggested_delay,
        explanation=explanation,
        context_key=context_key,
        all_timing_options=simplified_windows,
        decision_factors=decision_factors
    )


# ===================== BAYESIAN LEARNING ENDPOINTS =====================

@app.post("/learning/feedback")
def submit_learning_feedback(
    task_id: int,
    task_type: str,
    context: UserContextSchema,
    timing_window: int,
    feedback: str,
    db: Session = Depends(get_db)
):
    """
    Enhanced feedback endpoint with Bayesian learning.
    
    Updates Beta distributions for timing optimization.
    
    Args:
        task_id: ID of the task rule
        task_type: Type of task
        context: User's context when feedback was given
        timing_window: Minutes before task the notification was sent
        feedback: "accept" or "reject"
    """
    learning_service = LearningService(db)
    
    result = learning_service.record_feedback(
        task_id=task_id,
        task_type=task_type,
        context=context,
        timing_window=timing_window,
        feedback=feedback
    )
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result.get('error', 'Feedback recording failed'))
    
    return result


@app.get("/learning/summary")
def get_learning_summary(
    task_type: str = None,
    context_key: str = None,
    min_feedback_count: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get summary of all learned Beta distributions.
    
    Query params:
        task_type: Filter by specific task type
        context_key: Filter by specific context
        min_feedback_count: Minimum feedback samples to include
    """
    learning_service = LearningService(db)
    
    summary = learning_service.get_learning_summary(
        task_type=task_type,
        context_key=context_key,
        min_feedback_count=min_feedback_count
    )
    
    return summary


@app.post("/learning/explanation")
def get_learning_explanation(
    task_type: str,
    context: UserContextSchema,
    db: Session = Depends(get_db)
):
    """
    Get detailed explanation of learned behavior for a task in given context.
    
    Shows:
    - What the system has learned
    - Confidence levels for different timing windows
    - How many feedback samples were collected
    - Recommended timing window
    """
    learning_service = LearningService(db)
    
    explanation = learning_service.get_explanation_data(
        task_type=task_type,
        context=context
    )
    
    return explanation


@app.get("/learning/feedback-history")
def get_learning_feedback_history(
    task_id: int = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Get recent feedback history for analysis.
    
    Query params:
        task_id: Filter by specific task
        limit: Maximum number of records (default: 20)
    """
    learning_service = LearningService(db)
    
    history = learning_service.get_recent_feedback_history(
        task_id=task_id,
        limit=limit
    )
    
    return {
        "total": len(history),
        "history": history
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
