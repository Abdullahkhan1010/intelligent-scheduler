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
        # WEEKDAY MORNING TASKS
        {
            "task_name": "Get Fuel",
            "task_description": "Stop at gas station on your commute",
            "trigger_condition": {
                "activity": "IN_VEHICLE",
                "time_range": "07:00-10:00",
                "location_vector": "leaving_home",
                "min_speed": 15.0,
                "day_type": "weekday"
            },
            "current_probability_weight": 0.75,
            "is_active": 1
        },
        {
            "task_name": "Stop for Coffee",
            "task_description": "Grab coffee on your morning commute",
            "trigger_condition": {
                "activity": "IN_VEHICLE",
                "time_range": "07:00-09:30",
                "location_vector": "leaving_home",
                "car_bluetooth": True,
                "day_type": "weekday"
            },
            "current_probability_weight": 0.80,
            "is_active": 1
        },
        {
            "task_name": "Review Morning Emails",
            "task_description": "Check important emails when arriving at work",
            "trigger_condition": {
                "location_vector": "work",
                "time_range": "08:00-09:30",
                "activity": "STILL",
                "day_type": "weekday"
            },
            "current_probability_weight": 0.85,
            "is_active": 1
        },
        {
            "task_name": "Morning Standup",
            "task_description": "Join daily team standup meeting",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "09:00-10:00",
                "location_vector": "work",
                "day_type": "weekday"
            },
            "current_probability_weight": 0.80,
            "is_active": 1
        },
        
        # WEEKDAY WORK TASKS
        {
            "task_name": "Lunch Break Reminder",
            "task_description": "Time to take a break and eat",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "12:00-13:30",
                "location_vector": "work",
                "day_type": "weekday"
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
                "location_vector": "work",
                "day_type": "weekday"
            },
            "current_probability_weight": 0.60,
            "is_active": 1
        },
        {
            "task_name": "Plan Afternoon Tasks",
            "task_description": "Review and prioritize remaining work",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "13:00-15:00",
                "location_vector": "work",
                "day_type": "weekday"
            },
            "current_probability_weight": 0.70,
            "is_active": 1
        },
        
        # WEEKDAY EVENING TASKS
        {
            "task_name": "Buy Groceries",
            "task_description": "Stop for groceries on the way home",
            "trigger_condition": {
                "activity": "IN_VEHICLE",
                "time_range": "17:00-20:00",
                "location_vector": "leaving_work",
                "day_type": "weekday"
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
                "activity": "STILL",
                "day_type": "weekday"
            },
            "current_probability_weight": 0.65,
            "is_active": 1
        },
        {
            "task_name": "Evening Workout",
            "task_description": "Go to the gym or exercise at home",
            "trigger_condition": {
                "time_range": "18:00-20:00",
                "location_vector": "home",
                "activity": "STILL"
            },
            "current_probability_weight": 0.60,
            "is_active": 1
        },
        
        # WEEKEND MORNING TASKS
        {
            "task_name": "Weekend Breakfast",
            "task_description": "Enjoy a relaxed breakfast at home",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "08:00-11:00",
                "location_vector": "home",
                "day_type": "weekend"
            },
            "current_probability_weight": 0.75,
            "is_active": 1
        },
        {
            "task_name": "Morning Walk",
            "task_description": "Take a refreshing morning walk",
            "trigger_condition": {
                "activity": "WALKING",
                "time_range": "07:00-11:00",
                "location_vector": "near_home",
                "day_type": "weekend"
            },
            "current_probability_weight": 0.70,
            "is_active": 1
        },
        {
            "task_name": "Read the News",
            "task_description": "Catch up on news and articles",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "08:00-12:00",
                "location_vector": "home",
                "day_type": "weekend"
            },
            "current_probability_weight": 0.65,
            "is_active": 1
        },
        
        # WEEKEND DAYTIME TASKS
        {
            "task_name": "Weekend Errands",
            "task_description": "Time to run weekend errands",
            "trigger_condition": {
                "activity": "IN_VEHICLE",
                "time_range": "10:00-17:00",
                "car_bluetooth": True,
                "day_type": "weekend"
            },
            "current_probability_weight": 0.68,
            "is_active": 1
        },
        {
            "task_name": "Grocery Shopping",
            "task_description": "Do weekly grocery shopping",
            "trigger_condition": {
                "activity": "IN_VEHICLE",
                "time_range": "10:00-16:00",
                "day_type": "weekend"
            },
            "current_probability_weight": 0.72,
            "is_active": 1
        },
        {
            "task_name": "Clean the House",
            "task_description": "Weekend house cleaning",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "10:00-14:00",
                "location_vector": "home",
                "day_type": "weekend"
            },
            "current_probability_weight": 0.60,
            "is_active": 1
        },
        {
            "task_name": "Meal Prep",
            "task_description": "Prepare meals for the week ahead",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "14:00-18:00",
                "location_vector": "home",
                "day_type": "weekend"
            },
            "current_probability_weight": 0.65,
            "is_active": 1
        },
        
        # WEEKEND EVENING TASKS
        {
            "task_name": "Weekend Movie Night",
            "task_description": "Relax with a movie or show",
            "trigger_condition": {
                "activity": "STILL",
                "time_range": "19:00-23:00",
                "location_vector": "home",
                "day_type": "weekend"
            },
            "current_probability_weight": 0.70,
            "is_active": 1
        },
        
        # ANY DAY TASKS (no day_type filter)
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
            "task_name": "Water Plants",
            "task_description": "Don't forget to water your plants",
            "trigger_condition": {
                "activity": "STILL",
                "location_vector": "home",
                "time_range": "08:00-18:00"
            },
            "current_probability_weight": 0.52,
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
