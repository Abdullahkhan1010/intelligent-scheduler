"""
Google Calendar Task Parser
Classifies calendar events into actionable tasks with metadata for Bayesian inference
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
import re


class TaskType(str, Enum):
    """Type of calendar task"""
    FIXED_EVENT = "fixed_event"      # Specific start time (meetings, appointments)
    FLEXIBLE_TASK = "flexible_task"  # Can be scheduled within window (todos, reminders)


class Priority(str, Enum):
    """Task priority levels"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ParsedCalendarTask:
    """
    Normalized calendar task object for inference engine.
    Compatible with Bayesian timing optimization.
    """
    # Event identification
    event_id: str
    title: str
    description: Optional[str]
    
    # Temporal properties
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    duration_minutes: Optional[int]
    is_all_day: bool
    
    # Classification
    task_type: TaskType
    priority: Priority
    time_critical: bool
    preparation_required: bool
    location_dependent: bool
    
    # Location
    location: Optional[str]
    location_category: Optional[str]  # home, campus, work, other
    
    # Recurrence
    is_recurring: bool
    recurrence_pattern: Optional[str]
    recurrence_id: Optional[str]  # For grouping instances of same recurring event
    
    # Preparation metadata
    preparation_time_minutes: Optional[int]
    travel_time_minutes: Optional[int]
    
    # Context hints (for matching with sensor data)
    suggested_contexts: List[str]  # e.g., ["morning", "weekday", "campus"]
    
    # Raw event data (for reference)
    raw_event: Dict[str, Any]
    
    def get_optimal_reminder_time(self) -> Optional[datetime]:
        """
        Calculate when to remind user based on task properties.
        Returns the earliest time a reminder should be sent.
        """
        if not self.start_time:
            return None
        
        # Calculate total lead time needed
        lead_time_minutes = 0
        
        if self.preparation_required and self.preparation_time_minutes:
            lead_time_minutes += self.preparation_time_minutes
        
        if self.travel_time_minutes:
            lead_time_minutes += self.travel_time_minutes
        
        # Add buffer based on priority
        if self.priority == Priority.HIGH:
            lead_time_minutes += 60  # Extra hour for high priority
        elif self.priority == Priority.MEDIUM:
            lead_time_minutes += 30
        else:
            lead_time_minutes += 15
        
        # Minimum lead time
        lead_time_minutes = max(lead_time_minutes, 10)
        
        return self.start_time - timedelta(minutes=lead_time_minutes)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'event_id': self.event_id,
            'title': self.title,
            'description': self.description,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_minutes': self.duration_minutes,
            'is_all_day': self.is_all_day,
            'task_type': self.task_type.value,
            'priority': self.priority.value,
            'time_critical': self.time_critical,
            'preparation_required': self.preparation_required,
            'location_dependent': self.location_dependent,
            'location': self.location,
            'location_category': self.location_category,
            'is_recurring': self.is_recurring,
            'recurrence_pattern': self.recurrence_pattern,
            'recurrence_id': self.recurrence_id,
            'preparation_time_minutes': self.preparation_time_minutes,
            'travel_time_minutes': self.travel_time_minutes,
            'suggested_contexts': self.suggested_contexts,
            'optimal_reminder_time': self.get_optimal_reminder_time().isoformat() if self.get_optimal_reminder_time() else None
        }


