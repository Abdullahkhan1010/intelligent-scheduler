"""
Database Seeding Script
Pre-populates the database with intelligent task rules for common scenarios
"""
from datetime import datetime
from models import get_database, TaskRuleDB, Base
from sqlalchemy import create_engine

def seed_database():
    """Initialize database with pre-configured task rules"""
    
    # Create database and tables
    SQLALCHEMY_DATABASE_URL = "sqlite:///./scheduler.db"
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = get_database()
    db = SessionLocal()
    
    # Check if already seeded
    existing_rules = db.query(TaskRuleDB).count()
    if existing_rules > 0:
        print(f"Database already contains {existing_rules} rules. Skipping seed.")
        db.close()
        return
    
    # Pre-configured rules based on requirements
    seed_rules = [
        {
            "task_name": "Get Fuel",
            "task_description": "Stop at gas station on your commute",
            "trigger_condition": {
                "activity": "IN_VEHICLE",
                "time_range": "07:00-10:00",
                "location_vector": "leaving_home",
                "min_speed": 15.0  # Reduced for easier testing
            },
            "current_probability_weight": 0.75,
            "is_active": 1
        },
        {
            "task_name": "Buy Groceries",
            "task_description": "Stop for groceries on the way home",
            "trigger_condition": {
                "wifi_ssid": "disconnected",
                "time_range": "17:00-20:00",
                "location_vector": "leaving_work"
            },
            "current_probability_weight": 0.70,
            "is_active": 1
        },
        {
            "task_name": "Join Meeting via Car Audio",
            "task_description": "Connect to scheduled meeting while driving",
            "trigger_condition": {
                "activity": "IN_VEHICLE",
                "car_bluetooth": True,
                "min_speed": 15.0  # Reduced for easier testing
            },
            "current_probability_weight": 0.85,
            "is_active": 1
        },
        {
            "task_name": "Lunch Break Reminder",
            "task_description": "Time to take a break and eat",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "12:00-13:30",
                "location_vector": "work"
            },
            "current_probability_weight": 0.65,
            "is_active": 1
        },
        {
            "task_name": "Evening Workout",
            "task_description": "Go to the gym or exercise",
            "trigger_condition": {
                "time_range": "18:00-20:00",
                "location_vector": "home",
                "activity": "STILL"
            },
            "current_probability_weight": 0.60,
            "is_active": 1
        },
        {
            "task_name": "Morning Standup",
            "task_description": "Join daily team standup meeting",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "09:00-10:00",
                "location_vector": "work"
            },
            "current_probability_weight": 0.80,
            "is_active": 1
        },
        {
            "task_name": "Check Email",
            "task_description": "Review emails when arriving at work",
            "trigger_condition": {
                "location_vector": "work",
                "time_range": "08:00-09:30",
                "activity": "STILL"
            },
            "current_probability_weight": 0.70,
            "is_active": 1
        },
        {
            "task_name": "Prepare for Commute",
            "task_description": "Get ready to leave work",
            "trigger_condition": {
                "location_vector": "work",
                "time_range": "16:30-18:00",
                "activity": "STILL"
            },
            "current_probability_weight": 0.65,
            "is_active": 1
        },
        {
            "task_name": "Stretch Break",
            "task_description": "Take a moment to stretch and move around",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "10:00-16:00",
                "location_vector": "work"
            },
            "current_probability_weight": 0.70,
            "is_active": 1
        },
        {
            "task_name": "Get Coffee",
            "task_description": "Take a coffee break to refresh",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "10:00-11:00",
                "location_vector": "work"
            },
            "current_probability_weight": 0.65,
            "is_active": 1
        },
        {
            "task_name": "Afternoon Coffee Break",
            "task_description": "Grab an afternoon coffee",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "14:00-15:30",
                "location_vector": "work"
            },
            "current_probability_weight": 0.60,
            "is_active": 1
        },
        {
            "task_name": "Quick Drive Test",
            "task_description": "Test task for low-speed driving detection",
            "trigger_condition": {
                "activity": "IN_VEHICLE",
                "min_speed": 15.0,  # Low threshold for easy testing
                "car_bluetooth": True
            },
            "current_probability_weight": 0.75,
            "is_active": 1
        },
        {
            "task_name": "Evening Relaxation",
            "task_description": "Time to unwind at home",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "20:00-23:00",
                "location_vector": "home"
            },
            "current_probability_weight": 0.65,
            "is_active": 1
        },
        {
            "task_name": "Morning Routine",
            "task_description": "Start your day at home",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "06:00-08:00",
                "location_vector": "home"
            },
            "current_probability_weight": 0.70,
            "is_active": 1
        }
    ]
    
    # Insert seed rules
    for rule_data in seed_rules:
        rule = TaskRuleDB(**rule_data)
        db.add(rule)
    
    db.commit()
    
    print(f"✓ Database seeded successfully with {len(seed_rules)} task rules")
    print("\nSeeded Rules:")
    for idx, rule in enumerate(seed_rules, 1):
        print(f"  {idx}. {rule['task_name']} (Probability: {rule['current_probability_weight']})")
    
    db.close()


if __name__ == "__main__":
    seed_database()
