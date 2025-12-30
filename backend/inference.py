"""
Bayesian Inference Engine with Beta Distributions
Uses probabilistic modeling to optimize notification timing and task suggestions
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from models import (
    TaskRuleDB, UserContextSchema, InferredTask, 
    BayesianTimingParametersDB, FeedbackLogDB, CalendarEventDB
)
import re
import math

# Import A* search algorithm for optimal task scheduling
from search import TaskCandidate, TaskOption, optimize_schedule


class BayesianTimingOptimizer:
    """
    Bayesian inference for optimal notification timing using Beta distributions.
    
    For each (task_type, context, timing_window), we maintain a Beta distribution:
    - alpha: number of acceptances + 1 (prior)
    - beta: number of rejections/ignores + 1 (prior)
    - confidence = alpha / (alpha + beta)
    """
    
    TIMING_WINDOWS = [60, 30, 10]  # Minutes before task
    CONFIDENCE_THRESHOLD = 0.6
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def get_optimal_timing(
        self, 
        task_type: str, 
        context: UserContextSchema
    ) -> Dict[str, Any]:
        """
        Determine the optimal timing window for a notification.
        
        Returns:
        - timing_window: best time to notify (in minutes before task)
        - confidence: Bayesian probability estimate
        - explanation: human-readable reasoning
        - all_windows: details for all timing windows
        """
        context_key = self._generate_context_key(context)
        
        timing_options = []
        
        for window in self.TIMING_WINDOWS:
            params = self._get_or_create_parameters(task_type, context_key, window)
            
            # Calculate Bayesian confidence (posterior mean of Beta distribution)
            confidence = params.alpha / (params.alpha + params.beta)
            
            # Calculate uncertainty (variance of Beta distribution)
            total = params.alpha + params.beta
            variance = (params.alpha * params.beta) / (total**2 * (total + 1))
            uncertainty = math.sqrt(variance)
            
            timing_options.append({
                'window': window,
                'confidence': round(confidence, 3),
                'uncertainty': round(uncertainty, 3),
                'alpha': params.alpha,
                'beta': params.beta,
                'total_triggers': params.total_triggers,
                'evidence_strength': total - 2  # Subtract prior
            })
        
        # Select window with highest confidence (exploration vs exploitation)
        # Use Upper Confidence Bound (UCB) for exploration bonus
        best_option = max(
            timing_options, 
            key=lambda x: x['confidence'] + 0.5 * x['uncertainty']  # UCB exploration
        )
        
        explanation = self._generate_explanation(
            best_option, 
            timing_options, 
            context_key,
            task_type
        )
        
        return {
            'timing_window': best_option['window'],
            'confidence': best_option['confidence'],
            'meets_threshold': best_option['confidence'] >= self.CONFIDENCE_THRESHOLD,
            'explanation': explanation,
            'all_windows': timing_options,
            'context_key': context_key
        }
    
    def update_from_feedback(
        self, 
        task_type: str, 
        context_key: str, 
        timing_window: int, 
        accepted: bool
    ) -> Dict[str, Any]:
        """
        Update Beta distribution parameters based on user feedback.
        
        - If accepted: alpha += 1
        - If rejected/ignored: beta += 1
        """
        params = self._get_or_create_parameters(task_type, context_key, timing_window)
        
        old_alpha = params.alpha
        old_beta = params.beta
        old_confidence = old_alpha / (old_alpha + old_beta)
        
        if accepted:
            params.alpha += 1
        else:
            params.beta += 1
        
        params.total_triggers += 1
        params.last_updated = datetime.utcnow()
        
        self.db.commit()
        
        new_confidence = params.alpha / (params.alpha + params.beta)
        
        return {
            'success': True,
            'task_type': task_type,
            'context_key': context_key,
            'timing_window': timing_window,
            'old_confidence': round(old_confidence, 3),
            'new_confidence': round(new_confidence, 3),
            'alpha': params.alpha,
            'beta': params.beta,
            'feedback': 'accepted' if accepted else 'rejected'
        }
    
    def _get_or_create_parameters(
        self, 
        task_type: str, 
        context_key: str, 
        timing_window: int
    ) -> BayesianTimingParametersDB:
        """Retrieve or initialize Beta distribution parameters"""
        params = self.db.query(BayesianTimingParametersDB).filter(
            BayesianTimingParametersDB.task_type == task_type,
            BayesianTimingParametersDB.context_key == context_key,
            BayesianTimingParametersDB.timing_window == timing_window
        ).first()
        
        if not params:
            # Initialize with optimistic prior: Beta(4, 2)
            # This gives initial confidence of 66% (4/6)
            # Allows new tasks to show while still learning from feedback
            params = BayesianTimingParametersDB(
                task_type=task_type,
                context_key=context_key,
                timing_window=timing_window,
                alpha=4.0,
                beta=2.0,
                total_triggers=0
            )
            self.db.add(params)
            self.db.commit()
            self.db.refresh(params)
        
        return params
    
    def _generate_context_key(self, context: UserContextSchema) -> str:
        """
        Generate a context signature for grouping similar situations.
        
        Example: "IN_VEHICLE_morning_weekday"
        """
        activity = context.activity_type.upper()
        
        # Time of day classification
        hour = context.timestamp.hour
        if 5 <= hour < 12:
            time_period = "morning"
        elif 12 <= hour < 17:
            time_period = "afternoon"
        elif 17 <= hour < 21:
            time_period = "evening"
        else:
            time_period = "night"
        
        # Day type
        weekday = context.timestamp.weekday()
        day_type = "weekday" if weekday < 5 else "weekend"
        
        # Location component
        location = context.location_vector or "unknown"
        
        # Combine into signature
        context_key = f"{activity}_{time_period}_{day_type}_{location}"
        
        return context_key
    
    def _generate_explanation(
        self, 
        best_option: Dict[str, Any], 
        all_options: List[Dict[str, Any]], 
        context_key: str,
        task_type: str
    ) -> str:
        """Generate human-readable explanation of the timing decision"""
        window = best_option['window']
        conf = best_option['confidence']
        evidence = best_option['evidence_strength']
        
        explanation_parts = []
        
        # Main decision
        explanation_parts.append(
            f"Optimal timing: {window} minutes before task (confidence: {conf:.1%})"
        )
        
        # Evidence strength
        if evidence == 0:
            explanation_parts.append(
                "⚠️ No historical data yet - using initial estimate"
            )
        elif evidence < 5:
            explanation_parts.append(
                f"📊 Limited data ({evidence} prior interactions) - still learning"
            )
        else:
            explanation_parts.append(
                f"✓ Based on {evidence} historical interactions"
            )
        
        # Context description
        context_parts = context_key.split('_')
        if len(context_parts) >= 3:
            activity = context_parts[0].replace('_', ' ').lower()
            time_period = context_parts[1]
            day_type = context_parts[2]
            explanation_parts.append(
                f"Context: {activity} on {day_type} {time_period}"
            )
        
        # Comparison with other windows
        sorted_options = sorted(all_options, key=lambda x: x['confidence'], reverse=True)
        if len(sorted_options) > 1:
            second_best = sorted_options[1]
            if abs(best_option['confidence'] - second_best['confidence']) < 0.1:
                explanation_parts.append(
                    f"⚖️ Close alternative: {second_best['window']} min "
                    f"(confidence: {second_best['confidence']:.1%})"
                )
        
        return " • ".join(explanation_parts)


class InferenceEngine:
    """
    Enhanced inference engine with Bayesian timing optimization and A* search.
    Evaluates task rules against context and determines optimal notification timing.
    Now includes A* branch-and-bound search for globally optimal scheduling.
    """
    
    CONFIDENCE_THRESHOLD = 0.6
    
    def __init__(self, db_session: Session, enable_search: bool = True):
        self.db = db_session
        self.timing_optimizer = BayesianTimingOptimizer(db_session)
        self.enable_search = enable_search  # Toggle A* search optimization
    
    def infer_tasks(self, context: UserContextSchema) -> List[InferredTask]:
        """
        Main inference: Evaluate rules and optimize timing for each suggestion.
        
        Returns tasks that:
        1. Match context conditions
        2. Exceed confidence threshold (60%)
        3. Have optimal timing determined by Bayesian inference
        4. Include calendar events at appropriate reminder times (priority-aware)
        """
        active_rules = self.db.query(TaskRuleDB).filter(
            TaskRuleDB.is_active == 1
        ).all()
        
        suggested_tasks = []
        
        # First, process regular task rules
        for rule in active_rules:
            # Skip calendar-based rules - they will be handled separately
            if rule.calendar_event_id:
                continue
                
            match_result = self._evaluate_rule(rule, context)
            
            if match_result["matches"]:
                # Base confidence from rule matching
                base_confidence = rule.current_probability_weight * match_result["match_score"]
                
                if base_confidence >= self.CONFIDENCE_THRESHOLD:
                    # Get optimal timing using Bayesian inference
                    timing_result = self.timing_optimizer.get_optimal_timing(
                        task_type=rule.task_name,
                        context=context
                    )
                    
                    # Only check timing threshold if base confidence is moderate
                    # If base confidence is high (>= 70%), show the task regardless of timing confidence
                    should_suggest = (
                        base_confidence >= 0.70 or 
                        timing_result['meets_threshold']
                    )
                    
                    if should_suggest:
                        reasoning_parts = [
                            match_result["reasoning"],
                            timing_result['explanation']
                        ]
                        
                        # Collect all timing options for A* search
                        timing_options = []
                        for tw_option in timing_result['all_windows']:
                            timing_options.append({
                                'window': tw_option['window'],
                                'confidence': tw_option['confidence'],
                                'expected_reward': base_confidence * tw_option['confidence']
                            })
                        
                        task = InferredTask(
                            rule_id=rule.id,
                            task_name=rule.task_name,
                            task_description=rule.task_description,
                            confidence=round(base_confidence, 2),
                            reasoning=" | ".join(reasoning_parts),
                            matched_conditions=match_result["matched_conditions"],
                            optimal_timing_window=timing_result['timing_window'],
                            timing_confidence=timing_result['confidence'],
                            timing_options=timing_options  # Store all options for search
                        )
                        suggested_tasks.append(task)
        
        # Now, process calendar events with priority-aware reminders
        calendar_tasks = self._get_calendar_reminders(context)
        suggested_tasks.extend(calendar_tasks)
        
        # Apply A* search optimization if enabled
        if self.enable_search and len(suggested_tasks) > 1:
            suggested_tasks = self._apply_search_optimization(suggested_tasks)
        else:
            # Fallback: Sort by combined confidence (rule confidence × timing confidence)
            suggested_tasks.sort(
                key=lambda x: x.confidence * (x.timing_confidence or 1.0), 
                reverse=True
            )
        
        return suggested_tasks
    
    def _get_calendar_reminders(self, context: UserContextSchema) -> List[InferredTask]:
        """
        Get calendar event reminders based on priority-aware timing strategy:
        - HIGH priority: Remind throughout the day, multiple times until completion
        - MEDIUM priority: Wait for free time (when user is STILL at home/work)
        - LOW priority: Only suggest when context is perfect and close to event time
        """
        now = datetime.utcnow()
        calendar_tasks = []
        
        # Get upcoming events (next 24 hours)
        upcoming_events = self.db.query(CalendarEventDB).filter(
            CalendarEventDB.start_time != None,
            CalendarEventDB.start_time >= now,
            CalendarEventDB.start_time <= now + timedelta(hours=24),
            CalendarEventDB.completed == 0,
            CalendarEventDB.dismissed == 0
        ).all()
        
        for event in upcoming_events:
            should_remind, confidence, reasoning = self._should_remind_about_event(event, context, now)
            
            if should_remind:
                # Find associated rule for this calendar event
                rule = self.db.query(TaskRuleDB).filter(
                    TaskRuleDB.calendar_event_id == event.event_id
                ).first()
                
                if rule:
                    # Calculate time until event
                    time_until = event.start_time - now
                    minutes_until = int(time_until.total_seconds() / 60)
                    
                    # Create timing options for calendar events
                    # Use standard timing windows relative to event time
                    timing_options = []
                    for window_mins in [60, 30, 15, 10]:
                        if minutes_until >= window_mins:
                            timing_options.append({
                                'window': window_mins,
                                'confidence': confidence * (1.0 - (window_mins / 120)),  # Prefer closer timings
                                'expected_reward': confidence * (1.0 - (window_mins / 120))
                            })
                    
                    # If no standard windows fit, use current time
                    if not timing_options:
                        timing_options = [{
                            'window': minutes_until,
                            'confidence': confidence,
                            'expected_reward': confidence
                        }]
                    
                    task = InferredTask(
                        rule_id=rule.id,
                        task_name=event.title,
                        task_description=event.description or event.title,
                        confidence=confidence,
                        reasoning=reasoning,
                        matched_conditions={
                            'calendar_event': True,
                            'priority': event.priority,
                            'minutes_until': minutes_until,
                            'start_time': event.start_time.isoformat()
                        },
                        optimal_timing_window=minutes_until,
                        timing_confidence=confidence,
                        timing_options=timing_options  # Add timing options for A* search
                    )
                    calendar_tasks.append(task)
        
        return calendar_tasks
    
    def _should_remind_about_event(
        self, 
        event: CalendarEventDB, 
        context: UserContextSchema,
        now: datetime
    ) -> Tuple[bool, float, str]:
        """
        Priority-aware reminder logic for calendar events.
        
        Returns: (should_remind, confidence, reasoning)
        """
        time_until = event.start_time - now
        minutes_until = int(time_until.total_seconds() / 60)
        hours_until = minutes_until / 60
        
        # Get optimal reminder time if calculated
        optimal_reminder_time = event.optimal_reminder_time
        
        # HIGH PRIORITY: Remind aggressively until completion
        if event.priority == 'high':
            # Remind if:
            # 1. Past optimal reminder time
            # 2. Within 24 hours of event
            # 3. Not reminded too recently (at least 2 hours ago, or approaching event time)
            
            if optimal_reminder_time and now >= optimal_reminder_time:
                # Increase frequency as event approaches
                if minutes_until <= 30:
                    min_interval_hours = 0.25  # Every 15 minutes when very close
                elif minutes_until <= 120:
                    min_interval_hours = 0.5  # Every 30 minutes when close
                else:
                    min_interval_hours = 2  # Every 2 hours otherwise
                
                # Check last reminder time
                if event.last_reminded_at:
                    time_since_reminder = now - event.last_reminded_at
                    if time_since_reminder.total_seconds() / 3600 < min_interval_hours:
                        return False, 0.0, "Reminded too recently"
                
                # Update last reminder time
                event.last_reminded_at = now
                event.reminder_count += 1
                self.db.commit()
                
                confidence = 0.95
                reasoning = f"⚠️ HIGH PRIORITY: {event.title} in {self._format_time_until(minutes_until)}. "
                
                if event.preparation_time_minutes:
                    reasoning += f"Allow {event.preparation_time_minutes} min for preparation. "
                if event.travel_time_minutes:
                    reasoning += f"Travel time: {event.travel_time_minutes} min. "
                
                return True, confidence, reasoning
        
        # MEDIUM PRIORITY: Wait for free time
        elif event.priority == 'medium':
            # Remind if:
            # 1. At or past optimal reminder time
            # 2. User appears to be in a good state (STILL, at home/work)
            # 3. Not reminded in last 3 hours
            
            if optimal_reminder_time and now >= optimal_reminder_time:
                # Check if user is in "free time" context
                is_free = (
                    context.activity_type.upper() == 'STILL' and
                    context.location_vector in ['home', 'work']
                )
                
                if is_free or minutes_until <= 60:  # Force reminder if within 1 hour
                    # Check last reminder
                    if event.last_reminded_at:
                        time_since_reminder = now - event.last_reminded_at
                        if time_since_reminder.total_seconds() / 3600 < 3:
                            return False, 0.0, "Reminded too recently"
                    
                    event.last_reminded_at = now
                    event.reminder_count += 1
                    self.db.commit()
                    
                    confidence = 0.75 if is_free else 0.65
                    reasoning = f"📅 {event.title} in {self._format_time_until(minutes_until)}. "
                    
                    if is_free:
                        reasoning += "Good time to prepare. "
                    else:
                        reasoning += "Event approaching soon! "
                    
                    return True, confidence, reasoning
        
        # LOW PRIORITY: Only suggest when context is perfect
        else:  # priority == 'low'
            # Remind if:
            # 1. At optimal reminder time (or close to event)
            # 2. User is in perfect context (matching suggested contexts)
            # 3. Only remind once
            
            if event.reminder_count > 0:
                return False, 0.0, "Already reminded once (low priority)"
            
            # Only remind if within the optimal window
            if optimal_reminder_time:
                time_diff = abs((optimal_reminder_time - now).total_seconds() / 60)
                if time_diff > 15:  # Not within 15 minutes of optimal time
                    return False, 0.0, "Not at optimal reminder time yet"
            
            # Check if context matches suggestions
            context_matches = False
            if event.suggested_contexts:
                for suggested in event.suggested_contexts:
                    if suggested.lower() in str(context.location_vector).lower():
                        context_matches = True
                        break
            
            # Force reminder if very close to event, regardless of context
            if minutes_until <= 30 or context_matches:
                event.last_reminded_at = now
                event.reminder_count += 1
                self.db.commit()
                
                confidence = 0.60
                reasoning = f"📝 Reminder: {event.title} in {self._format_time_until(minutes_until)}"
                
                return True, confidence, reasoning
        
        return False, 0.0, "Not time to remind yet"
    
    def _format_time_until(self, minutes: int) -> str:
        """Format time until event in human-readable form"""
        if minutes < 60:
            return f"{minutes} min"
        elif minutes < 1440:  # Less than a day
            hours = minutes / 60
            if hours < 2:
                return f"~1 hour"
            return f"~{int(hours)} hours"
        else:
            days = minutes / 1440
            return f"~{int(days)} days"
    
    def _apply_search_optimization(self, tasks: List[InferredTask]) -> List[InferredTask]:
        """
        Apply A* branch-and-bound search to find globally optimal task schedule.
        
        This method:
        1. Converts InferredTask list to TaskCandidate list
        2. Runs A* search to find optimal timing choices
        3. Updates tasks with chosen timing windows
        4. Adds search metadata to each task
        5. Returns tasks sorted by expected reward
        
        Args:
            tasks: List of inferred tasks with timing options
            
        Returns:
            Optimized list of tasks with chosen timing windows and search metadata
        """
        try:
            # Convert tasks to search candidates
            candidates = []
            for task in tasks:
                if not task.timing_options or len(task.timing_options) == 0:
                    # Task has no timing options (e.g., calendar event), use default
                    options = [TaskOption(
                        timing_window_minutes=task.optimal_timing_window or 30,
                        expected_reward=task.confidence,
                        context_match_score=1.0
                    )]
                else:
                    # Convert timing options to TaskOption objects
                    options = []
                    for tw_opt in task.timing_options:
                        options.append(TaskOption(
                            timing_window_minutes=tw_opt['window'],
                            expected_reward=tw_opt['expected_reward'],
                            context_match_score=tw_opt.get('confidence', 1.0)
                        ))
                
                candidates.append(TaskCandidate(
                    task_id=task.rule_id,
                    title=task.task_name,
                    priority_weight=task.confidence,
                    options=options
                ))
            
            # Run A* search optimization
            search_result = optimize_schedule(
                candidates=candidates,
                max_nodes=10000,
                enable_pruning=True
            )
            
            # Create a map of task_id -> chosen timing window
            chosen_timings = {task_id: window for task_id, window in search_result.schedule}
            
            # Update tasks with search results
            updated_tasks = []
            for task in tasks:
                # Get chosen timing for this task
                chosen_window = chosen_timings.get(task.rule_id)
                
                if chosen_window is not None:
                    # Update the task with chosen timing
                    task.optimal_timing_window = chosen_window
                    
                    # Find the confidence for this chosen window
                    if task.timing_options:
                        for tw_opt in task.timing_options:
                            if tw_opt['window'] == chosen_window:
                                task.timing_confidence = tw_opt.get('confidence', task.timing_confidence)
                                break
                    
                    # Add search metadata
                    task.search_metadata = {
                        'search_algorithm': 'A* branch-and-bound',
                        'total_expected_reward': round(search_result.total_expected_reward, 3),
                        'nodes_explored': search_result.nodes_explored,
                        'search_completed': search_result.search_completed,
                        'search_time_ms': round(search_result.search_time_ms, 2),
                        'optimization_quality': 'optimal' if search_result.search_completed else 'greedy_fallback',
                        'chosen_timing_window': chosen_window
                    }
                    
                    updated_tasks.append(task)
                # If chosen_window is None, task was skipped by search (low priority)
            
            # Sort by expected reward (confidence × timing_confidence)
            updated_tasks.sort(
                key=lambda x: x.confidence * (x.timing_confidence or 1.0),
                reverse=True
            )
            
            return updated_tasks
            
        except Exception as e:
            # Fallback: If search fails, return tasks with original ordering
            print(f"⚠️  A* search failed: {e}. Falling back to greedy sorting.")
            tasks.sort(
                key=lambda x: x.confidence * (x.timing_confidence or 1.0),
                reverse=True
            )
            return tasks
    
    def _extract_scheduled_time(self, trigger_condition: dict) -> Optional[datetime]:
        """Extract scheduled time from trigger condition if it exists"""
        if not trigger_condition or "time_range" not in trigger_condition:
            return None
        
        try:
            time_range = trigger_condition["time_range"]
            # Parse start time from range (e.g., "16:00-18:00" -> 17:00 midpoint)
            start_str = time_range.split("-")[0].strip()
            end_str = time_range.split("-")[1].strip()
            
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()
            
            # Calculate midpoint as the scheduled time
            start_minutes = start_time.hour * 60 + start_time.minute
            end_minutes = end_time.hour * 60 + end_time.minute
            mid_minutes = (start_minutes + end_minutes) // 2
            
            scheduled_hour = mid_minutes // 60
            scheduled_minute = mid_minutes % 60
            
            # Create datetime with today's date
            from datetime import datetime as dt
            now = dt.now()
            scheduled_dt = now.replace(hour=scheduled_hour, minute=scheduled_minute, second=0, microsecond=0)
            
            return scheduled_dt
        except Exception:
            return None
    
    def _evaluate_rule(self, rule: TaskRuleDB, context: UserContextSchema) -> Dict[str, Any]:
        """
        Evaluate if a rule's trigger conditions match the current context.
        Returns match status, score, reasoning, and matched conditions.
        """
        trigger = rule.trigger_condition
        matched_conditions = {}
        reasons = []
        total_checks = 0
        successful_checks = 0
        
        # Activity check
        if "activity" in trigger:
            total_checks += 1
            expected_activity = trigger["activity"].upper()
            if context.activity_type.upper() == expected_activity:
                successful_checks += 1
                matched_conditions["activity"] = context.activity_type
                reasons.append(f"You are {self._humanize_activity(context.activity_type)}")
        
        # Time range check
        if "time_range" in trigger:
            total_checks += 1
            if self._is_time_in_range(trigger["time_range"], context.timestamp):
                successful_checks += 1
                matched_conditions["time"] = context.timestamp.strftime("%H:%M")
                reasons.append(f"Time is {context.timestamp.strftime('%I:%M %p')}")
        
        # Location check
        if "location_vector" in trigger:
            total_checks += 1
            if context.location_vector and context.location_vector.lower() == trigger["location_vector"].lower():
                successful_checks += 1
                matched_conditions["location_vector"] = context.location_vector
                reasons.append(f"Location: {context.location_vector.replace('_', ' ').title()}")
        
        # Bluetooth car check
        if "car_bluetooth" in trigger:
            total_checks += 1
            if trigger["car_bluetooth"] == context.is_connected_to_car_bluetooth:
                successful_checks += 1
                matched_conditions["car_bluetooth"] = context.is_connected_to_car_bluetooth
                if context.is_connected_to_car_bluetooth:
                    reasons.append("Connected to car Bluetooth")
        
        # WiFi check
        if "wifi_ssid" in trigger:
            total_checks += 1
            expected_wifi = trigger["wifi_ssid"]
            
            if expected_wifi in ["disconnected", "not_connected", None]:
                if not context.wifi_ssid or context.wifi_ssid == "":
                    successful_checks += 1
                    matched_conditions["wifi_ssid"] = "disconnected"
                    reasons.append("WiFi disconnected")
            elif context.wifi_ssid and context.wifi_ssid.lower() == expected_wifi.lower():
                successful_checks += 1
                matched_conditions["wifi_ssid"] = context.wifi_ssid
                reasons.append(f"Connected to {context.wifi_ssid}")
        
        # Speed check
        if "min_speed" in trigger:
            total_checks += 1
            if context.speed >= trigger["min_speed"]:
                successful_checks += 1
                matched_conditions["speed"] = context.speed
                reasons.append(f"Speed: {context.speed:.1f} km/h")
        
        # Custom conditions
        if "custom" in trigger:
            for key, expected_value in trigger["custom"].items():
                if context.additional_data and key in context.additional_data:
                    total_checks += 1
                    if context.additional_data[key] == expected_value:
                        successful_checks += 1
                        matched_conditions[key] = expected_value
                        reasons.append(f"{key.replace('_', ' ').title()}: {expected_value}")
        
        # Calculate match score
        match_score = successful_checks / total_checks if total_checks > 0 else 0.0
        matches = match_score >= 0.8  # 80% of conditions must match
        
        reasoning = " • ".join(reasons) if reasons else "Conditions not met"
        
        return {
            "matches": matches,
            "match_score": match_score,
            "reasoning": reasoning,
            "matched_conditions": matched_conditions
        }
    
    def _is_time_in_range(self, time_range_str: str, current_time: datetime) -> bool:
        """Check if current time falls within specified range"""
        try:
            start_str, end_str = time_range_str.split("-")
            start_time = datetime.strptime(start_str.strip(), "%H:%M").time()
            end_time = datetime.strptime(end_str.strip(), "%H:%M").time()
            current = current_time.time()
            
            if start_time <= end_time:
                return start_time <= current <= end_time
            else:  # Crosses midnight
                return current >= start_time or current <= end_time
        except Exception:
            return False
    
    def _humanize_activity(self, activity: str) -> str:
        """Convert activity codes to human-readable text"""
        activity_map = {
            "STILL": "stationary",
            "WALKING": "walking",
            "RUNNING": "running",
            "IN_VEHICLE": "driving",
            "ON_BICYCLE": "cycling",
            "ON_FOOT": "on foot"
        }
        return activity_map.get(activity.upper(), activity.lower())
    
    def apply_feedback(self, rule_id: int, outcome: str, context: Optional[UserContextSchema] = None) -> Dict[str, Any]:
        """
        Apply reinforcement learning to both:
        1. Rule probability weights (existing system)
        2. Bayesian timing parameters (new Bayesian system)
        """
        rule = self.db.query(TaskRuleDB).filter(TaskRuleDB.id == rule_id).first()
        
        if not rule:
            return {"success": False, "message": "Rule not found"}
        
        # Update rule probability weight (existing RL)
        old_weight = rule.current_probability_weight
        
        if outcome == "positive":
            rule.current_probability_weight = min(1.0, old_weight + 0.05)
            adjustment = "increased"
            accepted = True
        elif outcome == "negative":
            rule.current_probability_weight = max(0.0, old_weight - 0.10)
            adjustment = "decreased"
            accepted = False
        else:
            return {"success": False, "message": "Invalid outcome. Use 'positive' or 'negative'"}
        
        rule.updated_at = datetime.utcnow()
        
        # Store feedback log
        feedback_log = FeedbackLogDB(
            rule_id=rule_id,
            user_action="accepted" if accepted else "rejected",
            context_snapshot=context.model_dump() if context else None,
            timestamp=datetime.utcnow()
        )
        self.db.add(feedback_log)
        
        result = {
            "success": True,
            "rule_id": rule_id,
            "task_name": rule.task_name,
            "old_weight": round(old_weight, 2),
            "new_weight": round(rule.current_probability_weight, 2),
            "adjustment": adjustment
        }
        
        # Update Bayesian timing parameters if context is provided
        if context:
            context_key = self.timing_optimizer._generate_context_key(context)
            
            # Update for the timing window that was actually used
            # For now, use default 30 minutes (in production, track which window was used)
            timing_window = 30  # This should be passed from the notification system
            
            bayesian_update = self.timing_optimizer.update_from_feedback(
                task_type=rule.task_name,
                context_key=context_key,
                timing_window=timing_window,
                accepted=accepted
            )
            
            result["bayesian_update"] = bayesian_update
        
        self.db.commit()
        
        result["message"] = (
            f"Rule '{rule.task_name}' probability {adjustment} from "
            f"{old_weight:.2f} to {rule.current_probability_weight:.2f}"
        )
        
        return result


class NaturalLanguageParser:
    """Enhanced NLP parser for converting user text into task rules"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def parse_with_confidence(self, user_input: str, current_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Parse natural language with detailed confidence scoring.
        Returns structured task data with confidence metrics.
        """
        user_lower = user_input.lower().strip()
        
        # Initialize response
        result = {
            "success": True,
            "confidence": 0.0,
            "parsed_task_name": None,
            "parsed_description": user_input,
            "parsed_time": None,
            "parsed_date": None,
            "parsed_location": None,
            "parsed_priority": "medium",
            "parsed_duration_minutes": None,
            "extraction_details": {},
            "confidence_breakdown": {},
            "requires_confirmation": True,
            "suggestions": [],
            "original_input": user_input
        }
        
        # Task name extraction with confidence
        task_result = self._extract_task_name(user_lower, user_input)
        result["parsed_task_name"] = task_result["name"]
        result["confidence_breakdown"]["task_name"] = task_result["confidence"]
        result["extraction_details"]["task_name"] = task_result["explanation"]
        
        # Time extraction
        time_result = self._extract_time(user_lower)
        if time_result["found"]:
            result["parsed_time"] = time_result["time"]
            result["confidence_breakdown"]["time"] = time_result["confidence"]
            result["extraction_details"]["time"] = time_result["explanation"]
        
        # Date extraction
        date_result = self._extract_date(user_lower)
        if date_result["found"]:
            result["parsed_date"] = date_result["date"]
            result["confidence_breakdown"]["date"] = date_result["confidence"]
            result["extraction_details"]["date"] = date_result["explanation"]
        
        # Location extraction
        location_result = self._extract_location(user_lower)
        if location_result["found"]:
            result["parsed_location"] = location_result["location"]
            result["confidence_breakdown"]["location"] = location_result["confidence"]
            result["extraction_details"]["location"] = location_result["explanation"]
        
        # Priority inference
        priority_result = self._infer_priority(user_lower)
        result["parsed_priority"] = priority_result["priority"]
        result["confidence_breakdown"]["priority"] = priority_result["confidence"]
        result["extraction_details"]["priority"] = priority_result["explanation"]
        
        # Duration estimation
        duration_result = self._estimate_duration(result["parsed_task_name"], user_lower)
        if duration_result["found"]:
            result["parsed_duration_minutes"] = duration_result["duration"]
            result["confidence_breakdown"]["duration"] = duration_result["confidence"]
            result["extraction_details"]["duration"] = duration_result["explanation"]
        
        # Calculate overall confidence (weighted average)
        weights = {
            "task_name": 0.4,  # Most important
            "time": 0.15,
            "date": 0.1,
            "location": 0.1,
            "priority": 0.15,
            "duration": 0.1
        }
        
        total_confidence = 0.0
        total_weight = 0.0
        for field, weight in weights.items():
            if field in result["confidence_breakdown"]:
                total_confidence += result["confidence_breakdown"][field] * weight
                total_weight += weight
        
        result["confidence"] = round(total_confidence / total_weight if total_weight > 0 else 0.5, 3)
        
        # Add suggestions for low confidence fields
        if result["confidence_breakdown"].get("time", 1.0) < 0.7 and not result["parsed_time"]:
            result["suggestions"].append("When should this task be done?")
        if result["confidence_breakdown"].get("date", 1.0) < 0.7 and not result["parsed_date"]:
            result["suggestions"].append("Which day is this for?")
        if not result["parsed_location"] and "appointment" in user_lower:
            result["suggestions"].append("Where is this appointment?")
        
        # Decide if confirmation is needed
        result["requires_confirmation"] = result["confidence"] < 0.85
        
        return result
    
    def _extract_task_name(self, user_lower: str, original: str) -> Dict[str, Any]:
        """Extract task name with confidence score"""
        # Keyword mapping with confidence levels
        task_keywords = {
            "dentist": ("Dentist Appointment", 0.95),
            "doctor": ("Doctor Appointment", 0.95),
            "meeting": ("Meeting", 0.9),
            "call": ("Phone Call", 0.9),
            "email": ("Send Email", 0.9),
            "groceries": ("Buy Groceries", 0.95),
            "shopping": ("Shopping", 0.85),
            "gas": ("Get Fuel", 0.95),
            "fuel": ("Get Fuel", 0.95),
            "gym": ("Gym Workout", 0.95),
            "workout": ("Workout", 0.9),
            "pickup": ("Pickup Task", 0.85),
            "medicine": ("Take Medicine", 0.95),
            "medication": ("Take Medication", 0.95),
            "appointment": ("Appointment", 0.7),
            "remind": ("Reminder", 0.6),
            "task": ("Task", 0.5),
            "todo": ("Task", 0.5)
        }
        
        # Check for explicit task keywords
        for keyword, (name, confidence) in task_keywords.items():
            if keyword in user_lower:
                # Try to extract more specific name from context
                if keyword in ["call", "email"]:
                    # Extract target person/entity
                    patterns = [r'call\s+(\w+)', r'email\s+(\w+)']
                    for pattern in patterns:
                        match = re.search(pattern, user_lower)
                        if match:
                            target = match.group(1).capitalize()
                            return {
                                "name": f"{name} - {target}",
                                "confidence": confidence + 0.05,
                                "explanation": f"Found '{keyword}' and target '{target}'"
                            }
                
                return {
                    "name": name,
                    "confidence": confidence,
                    "explanation": f"Detected keyword '{keyword}'"
                }
        
        # Fallback: Use first few words
        words = original.split()[:3]
        task_name = " ".join(words).title()
        
        return {
            "name": task_name,
            "confidence": 0.4,
            "explanation": "No clear keywords, using first words"
        }
    
    def _extract_time(self, user_lower: str) -> Dict[str, Any]:
        """Extract time with confidence"""
        # Pattern for times like "5 PM", "17:00", "5:30 PM"
        patterns = [
            (r'(\d{1,2}):(\d{2})\s*(am|pm)', 0.95),  # "5:30 PM"
            (r'(\d{1,2})\s*(am|pm)', 0.9),  # "5 PM"
            (r'(\d{1,2}):(\d{2})', 0.85),  # "17:30"
        ]
        
        for pattern, confidence in patterns:
            match = re.search(pattern, user_lower)
            if match:
                groups = match.groups()
                
                if len(groups) == 3:  # Has am/pm
                    hour = int(groups[0])
                    minute = int(groups[1])
                    period = groups[2]
                    
                    if period == 'pm' and hour != 12:
                        hour += 12
                    elif period == 'am' and hour == 12:
                        hour = 0
                    
                    time_str = f"{hour:02d}:{minute:02d}"
                elif len(groups) == 2 and groups[1] in ['am', 'pm']:  # Hour with am/pm
                    hour = int(groups[0])
                    period = groups[1]
                    
                    if period == 'pm' and hour != 12:
                        hour += 12
                    elif period == 'am' and hour == 12:
                        hour = 0
                    
                    time_str = f"{hour:02d}:00"
                else:  # 24-hour format
                    hour = int(groups[0])
                    minute = int(groups[1])
                    time_str = f"{hour:02d}:{minute:02d}"
                
                return {
                    "found": True,
                    "time": time_str,
                    "confidence": confidence,
                    "explanation": f"Extracted time '{match.group(0)}' → {time_str}"
                }
        
        return {"found": False, "time": None, "confidence": 0.0, "explanation": "No time found"}
    
    def _extract_date(self, user_lower: str) -> Dict[str, Any]:
        """Extract date with confidence"""
        from datetime import datetime, timedelta
        
        today = datetime.now().date()
        
        # Relative dates
        if "tomorrow" in user_lower:
            date = today + timedelta(days=1)
            return {
                "found": True,
                "date": date.isoformat(),
                "confidence": 0.95,
                "explanation": "'tomorrow' → next day"
            }
        elif "today" in user_lower:
            return {
                "found": True,
                "date": today.isoformat(),
                "confidence": 0.95,
                "explanation": "'today' → current day"
            }
        elif "next week" in user_lower:
            date = today + timedelta(days=7)
            return {
                "found": True,
                "date": date.isoformat(),
                "confidence": 0.8,
                "explanation": "'next week' → 7 days ahead"
            }
        
        # Day names
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day in enumerate(days):
            if day in user_lower:
                # Find next occurrence
                current_weekday = today.weekday()
                days_ahead = (i - current_weekday) % 7
                if days_ahead == 0:
                    days_ahead = 7  # Next week if same day
                date = today + timedelta(days=days_ahead)
                return {
                    "found": True,
                    "date": date.isoformat(),
                    "confidence": 0.85,
                    "explanation": f"'{day}' → next {day.title()}"
                }
        
        # Explicit date patterns (MM/DD, DD/MM, etc.)
        date_patterns = [
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', 0.95),  # MM/DD/YYYY
            (r'(\d{1,2})/(\d{1,2})', 0.8),  # MM/DD (assume current year)
        ]
        
        for pattern, confidence in date_patterns:
            match = re.search(pattern, user_lower)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                else:
                    month, day = int(groups[0]), int(groups[1])
                    year = today.year
                
                try:
                    date = datetime(year, month, day).date()
                    return {
                        "found": True,
                        "date": date.isoformat(),
                        "confidence": confidence,
                        "explanation": f"Parsed date '{match.group(0)}'"
                    }
                except ValueError:
                    pass
        
        return {"found": False, "date": None, "confidence": 0.0, "explanation": "No date found"}
    
    def _extract_location(self, user_lower: str) -> Dict[str, Any]:
        """Extract location context"""
        location_keywords = {
            "on the way home": ("leaving_work", 0.9),
            "going home": ("leaving_work", 0.85),
            "on the way to work": ("leaving_home", 0.9),
            "at home": ("home", 0.95),
            "at work": ("work", 0.95),
            "at office": ("work", 0.9),
            "at the gym": ("gym", 0.95),
            "downtown": ("downtown", 0.8),
            "nearby": ("near_current", 0.7)
        }
        
        for phrase, (location, confidence) in location_keywords.items():
            if phrase in user_lower:
                return {
                    "found": True,
                    "location": location,
                    "confidence": confidence,
                    "explanation": f"Detected '{phrase}' → {location}"
                }
        
        return {"found": False, "location": None, "confidence": 0.0, "explanation": "No location found"}
    
    def _infer_priority(self, user_lower: str) -> Dict[str, Any]:
        """Infer task priority from language"""
        high_keywords = ["urgent", "asap", "important", "critical", "deadline", "must"]
        low_keywords = ["maybe", "sometime", "when free", "if possible", "optional"]
        
        for keyword in high_keywords:
            if keyword in user_lower:
                return {
                    "priority": "high",
                    "confidence": 0.85,
                    "explanation": f"Detected urgency keyword '{keyword}'"
                }
        
        for keyword in low_keywords:
            if keyword in user_lower:
                return {
                    "priority": "low",
                    "confidence": 0.8,
                    "explanation": f"Detected low-priority keyword '{keyword}'"
                }
        
        # Default to medium
        return {
            "priority": "medium",
            "confidence": 0.6,
            "explanation": "No priority indicators, defaulting to medium"
        }
    
    def _estimate_duration(self, task_name: Optional[str], user_lower: str) -> Dict[str, Any]:
        """Estimate task duration"""
        # Explicit duration patterns
        duration_pattern = r'(\d+)\s*(hour|hr|minute|min)'
        match = re.search(duration_pattern, user_lower)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            
            if 'hour' in unit or 'hr' in unit:
                minutes = value * 60
            else:
                minutes = value
            
            return {
                "found": True,
                "duration": minutes,
                "confidence": 0.95,
                "explanation": f"Explicit duration: {match.group(0)}"
            }
        
        # Estimate from task type
        if task_name:
            task_lower = task_name.lower()
            duration_estimates = {
                "call": (15, 0.7),
                "email": (10, 0.7),
                "meeting": (60, 0.6),
                "appointment": (45, 0.6),
                "dentist": (60, 0.75),
                "doctor": (45, 0.7),
                "gym": (90, 0.75),
                "workout": (60, 0.7),
                "groceries": (45, 0.7),
                "shopping": (60, 0.6)
            }
            
            for keyword, (duration, confidence) in duration_estimates.items():
                if keyword in task_lower:
                    return {
                        "found": True,
                        "duration": duration,
                        "confidence": confidence,
                        "explanation": f"Estimated from task type '{keyword}'"
                    }
        
        return {"found": False, "duration": None, "confidence": 0.0, "explanation": "No duration info"}
    
    def parse_user_input(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Parse natural language and create task rule with Bayesian timing"""
        user_message_lower = user_message.lower()
        
        # Task name extraction
        task_keywords = {
            "dentist": "Dentist Appointment",
            "doctor": "Doctor Appointment",
            "meeting": "Meeting",
            "groceries": "Buy Groceries",
            "gas": "Get Fuel",
            "fuel": "Get Fuel",
            "gym": "Go to Gym",
            "pickup": "Pickup Task",
            "call": "Make Phone Call",
            "medicine": "Take Medicine",
            "appointment": "Appointment"
        }
        
        task_name = "Custom Task"
        for keyword, name in task_keywords.items():
            if keyword in user_message_lower:
                task_name = name
                break
        
        # Time extraction
        time_pattern = r'(\d{1,2})\s*(am|pm|:)'
        time_match = re.search(time_pattern, user_message_lower)
        
        trigger_condition = {}
        
        # Location context
        if "on the way home" in user_message_lower or "going home" in user_message_lower:
            trigger_condition["location_vector"] = "leaving_work"
        elif "on the way to work" in user_message_lower:
            trigger_condition["location_vector"] = "leaving_home"
        elif "at home" in user_message_lower:
            trigger_condition["location_vector"] = "home"
        elif "at work" in user_message_lower or "at office" in user_message_lower:
            trigger_condition["location_vector"] = "work"
        
        # Time constraint
        if time_match:
            hour = int(time_match.group(1))
            period = time_match.group(2)
            
            if 'pm' in period and hour != 12:
                hour += 12
            elif 'am' in period and hour == 12:
                hour = 0
            
            start_hour = max(0, hour - 1) if hour > 0 else 23
            end_hour = min(23, hour + 1) if hour < 23 else 0
            trigger_condition["time_range"] = f"{start_hour:02d}:00-{end_hour:02d}:00"
        
        # Activity context
        if "driving" in user_message_lower or "car" in user_message_lower:
            trigger_condition["activity"] = "IN_VEHICLE"
        elif "walking" in user_message_lower:
            trigger_condition["activity"] = "WALKING"
        
        # Create task rule
        new_rule = TaskRuleDB(
            task_name=task_name,
            task_description=user_message,
            trigger_condition=trigger_condition,
            current_probability_weight=0.75,
            is_active=1
        )
        
        self.db.add(new_rule)
        self.db.commit()
        self.db.refresh(new_rule)
        
        return {
            "understood": True,
            "interpretation": f"I'll remind you about '{task_name}' when {self._describe_trigger(trigger_condition)}",
            "created_rule": new_rule,
            "task_name": task_name,
            "trigger_condition": trigger_condition
        }
    
    def _describe_trigger(self, trigger: Dict[str, Any]) -> str:
        """Generate human-readable trigger description"""
        parts = []
        
        if "location_vector" in trigger:
            parts.append(trigger["location_vector"].replace("_", " "))
        
        if "time_range" in trigger:
            time_range = trigger["time_range"]
            start = time_range.split("-")[0]
            parts.append(f"around {start}")
        
        if "activity" in trigger:
            activities = {
                "IN_VEHICLE": "you're driving",
                "WALKING": "you're walking",
                "STILL": "you're stationary"
            }
            parts.append(activities.get(trigger["activity"], trigger["activity"]))
        
        return " and ".join(parts) if parts else "the conditions are met"
