"""
Probability-Based Inference Engine with Inductive Reasoning
Evaluates sensor context against task rules and returns high-confidence suggestions
"""
from datetime import datetime, time
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from models import TaskRuleDB, UserContextSchema, InferredTask
import re


class InferenceEngine:
    """Core inference logic for context-aware task suggestions"""
    
    CONFIDENCE_THRESHOLD = 0.6  # Minimum probability to suggest a task
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def infer_tasks(self, context: UserContextSchema) -> List[InferredTask]:
        """
        Main inference method: Evaluate all active rules against current context
        Returns tasks that match conditions and exceed confidence threshold
        """
        # Fetch all active task rules
        active_rules = self.db.query(TaskRuleDB).filter(
            TaskRuleDB.is_active == 1
        ).all()
        
        suggested_tasks = []
        
        for rule in active_rules:
            # Check if rule conditions match current context
            match_result = self._evaluate_rule(rule, context)
            
            if match_result["matches"]:
                # Apply probability weight (inductive learning parameter)
                confidence = rule.current_probability_weight * match_result["match_score"]
                
                # Only suggest if confidence exceeds threshold
                if confidence >= self.CONFIDENCE_THRESHOLD:
                    task = InferredTask(
                        rule_id=rule.id,
                        task_name=rule.task_name,
                        task_description=rule.task_description,
                        confidence=round(confidence, 2),
                        reasoning=match_result["reasoning"],
                        matched_conditions=match_result["matched_conditions"]
                    )
                    suggested_tasks.append(task)
        
        # Sort by confidence (highest first)
        suggested_tasks.sort(key=lambda x: x.confidence, reverse=True)
        
        return suggested_tasks
    
    def _evaluate_rule(self, rule: TaskRuleDB, context: UserContextSchema) -> Dict[str, Any]:
        """
        Evaluate if a rule's trigger conditions match the current context
        Returns: {"matches": bool, "match_score": float, "reasoning": str, "matched_conditions": dict}
        """
        trigger = rule.trigger_condition
        matched_conditions = {}
        reasons = []
        total_checks = 0
        successful_checks = 0
        
        # ===== ACTIVITY CHECK =====
        if "activity" in trigger:
            total_checks += 1
            expected_activity = trigger["activity"].upper()
            if context.activity_type.upper() == expected_activity:
                successful_checks += 1
                matched_conditions["activity"] = context.activity_type
                reasons.append(f"You are {self._humanize_activity(context.activity_type)}")
        
        # ===== TIME RANGE CHECK =====
        if "time_range" in trigger:
            total_checks += 1
            if self._is_time_in_range(trigger["time_range"], context.timestamp):
                successful_checks += 1
                matched_conditions["time"] = context.timestamp.strftime("%H:%M")
                reasons.append(f"Time is {context.timestamp.strftime('%I:%M %p')}")
        
        # ===== LOCATION VECTOR CHECK =====
        if "location_vector" in trigger:
            total_checks += 1
            if context.location_vector and context.location_vector.lower() == trigger["location_vector"].lower():
                successful_checks += 1
                matched_conditions["location_vector"] = context.location_vector
                reasons.append(f"Location: {context.location_vector.replace('_', ' ').title()}")
        
        # ===== BLUETOOTH CAR CHECK =====
        if "car_bluetooth" in trigger:
            total_checks += 1
            if trigger["car_bluetooth"] == context.is_connected_to_car_bluetooth:
                successful_checks += 1
                matched_conditions["car_bluetooth"] = context.is_connected_to_car_bluetooth
                if context.is_connected_to_car_bluetooth:
                    reasons.append("Connected to car Bluetooth")
        
        # ===== WIFI CHECK =====
        if "wifi_ssid" in trigger:
            total_checks += 1
            expected_wifi = trigger["wifi_ssid"]
            
            # Handle "disconnected" or "not_connected" special cases
            if expected_wifi in ["disconnected", "not_connected", None]:
                if not context.wifi_ssid or context.wifi_ssid == "":
                    successful_checks += 1
                    matched_conditions["wifi_ssid"] = "disconnected"
                    reasons.append("WiFi disconnected")
            elif context.wifi_ssid and context.wifi_ssid.lower() == expected_wifi.lower():
                successful_checks += 1
                matched_conditions["wifi_ssid"] = context.wifi_ssid
                reasons.append(f"Connected to {context.wifi_ssid}")
        
        # ===== SPEED CHECK (for fuel scenario) =====
        if "min_speed" in trigger:
            total_checks += 1
            if context.speed >= trigger["min_speed"]:
                successful_checks += 1
                matched_conditions["speed"] = context.speed
                reasons.append(f"Speed: {context.speed:.1f} km/h")
        
        # ===== CUSTOM CONDITIONS (extensible) =====
        if "custom" in trigger:
            for key, expected_value in trigger["custom"].items():
                if context.additional_data and key in context.additional_data:
                    total_checks += 1
                    if context.additional_data[key] == expected_value:
                        successful_checks += 1
                        matched_conditions[key] = expected_value
                        reasons.append(f"{key.replace('_', ' ').title()}: {expected_value}")
        
        # Calculate match score (percentage of conditions met)
        match_score = successful_checks / total_checks if total_checks > 0 else 0.0
        matches = match_score >= 0.8  # At least 80% of conditions must match
        
        reasoning = " • ".join(reasons) if reasons else "Conditions not met"
        
        return {
            "matches": matches,
            "match_score": match_score,
            "reasoning": reasoning,
            "matched_conditions": matched_conditions
        }
    
    def _is_time_in_range(self, time_range_str: str, current_time: datetime) -> bool:
        """
        Check if current time falls within a specified range
        Format: "HH:MM-HH:MM" (e.g., "08:00-09:00")
        """
        try:
            start_str, end_str = time_range_str.split("-")
            start_time = datetime.strptime(start_str.strip(), "%H:%M").time()
            end_time = datetime.strptime(end_str.strip(), "%H:%M").time()
            current = current_time.time()
            
            # Handle ranges that cross midnight
            if start_time <= end_time:
                return start_time <= current <= end_time
            else:
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
    
    def apply_feedback(self, rule_id: int, outcome: str) -> Dict[str, Any]:
        """
        Reinforcement Learning: Adjust probability weights based on user feedback
        Positive feedback: Increase weight by 0.05
        Negative feedback: Decrease weight by 0.1
        """
        rule = self.db.query(TaskRuleDB).filter(TaskRuleDB.id == rule_id).first()
        
        if not rule:
            return {"success": False, "message": "Rule not found"}
        
        old_weight = rule.current_probability_weight
        
        if outcome == "positive":
            # Reward: Increment probability (cap at 1.0)
            rule.current_probability_weight = min(1.0, old_weight + 0.05)
            adjustment = "increased"
        elif outcome == "negative":
            # Penalty: Decrement probability (floor at 0.0)
            rule.current_probability_weight = max(0.0, old_weight - 0.10)
            adjustment = "decreased"
        else:
            return {"success": False, "message": "Invalid outcome. Use 'positive' or 'negative'"}
        
        rule.updated_at = datetime.utcnow()
        self.db.commit()
        
        return {
            "success": True,
            "rule_id": rule_id,
            "task_name": rule.task_name,
            "old_weight": round(old_weight, 2),
            "new_weight": round(rule.current_probability_weight, 2),
            "adjustment": adjustment,
            "message": f"Rule '{rule.task_name}' probability {adjustment} from {old_weight:.2f} to {rule.current_probability_weight:.2f}"
        }


