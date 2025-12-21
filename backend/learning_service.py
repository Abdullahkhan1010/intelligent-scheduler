"""
Feedback-Based Learning Service
Handles user feedback, updates Beta distributions, and provides learning explanations
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import (
    BayesianTimingParametersDB, 
    FeedbackLogDB,
    TaskRuleDB,
    UserContextSchema
)
import math


class LearningService:
    """
    Manages feedback-based learning for task scheduling.
    
    Core responsibilities:
    1. Accept user feedback (accept/reject)
    2. Update Beta distribution parameters (alpha/beta)
    3. Persist learning to database
    4. Generate explanations of learned behavior
    5. Provide learning analytics
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def record_feedback(
        self,
        task_id: int,
        task_type: str,
        context: UserContextSchema,
        timing_window: int,
        feedback: str,
        notification_sent_at: Optional[datetime] = None,
        task_completed_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Main feedback recording method. Updates Beta distributions and logs feedback.
        
        Args:
            task_id: ID of the task rule
            task_type: Type of task (e.g., "Check email", "Gym workout")
            context: User's current context when feedback was given
            timing_window: Minutes before task the notification was sent
            feedback: "accept" or "reject"
            notification_sent_at: When notification was shown
            task_completed_at: When user completed/dismissed task
            
        Returns:
            Dictionary with update results and learning insights
        """
        # Validate feedback
        if feedback.lower() not in ['accept', 'reject', 'accepted', 'rejected']:
            return {
                'success': False,
                'error': f"Invalid feedback '{feedback}'. Use 'accept' or 'reject'"
            }
        
        accepted = feedback.lower() in ['accept', 'accepted']
        
        # Generate context key for Beta distribution lookup
        context_key = self._generate_context_key(context)
        
        # Update Beta distribution
        beta_update = self._update_beta_distribution(
            task_type=task_type,
            context_key=context_key,
            timing_window=timing_window,
            accepted=accepted
        )
        
        # Log feedback to database
        feedback_log = FeedbackLogDB(
            rule_id=task_id,
            user_action='accepted' if accepted else 'rejected',
            context_snapshot={
                'context_key': context_key,
                'timing_window': timing_window,
                'activity': context.activity_type,
                'location': context.location_vector,
                'time': context.timestamp.isoformat()
            },
            timestamp=datetime.utcnow()
        )
        self.db.add(feedback_log)
        
        # Update task rule probability weight (existing RL system)
        rule_update = self._update_rule_weight(task_id, accepted)
        
        self.db.commit()
        
        # Generate explanation of what was learned
        explanation = self._generate_learning_explanation(
            beta_update=beta_update,
            rule_update=rule_update,
            context_key=context_key,
            accepted=accepted
        )
        
        return {
            'success': True,
            'feedback': 'accepted' if accepted else 'rejected',
            'task_type': task_type,
            'context_key': context_key,
            'timing_window': timing_window,
            'beta_distribution': {
                'alpha': beta_update['alpha'],
                'beta': beta_update['beta'],
                'confidence': beta_update['new_confidence'],
                'confidence_change': round(
                    beta_update['new_confidence'] - beta_update['old_confidence'], 
                    3
                )
            },
            'rule_weight': {
                'old': rule_update['old_weight'],
                'new': rule_update['new_weight'],
                'change': round(rule_update['new_weight'] - rule_update['old_weight'], 3)
            },
            'explanation': explanation,
            'total_feedback_count': beta_update['total_feedback']
        }
    
    def _update_beta_distribution(
        self,
        task_type: str,
        context_key: str,
        timing_window: int,
        accepted: bool
    ) -> Dict[str, Any]:
        """
        Update Beta(alpha, beta) parameters based on feedback.
        
        Accept -> alpha += 1
        Reject -> beta += 1
        """
        # Get or create parameters
        params = self.db.query(BayesianTimingParametersDB).filter(
            BayesianTimingParametersDB.task_type == task_type,
            BayesianTimingParametersDB.context_key == context_key,
            BayesianTimingParametersDB.timing_window == timing_window
        ).first()
        
        if not params:
            # Initialize with uniform prior Beta(1, 1)
            params = BayesianTimingParametersDB(
                task_type=task_type,
                context_key=context_key,
                timing_window=timing_window,
                alpha=1.0,
                beta=1.0,
                total_triggers=0
            )
            self.db.add(params)
            self.db.flush()  # Get ID without committing
        
        # Store old values for comparison
        old_alpha = params.alpha
        old_beta = params.beta
        old_confidence = old_alpha / (old_alpha + old_beta)
        
        # Update based on feedback
        if accepted:
            params.alpha += 1
        else:
            params.beta += 1
        
        params.total_triggers += 1
        params.last_updated = datetime.utcnow()
        
        # Calculate new confidence
        new_confidence = params.alpha / (params.alpha + params.beta)
        
        return {
            'alpha': params.alpha,
            'beta': params.beta,
            'old_confidence': round(old_confidence, 3),
            'new_confidence': round(new_confidence, 3),
            'total_feedback': int(params.alpha + params.beta - 2)  # Subtract priors
        }
    
    def _update_rule_weight(self, rule_id: int, accepted: bool) -> Dict[str, Any]:
        """Update task rule probability weight (existing RL system)"""
        rule = self.db.query(TaskRuleDB).filter(TaskRuleDB.id == rule_id).first()
        
        if not rule:
            return {
                'old_weight': 0.0,
                'new_weight': 0.0,
                'found': False
            }
        
        old_weight = rule.current_probability_weight
        
        if accepted:
            rule.current_probability_weight = min(1.0, old_weight + 0.05)
        else:
            rule.current_probability_weight = max(0.0, old_weight - 0.10)
        
        rule.updated_at = datetime.utcnow()
        
        return {
            'old_weight': round(old_weight, 2),
            'new_weight': round(rule.current_probability_weight, 2),
            'found': True
        }
    
    def _generate_context_key(self, context: UserContextSchema) -> str:
        """
        Generate context signature for Beta distribution grouping.
        Format: "activity_timeofday_daytype_location"
        """
        activity = context.activity_type.upper().replace(' ', '_')
        
        # Time of day
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
        day_type = "weekday" if context.timestamp.weekday() < 5 else "weekend"
        
        # Location
        location = (context.location_vector or "unknown").lower().replace(' ', '_')
        
        return f"{activity}_{time_period}_{day_type}_{location}"
    
    def _generate_learning_explanation(
        self,
        beta_update: Dict[str, Any],
        rule_update: Dict[str, Any],
        context_key: str,
        accepted: bool
    ) -> str:
        """Generate human-readable explanation of learning update"""
        action = "accepted" if accepted else "rejected"
        
        # Parse context key for readable description
        parts = context_key.split('_')
        activity = parts[0].replace('_', ' ').lower() if len(parts) > 0 else "unknown"
        time_period = parts[1] if len(parts) > 1 else "unknown time"
        day_type = parts[2] if len(parts) > 2 else "unknown day"
        
        conf_change = beta_update['new_confidence'] - beta_update['old_confidence']
        direction = "increased" if conf_change > 0 else "decreased"
        
        explanation_parts = [
            f"You {action} the notification during {activity} on {day_type} {time_period}.",
            f"Confidence {direction} from {beta_update['old_confidence']:.1%} to {beta_update['new_confidence']:.1%}.",
        ]
        
        # Add learning progress indicator
        total_feedback = beta_update['total_feedback']
        if total_feedback == 0:
            explanation_parts.append("This is the first feedback for this context.")
        elif total_feedback < 5:
            explanation_parts.append(f"Based on {total_feedback + 1} total feedback samples - still learning.")
        else:
            explanation_parts.append(f"Based on {total_feedback + 1} feedback samples - confidence is well-calibrated.")
        
        # Add Beta distribution info
        alpha = beta_update['alpha']
        beta = beta_update['beta']
        explanation_parts.append(f"Distribution: Beta({alpha:.0f}, {beta:.0f}).")
        
        return " ".join(explanation_parts)
    
    def get_learning_summary(
        self,
        task_type: Optional[str] = None,
        context_key: Optional[str] = None,
        min_feedback_count: int = 0
    ) -> Dict[str, Any]:
        """
        Get summary of learned behavior across all or specific contexts.
        
        Args:
            task_type: Filter by specific task type
            context_key: Filter by specific context
            min_feedback_count: Only include distributions with at least this many feedback samples
            
        Returns:
            Summary of all Beta distributions with confidence levels
        """
        query = self.db.query(BayesianTimingParametersDB)
        
        if task_type:
            query = query.filter(BayesianTimingParametersDB.task_type == task_type)
        
        if context_key:
            query = query.filter(BayesianTimingParametersDB.context_key == context_key)
        
        # Order by confidence (most confident first)
        all_params = query.all()
        
        summaries = []
        for params in all_params:
            feedback_count = int(params.alpha + params.beta - 2)  # Subtract priors
            
            if feedback_count < min_feedback_count:
                continue
            
            confidence = params.alpha / (params.alpha + params.beta)
            total = params.alpha + params.beta
            variance = (params.alpha * params.beta) / (total**2 * (total + 1))
            uncertainty = math.sqrt(variance)
            
            summaries.append({
                'task_type': params.task_type,
                'context_key': params.context_key,
                'timing_window': params.timing_window,
                'confidence': round(confidence, 3),
                'uncertainty': round(uncertainty, 3),
                'alpha': params.alpha,
                'beta': params.beta,
                'feedback_count': feedback_count,
                'total_triggers': params.total_triggers,
                'last_updated': params.last_updated.isoformat() if params.last_updated else None
            })
        
        # Sort by confidence (descending)
        summaries.sort(key=lambda x: x['confidence'], reverse=True)
        
        return {
            'total_distributions': len(summaries),
            'distributions': summaries,
            'filters': {
                'task_type': task_type,
                'context_key': context_key,
                'min_feedback_count': min_feedback_count
            }
        }
    
    def get_explanation_data(
        self,
        task_type: str,
        context: UserContextSchema
    ) -> Dict[str, Any]:
        """
        Expose learning data for explanation generation.
        Shows what the system has learned about a task in a specific context.
        
        Returns:
            Detailed learning data including all timing windows and their distributions
        """
        context_key = self._generate_context_key(context)
        
        timing_windows = [60, 30, 10]  # Standard windows
        window_data = []
        
        for window in timing_windows:
            params = self.db.query(BayesianTimingParametersDB).filter(
                BayesianTimingParametersDB.task_type == task_type,
                BayesianTimingParametersDB.context_key == context_key,
                BayesianTimingParametersDB.timing_window == window
            ).first()
            
            if params:
                confidence = params.alpha / (params.alpha + params.beta)
                feedback_count = int(params.alpha + params.beta - 2)
                
                # Calculate credible interval (95%)
                # For Beta distribution, approximate 95% CI
                total = params.alpha + params.beta
                variance = (params.alpha * params.beta) / (total**2 * (total + 1))
                std = math.sqrt(variance)
                
                window_data.append({
                    'window': window,
                    'confidence': round(confidence, 3),
                    'alpha': params.alpha,
                    'beta': params.beta,
                    'feedback_count': feedback_count,
                    'total_triggers': params.total_triggers,
                    'credible_interval_95': {
                        'lower': max(0, round(confidence - 1.96 * std, 3)),
                        'upper': min(1, round(confidence + 1.96 * std, 3))
                    },
                    'is_well_learned': feedback_count >= 5
                })
            else:
                # No data yet for this window
                window_data.append({
                    'window': window,
                    'confidence': 0.5,  # Uniform prior
                    'alpha': 1.0,
                    'beta': 1.0,
                    'feedback_count': 0,
                    'total_triggers': 0,
                    'credible_interval_95': {'lower': 0.0, 'upper': 1.0},
                    'is_well_learned': False
                })
        
        # Find best window
        best_window = max(window_data, key=lambda x: x['confidence'])
        
        # Generate explanation
        parts = context_key.split('_')
        context_description = {
            'activity': parts[0].replace('_', ' ').lower() if len(parts) > 0 else 'unknown',
            'time_of_day': parts[1] if len(parts) > 1 else 'unknown',
            'day_type': parts[2] if len(parts) > 2 else 'unknown',
            'location': parts[3] if len(parts) > 3 else 'unknown'
        }
        
        return {
            'task_type': task_type,
            'context_key': context_key,
            'context_description': context_description,
            'recommended_window': best_window['window'],
            'recommended_confidence': best_window['confidence'],
            'all_windows': window_data,
            'total_learning_samples': sum(w['feedback_count'] for w in window_data),
            'is_well_trained': any(w['is_well_learned'] for w in window_data)
        }
    
    def get_recent_feedback_history(
        self,
        task_id: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get recent feedback history for analysis.
        
        Args:
            task_id: Filter by specific task rule
            limit: Maximum number of records to return
            
        Returns:
            List of recent feedback records
        """
        query = self.db.query(FeedbackLogDB).order_by(desc(FeedbackLogDB.timestamp))
        
        if task_id:
            query = query.filter(FeedbackLogDB.rule_id == task_id)
        
        feedback_logs = query.limit(limit).all()
        
        history = []
        for log in feedback_logs:
            history.append({
                'id': log.id,
                'rule_id': log.rule_id,
                'action': log.user_action,
                'timestamp': log.timestamp.isoformat(),
                'context_snapshot': log.context_snapshot
            })
        
        return history


# Factory function
def create_learning_service(db_session: Session) -> LearningService:
    """Create a LearningService instance"""
    return LearningService(db_session)
