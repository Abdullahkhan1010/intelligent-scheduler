#!/usr/bin/env python3
"""
Seed the database with realistic demo tasks that match the demo scenarios.
Some tasks have high weights (will trigger easily), some have low weights (for testing feedback).
"""

from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from models import TaskRuleDB, Base

# Create engine
SQLALCHEMY_DATABASE_URL = "sqlite:///./scheduler.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def clear_existing_tasks():
    """Remove all existing tasks"""
    db = SessionLocal()
    try:
        db.query(TaskRuleDB).delete()
        db.commit()
        print("✓ Cleared all existing tasks")
    finally:
        db.close()

def seed_demo_tasks():
    """Add demo tasks with varying weights"""
    
    tasks = [
        # HIGH WEIGHT TASKS (0.75-0.85) - Will trigger easily
        {
            "task_name": "Review morning emails",
            "task_description": "Check and respond to important emails",
            "trigger_condition": {
                "time_range": "07:00-09:00",
                "location_vector": "home",
                "wifi_ssid": "HomeNetwork"
            },
            "current_probability_weight": 0.85,
            "is_active": 1
        },
        {
            "task_name": "Stop for coffee",
            "task_description": "Grab coffee on the way to work",
            "trigger_condition": {
                "time_range": "07:30-09:00",
                "activity": "IN_VEHICLE",
                "location_vector": "leaving_home"
            },
            "current_probability_weight": 0.80,
            "is_active": 1
        },
        {
            "task_name": "Plan afternoon tasks",
            "task_description": "Review and organize your afternoon schedule",
            "trigger_condition": {
                "time_range": "12:00-13:30",
                "location_vector": "work",
                "activity": "STILL"
            },
            "current_probability_weight": 0.78,
            "is_active": 1
        },
        {
            "task_name": "Call family",
            "task_description": "Check in with family members",
            "trigger_condition": {
                "time_range": "18:00-20:00",
                "location_vector": "home",
                "activity": "STILL"
            },
            "current_probability_weight": 0.82,
            "is_active": 1
        },
        
        # MEDIUM WEIGHT TASKS (0.65-0.70) - Moderate confidence
        {
            "task_name": "Buy groceries",
            "task_description": "Stop at the store on the way home",
            "trigger_condition": {
                "time_range": "16:00-19:00",
                "activity": "IN_VEHICLE",
                "location_vector": "leaving_work"
            },
            "current_probability_weight": 0.68,
            "is_active": 1
        },
        {
            "task_name": "Take medication",
            "task_description": "Remember to take your daily medication",
            "trigger_condition": {
                "time_range": "18:30-20:00",
                "location_vector": "home"
            },
            "current_probability_weight": 0.70,
            "is_active": 1
        },
        {
            "task_name": "Morning workout",
            "task_description": "Quick exercise before starting the day",
            "trigger_condition": {
                "time_range": "06:30-08:00",
                "location_vector": "home",
                "activity": "STILL"
            },
            "current_probability_weight": 0.67,
            "is_active": 1
        },
        
        # LOW WEIGHT TASKS (0.50-0.60) - Need user feedback to improve
        {
            "task_name": "Check traffic conditions",
            "task_description": "Review traffic before commute",
            "trigger_condition": {
                "time_range": "07:30-09:00",
                "location_vector": "home"
            },
            "current_probability_weight": 0.58,
            "is_active": 1
        },
        {
            "task_name": "Prepare lunch",
            "task_description": "Pack lunch for work",
            "trigger_condition": {
                "time_range": "06:30-08:30",
                "location_vector": "home",
                "activity": "STILL"
            },
            "current_probability_weight": 0.55,
            "is_active": 1
        },
        {
            "task_name": "Water plants",
            "task_description": "Water your indoor plants",
            "trigger_condition": {
                "time_range": "18:00-20:00",
                "location_vector": "home",
                "activity": "STILL"
            },
            "current_probability_weight": 0.52,
            "is_active": 1
        },
        
        # WEEKEND TASKS
        {
            "task_name": "Weekend grocery shopping",
            "task_description": "Stock up on groceries for the week",
            "trigger_condition": {
                "time_range": "13:00-17:00",
                "activity": "IN_VEHICLE"
            },
            "current_probability_weight": 0.75,
            "is_active": 1
        },
        {
            "task_name": "Go for a walk",
            "task_description": "Get some exercise and fresh air",
            "trigger_condition": {
                "time_range": "09:00-12:00",
                "activity": "WALKING"
            },
            "current_probability_weight": 0.72,
            "is_active": 1
        },
        
        # CAR-SPECIFIC TASKS
        {
            "task_name": "Get gas",
            "task_description": "Fuel up the car",
            "trigger_condition": {
                "activity": "IN_VEHICLE",
                "car_bluetooth": True
            },
            "current_probability_weight": 0.65,
            "is_active": 1
        },
    ]
    
    db = SessionLocal()
    try:
        for task_data in tasks:
            task = TaskRuleDB(
                task_name=task_data["task_name"],
                task_description=task_data["task_description"],
                trigger_condition=task_data["trigger_condition"],
                current_probability_weight=task_data["current_probability_weight"],
                is_active=task_data["is_active"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(task)
        
        db.commit()
        print(f"✓ Added {len(tasks)} demo tasks")
    finally:
        db.close()
    
    # Print summary
    print("\n" + "="*60)
    print("DEMO TASKS SUMMARY")
    print("="*60)
    
    db = SessionLocal()
    try:
        high_weight = db.query(TaskRuleDB).filter(TaskRuleDB.current_probability_weight >= 0.75).count()
        medium_weight = db.query(TaskRuleDB).filter(
            TaskRuleDB.current_probability_weight >= 0.65,
            TaskRuleDB.current_probability_weight < 0.75
        ).count()
        low_weight = db.query(TaskRuleDB).filter(TaskRuleDB.current_probability_weight < 0.65).count()
        
        print(f"High confidence (≥75%): {high_weight} tasks - Will trigger easily")
        print(f"Medium confidence (65-74%): {medium_weight} tasks - Moderate")
        print(f"Low confidence (<65%): {low_weight} tasks - Need feedback to improve")
        print("\nTotal tasks:", high_weight + medium_weight + low_weight)
    finally:
        db.close()
    
    print("\n" + "="*60)
    print("DEMO SCENARIOS MATCHED")
    print("="*60)
    print("🏠 Morning at Home (7:30 AM):")
    print("   - Review morning emails (85%)")
    print("   - Morning workout (67%)")
    print("   - Prepare lunch (55%)")
    print("   - Check traffic conditions (58%)")
    print("\n🚗 Commute to Work (8:15 AM):")
    print("   - Stop for coffee (80%)")
    print("\n💼 At Office (12:30 PM):")
    print("   - Plan afternoon tasks (78%)")
    print("\n🚗 Leaving Work (5:45 PM):")
    print("   - Buy groceries (68%)")
    print("\n🏠 Evening at Home (7:00 PM):")
    print("   - Call family (82%)")
    print("   - Take medication (70%)")
    print("   - Water plants (52%)")
    print("\n🏃 Weekend Walk (10:00 AM Saturday):")
    print("   - Go for a walk (72%)")
    print("\n🛒 Weekend Errands (2:30 PM Saturday):")
    print("   - Weekend grocery shopping (75%)")
    print("="*60)

if __name__ == "__main__":
    print("Seeding database with demo tasks...\n")
    clear_existing_tasks()
    seed_demo_tasks()
    print("\n✓ Database seeding complete!")