class NaturalLanguageParser:
    """Simple NLP for converting user text into task rules"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def parse_user_input(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Parse natural language and create a temporary task rule
        Example: "I have a dentist appointment on the way home at 5 PM"
        """
        user_message_lower = user_message.lower()
        
        # Extract task name (simple keyword matching)
        task_keywords = {
            "dentist": "Dentist Appointment",
            "doctor": "Doctor Appointment",
            "meeting": "Meeting",
            "groceries": "Buy Groceries",
            "gas": "Get Fuel",
            "fuel": "Get Fuel",
            "gym": "Go to Gym",
            "pickup": "Pickup Task",
            "call": "Make Phone Call"
        }
        
        task_name = "Custom Task"
        for keyword, name in task_keywords.items():
            if keyword in user_message_lower:
                task_name = name
                break
        
        # Extract time (basic regex for HH:MM or "5 PM" format)
        time_pattern = r'(\d{1,2})\s*(am|pm|:)'
        time_match = re.search(time_pattern, user_message_lower)
        
        trigger_condition = {}
        
        # Determine location context
        if "on the way home" in user_message_lower or "going home" in user_message_lower:
            trigger_condition["location_vector"] = "leaving_work"
        elif "on the way to work" in user_message_lower:
            trigger_condition["location_vector"] = "leaving_home"
        elif "at home" in user_message_lower:
            trigger_condition["location_vector"] = "home"
        elif "at work" in user_message_lower or "at office" in user_message_lower:
            trigger_condition["location_vector"] = "work"
        
        # Add time constraint if found
        if time_match:
            hour = int(time_match.group(1))
            period = time_match.group(2)
            
            # Convert to 24-hour format
            if 'pm' in period and hour != 12:
                hour += 12
            elif 'am' in period and hour == 12:
                hour = 0
            
            # Create time range (±30 minutes)
            start_hour = max(0, hour - 1) if hour > 0 else 23
            end_hour = min(23, hour + 1) if hour < 23 else 0
            trigger_condition["time_range"] = f"{start_hour:02d}:00-{end_hour:02d}:00"
        
        # Detect activity context
        if "driving" in user_message_lower or "car" in user_message_lower:
            trigger_condition["activity"] = "IN_VEHICLE"
        elif "walking" in user_message_lower:
            trigger_condition["activity"] = "WALKING"
        
        # Create the task rule
        new_rule = TaskRuleDB(
            task_name=task_name,
            task_description=user_message,
            trigger_condition=trigger_condition,
            current_probability_weight=0.75,  # Start with high confidence for user-created tasks
            is_active=1
        )
        
        self.db.add(new_rule)
        self.db.commit()
        self.db.refresh(new_rule)
        
        return {
            "understood": True,
            "interpretation": f"I'll remind you about '{task_name}' when " + self._describe_trigger(trigger_condition),
            "created_rule": new_rule,
            "task_name": task_name,
            "trigger_condition": trigger_condition
        }
    
    def _describe_trigger(self, trigger: Dict[str, Any]) -> str:
        """Generate human-readable description of trigger conditions"""
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
