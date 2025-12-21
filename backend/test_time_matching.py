#!/usr/bin/env python3
"""
Quick test to verify time-matching logic for demo mode.
This simulates creating a task and checking if it appears when demo time matches.
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

def test_time_matching():
    print("=" * 60)
    print("TESTING TIME-BASED TASK MATCHING")
    print("=" * 60)
    
    # Step 1: Create a task for "5:00 PM" (17:00)
    print("\n1. Creating task: 'Dentist Appointment at 5 PM'")
    create_response = requests.post(f"{BASE_URL}/create-task", json={
        "task_name": "Dentist Appointment",
        "task_description": "Annual checkup at downtown clinic",
        "scheduled_time": "2024-12-19T17:00:00",  # 5 PM today
        "priority": "high",
        "location_context": "leaving_work"
    })
    
    if create_response.status_code == 200:
        task_data = create_response.json()
        print(f"✓ Task created with ID: {task_data['id']}")
        print(f"  Trigger conditions: {json.dumps(task_data['trigger_condition'], indent=4)}")
    else:
        print(f"✗ Failed to create task: {create_response.status_code}")
        return
    
    # Step 2: Test inference with time at 4:45 PM (15 minutes before)
    print("\n2. Testing inference at 4:45 PM (15 min before scheduled time)")
    test_time = datetime.now().replace(hour=16, minute=45, second=0, microsecond=0)
    
    context = {
        "timestamp": test_time.isoformat(),
        "activity_type": "IN_VEHICLE",
        "speed": 35.0,
        "is_connected_to_car_bluetooth": False,
        "wifi_ssid": None,
        "location_vector": "leaving_work",
        "additional_data": {}
    }
    
    infer_response = requests.post(f"{BASE_URL}/infer", json=context)
    
    if infer_response.status_code == 200:
        result = infer_response.json()
        suggested_tasks = result.get("suggested_tasks", [])
        
        print(f"\n  Total tasks suggested: {len(suggested_tasks)}")
        
        # Check if dentist appointment appears
        dentist_task = next((t for t in suggested_tasks if "Dentist" in t["task_name"]), None)
        
        if dentist_task:
            print(f"\n  ✓ DENTIST APPOINTMENT FOUND!")
            print(f"    Confidence: {dentist_task['confidence'] * 100:.0f}%")
            print(f"    Reasoning: {dentist_task['reasoning']}")
            print(f"    Matched Conditions: {json.dumps(dentist_task['matched_conditions'], indent=6)}")
        else:
            print(f"\n  ✗ Dentist appointment NOT found in suggestions")
            if suggested_tasks:
                print(f"\n  Other suggested tasks:")
                for task in suggested_tasks[:3]:
                    print(f"    - {task['task_name']} ({task['confidence'] * 100:.0f}%)")
    else:
        print(f"✗ Inference failed: {infer_response.status_code}")
    
    # Step 3: Test with time at 5:45 PM (45 minutes after - should NOT appear)
    print("\n\n3. Testing inference at 5:45 PM (45 min AFTER scheduled time)")
    test_time2 = datetime.now().replace(hour=17, minute=45, second=0, microsecond=0)
    
    context2 = context.copy()
    context2["timestamp"] = test_time2.isoformat()
    
    infer_response2 = requests.post(f"{BASE_URL}/infer", json=context2)
    
    if infer_response2.status_code == 200:
        result2 = infer_response2.json()
        suggested_tasks2 = result2.get("suggested_tasks", [])
        
        print(f"  Total tasks suggested: {len(suggested_tasks2)}")
        
        dentist_task2 = next((t for t in suggested_tasks2 if "Dentist" in t["task_name"]), None)
        
        if dentist_task2:
            print(f"\n  ⚠️ Dentist appointment still appearing (should have passed)")
            print(f"    Confidence: {dentist_task2['confidence'] * 100:.0f}%")
        else:
            print(f"\n  ✓ Correctly NOT showing - task time has passed")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_time_matching()