class CalendarTaskParser:
    """
    Parses Google Calendar events into classified task objects.
    Uses heuristics and keyword matching for intelligent classification.
    """
    
    # Keywords for classification
    HIGH_PRIORITY_KEYWORDS = [
        'urgent', 'important', 'deadline', 'interview', 'exam', 'test',
        'presentation', 'demo', 'doctor', 'dentist', 'appointment', 'flight'
    ]
    
    PREPARATION_KEYWORDS = [
        'meeting', 'interview', 'presentation', 'gym', 'workout', 'class',
        'lecture', 'appointment', 'event', 'party', 'dinner', 'lunch'
    ]
    
    LOCATION_KEYWORDS = {
        'campus': ['university', 'campus', 'lecture', 'class', 'library', 'lab'],
        'work': ['office', 'work', 'conference room', 'meeting room'],
        'home': ['home', 'house', 'residence'],
        'gym': ['gym', 'fitness', 'workout'],
        'medical': ['hospital', 'clinic', 'doctor', 'dentist']
    }
    
    TRAVEL_KEYWORDS = ['commute', 'drive', 'travel', 'flight', 'trip']
    
    def __init__(self, learning_db: Optional[Dict[str, Any]] = None):
        """
        Initialize parser with optional learning database for recurring events.
        
        Args:
            learning_db: Dictionary storing learned behaviors for recurring events
        """
        self.learning_db = learning_db or {}
    
    def parse(self, calendar_event: Dict[str, Any]) -> ParsedCalendarTask:
        """
        Main parsing method. Converts Google Calendar event to ParsedCalendarTask.
        
        Args:
            calendar_event: Dictionary representing a Google Calendar event
            
        Returns:
            ParsedCalendarTask with classified properties
        """
        # Extract basic event information
        event_id = calendar_event.get('id', '')
        title = calendar_event.get('summary', 'Untitled Event')
        description = calendar_event.get('description', '')
        location = calendar_event.get('location')
        
        # Parse temporal properties
        start_time, end_time, is_all_day = self._parse_time_info(calendar_event)
        duration_minutes = self._calculate_duration(start_time, end_time)
        
        # Check if recurring
        is_recurring = 'recurrence' in calendar_event or 'recurringEventId' in calendar_event
        recurrence_pattern = self._extract_recurrence_pattern(calendar_event)
        recurrence_id = calendar_event.get('recurringEventId')
        
        # Classify task type
        task_type = self._classify_task_type(
            start_time=start_time,
            is_all_day=is_all_day,
            title=title,
            description=description
        )
        
        # Determine priority
        priority = self._determine_priority(
            title=title,
            description=description,
            start_time=start_time,
            attendees=calendar_event.get('attendees', [])
        )
        
        # Classify properties
        time_critical = self._is_time_critical(task_type, start_time, title)
        preparation_required = self._requires_preparation(title, description, location)
        location_dependent = self._is_location_dependent(location, title, description)
        
        # Infer location category
        location_category = self._categorize_location(location, title, description)
        
        # Estimate preparation and travel time
        preparation_time = self._estimate_preparation_time(
            title, description, preparation_required
        )
        travel_time = self._estimate_travel_time(
            location_category, location_dependent, title
        )
        
        # Generate context suggestions
        suggested_contexts = self._generate_context_suggestions(
            start_time=start_time,
            location_category=location_category,
            title=title
        )
        
        # Check if we have learned behavior for this recurring event
        if is_recurring and recurrence_id:
            learned_behavior = self.learning_db.get(recurrence_id, {})
            if learned_behavior:
                # Override with learned preferences
                priority = Priority(learned_behavior.get('priority', priority.value))
                preparation_time = learned_behavior.get('preparation_time', preparation_time)
                travel_time = learned_behavior.get('travel_time', travel_time)
        
        return ParsedCalendarTask(
            event_id=event_id,
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            is_all_day=is_all_day,
            task_type=task_type,
            priority=priority,
            time_critical=time_critical,
            preparation_required=preparation_required,
            location_dependent=location_dependent,
            location=location,
            location_category=location_category,
            is_recurring=is_recurring,
            recurrence_pattern=recurrence_pattern,
            recurrence_id=recurrence_id,
            preparation_time_minutes=preparation_time,
            travel_time_minutes=travel_time,
            suggested_contexts=suggested_contexts,
            raw_event=calendar_event
        )
    
    def update_learned_behavior(
        self, 
        recurrence_id: str, 
        feedback: Dict[str, Any]
    ) -> None:
        """
        Update learned behavior for a recurring event based on user feedback.
        
        Args:
            recurrence_id: ID of the recurring event
            feedback: Dictionary with user preferences (priority, timing, etc.)
        """
        if recurrence_id not in self.learning_db:
            self.learning_db[recurrence_id] = {}
        
        self.learning_db[recurrence_id].update(feedback)
    
    def _parse_time_info(
        self, 
        event: Dict[str, Any]
    ) -> tuple[Optional[datetime], Optional[datetime], bool]:
        """Parse start and end times from event"""
        start = event.get('start', {})
        end = event.get('end', {})
        
        # Check if all-day event
        is_all_day = 'date' in start
        
        start_time = None
        end_time = None
        
        if is_all_day:
            # All-day events use 'date' field
            date_str = start.get('date')
            if date_str:
                start_time = datetime.fromisoformat(date_str)
                end_date_str = end.get('date')
                if end_date_str:
                    end_time = datetime.fromisoformat(end_date_str)
        else:
            # Timed events use 'dateTime' field
            datetime_str = start.get('dateTime')
            if datetime_str:
                start_time = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                end_datetime_str = end.get('dateTime')
                if end_datetime_str:
                    end_time = datetime.fromisoformat(end_datetime_str.replace('Z', '+00:00'))
        
        return start_time, end_time, is_all_day
    
    def _calculate_duration(
        self, 
        start: Optional[datetime], 
        end: Optional[datetime]
    ) -> Optional[int]:
        """Calculate duration in minutes"""
        if start and end:
            delta = end - start
            return int(delta.total_seconds() / 60)
        return None
    
    def _extract_recurrence_pattern(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract recurrence pattern description"""
        if 'recurrence' in event:
            return event['recurrence'][0] if event['recurrence'] else None
        return None
    
    def _classify_task_type(
        self,
        start_time: Optional[datetime],
        is_all_day: bool,
        title: str,
        description: str
    ) -> TaskType:
        """
        Classify as fixed event or flexible task.
        
        Rules:
        - All-day events are usually flexible
        - Events with specific times are fixed
        - Tasks/reminders in title suggest flexible
        """
        title_lower = title.lower()
        desc_lower = description.lower() if description else ""
        
        # Check for task/todo indicators
        flexible_indicators = ['todo', 'task', 'reminder', 'remember to', 'don\'t forget']
        if any(indicator in title_lower or indicator in desc_lower for indicator in flexible_indicators):
            return TaskType.FLEXIBLE_TASK
        
        # All-day events are typically flexible
        if is_all_day:
            return TaskType.FLEXIBLE_TASK
        
        # Events with specific start times are fixed
        if start_time and not is_all_day:
            return TaskType.FIXED_EVENT
        
        # Default to flexible
        return TaskType.FLEXIBLE_TASK
    
    def _determine_priority(
        self,
        title: str,
        description: str,
        start_time: Optional[datetime],
        attendees: List[Dict[str, Any]]
    ) -> Priority:
        """
        Determine task priority using multiple signals.
        
        Factors:
        - Keywords in title/description
        - Number of attendees (more = higher priority)
        - Time until event (sooner = higher priority)
        """
        text = f"{title} {description or ''}".lower()
        
        # Check for high-priority keywords
        if any(keyword in text for keyword in self.HIGH_PRIORITY_KEYWORDS):
            return Priority.HIGH
        
        # Multiple attendees suggest important meeting
        if len(attendees) >= 3:
            return Priority.HIGH
        elif len(attendees) >= 1:
            return Priority.MEDIUM
        
        # Time-based priority
        if start_time:
            time_until = start_time - datetime.now()
            if time_until.total_seconds() < 3600:  # Less than 1 hour
                return Priority.HIGH
            elif time_until.total_seconds() < 86400:  # Less than 1 day
                return Priority.MEDIUM
        
        return Priority.LOW
    
    def _is_time_critical(
        self, 
        task_type: TaskType, 
        start_time: Optional[datetime],
        title: str
    ) -> bool:
        """
        Determine if task is time-critical.
        
        Rules:
        - Fixed events are always time-critical
        - Events with specific deadlines are time-critical
        """
        if task_type == TaskType.FIXED_EVENT:
            return True
        
        # Check for deadline keywords
        deadline_keywords = ['deadline', 'due', 'submit', 'turn in', 'by']
        if any(keyword in title.lower() for keyword in deadline_keywords):
            return True
        
        return False
    
    def _requires_preparation(
        self, 
        title: str, 
        description: str,
        location: Optional[str]
    ) -> bool:
        """Check if task requires preparation"""
        text = f"{title} {description or ''}".lower()
        
        # Events requiring preparation
        if any(keyword in text for keyword in self.PREPARATION_KEYWORDS):
            return True
        
        # Events at specific locations usually need preparation
        if location:
            return True
        
        return False
    
    def _is_location_dependent(
        self, 
        location: Optional[str],
        title: str,
        description: str
    ) -> bool:
        """Check if task depends on specific location"""
        if location:
            return True
        
        text = f"{title} {description or ''}".lower()
        
        # Check for location keywords
        location_indicators = ['at', 'in', 'room', 'building', 'address']
        if any(indicator in text for indicator in location_indicators):
            return True
        
        return False
    
    def _categorize_location(
        self, 
        location: Optional[str],
        title: str,
        description: str
    ) -> Optional[str]:
        """Categorize location into standard categories"""
        if not location:
            # Try to infer from title/description
            text = f"{title} {description or ''}".lower()
            
            for category, keywords in self.LOCATION_KEYWORDS.items():
                if any(keyword in text for keyword in keywords):
                    return category
            
            return None
        
        location_lower = location.lower()
        
        # Match against known location patterns
        for category, keywords in self.LOCATION_KEYWORDS.items():
            if any(keyword in location_lower for keyword in keywords):
                return category
        
        return 'other'
    
    def _estimate_preparation_time(
        self,
        title: str,
        description: str,
        preparation_required: bool
    ) -> Optional[int]:
        """Estimate preparation time in minutes"""
        if not preparation_required:
            return None
        
        text = f"{title} {description or ''}".lower()
        
        # Event-specific estimates
        if any(word in text for word in ['interview', 'presentation', 'exam']):
            return 30
        elif any(word in text for word in ['gym', 'workout']):
            return 15
        elif any(word in text for word in ['meeting', 'appointment']):
            return 10
        
        # Default
        return 15
    
    def _estimate_travel_time(
        self,
        location_category: Optional[str],
        location_dependent: bool,
        title: str
    ) -> Optional[int]:
        """Estimate travel time in minutes"""
        if not location_dependent:
            return None
        
        title_lower = title.lower()
        
        # Check for explicit travel keywords
        if any(keyword in title_lower for keyword in self.TRAVEL_KEYWORDS):
            return 30
        
        # Category-based estimates
        if location_category == 'campus':
            return 20
        elif location_category == 'work':
            return 25
        elif location_category == 'gym':
            return 15
        elif location_category == 'medical':
            return 30
        elif location_category == 'home':
            return 0
        
        # Default for unknown locations
        return 20
    
    def _generate_context_suggestions(
        self,
        start_time: Optional[datetime],
        location_category: Optional[str],
        title: str
    ) -> List[str]:
        """Generate context hints for matching with sensor data"""
        suggestions = []
        
        # Time-based contexts
        if start_time:
            hour = start_time.hour
            if 5 <= hour < 12:
                suggestions.append('morning')
            elif 12 <= hour < 17:
                suggestions.append('afternoon')
            elif 17 <= hour < 21:
                suggestions.append('evening')
            else:
                suggestions.append('night')
            
            # Weekday/weekend
            if start_time.weekday() < 5:
                suggestions.append('weekday')
            else:
                suggestions.append('weekend')
        
        # Location-based contexts
        if location_category:
            suggestions.append(location_category)
        
        # Activity-based contexts
        title_lower = title.lower()
        if any(word in title_lower for word in ['drive', 'commute', 'travel']):
            suggestions.append('traveling')
        elif any(word in title_lower for word in ['walk', 'walking']):
            suggestions.append('walking')
        
        return suggestions


# Factory function
def parse_calendar_event(
    event: Dict[str, Any], 
    learning_db: Optional[Dict[str, Any]] = None
) -> ParsedCalendarTask:
    """
    Convenience function to parse a calendar event.
    
    Usage:
        event = {...}  # Google Calendar event
        task = parse_calendar_event(event)
        print(f"Priority: {task.priority.value}")
        print(f"Reminder at: {task.get_optimal_reminder_time()}")
    """
    parser = CalendarTaskParser(learning_db)
    return parser.parse(event)
