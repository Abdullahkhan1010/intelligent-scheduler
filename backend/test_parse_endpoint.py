"""
Quick test of the task parsing functionality
"""
from inference import NaturalLanguageParser
from models import ParsedTaskRequest, ParsedTaskResponse, get_database

# Create database session
SessionLocal = get_database()
db = SessionLocal()

# Create parser
parser = NaturalLanguageParser(db)

# Test cases
test_cases = [
    "Remind me to call mom at 6 PM tomorrow",
    "I have a dentist appointment at 3 PM on Friday",
    "Buy groceries on the way home",
    "Meeting with team at 2:30 PM next Monday",
    "Urgent: Send email to client by 5 PM today"
]

print("=" * 70)
print("TESTING NATURAL LANGUAGE TASK PARSER WITH CONFIDENCE")
print("=" * 70)

for i, user_input in enumerate(test_cases, 1):
    print(f"\n{i}. Input: \"{user_input}\"")
    print("-" * 70)
    
    result = parser.parse_with_confidence(user_input)
    
    print(f"✓ Task Name: {result['parsed_task_name']}")
    print(f"✓ Overall Confidence: {result['confidence']:.1%}")
    
    if result['parsed_time']:
        print(f"✓ Time: {result['parsed_time']}")
    if result['parsed_date']:
        print(f"✓ Date: {result['parsed_date']}")
    if result['parsed_location']:
        print(f"✓ Location: {result['parsed_location']}")
    
    print(f"✓ Priority: {result['parsed_priority']}")
    
    if result['parsed_duration_minutes']:
        print(f"✓ Duration: {result['parsed_duration_minutes']} minutes")
    
    # Show confidence breakdown
    if result['confidence_breakdown']:
        print("\n  Confidence Breakdown:")
        for field, conf in result['confidence_breakdown'].items():
            bar_length = int(conf * 20)
            bar = '█' * bar_length + '░' * (20 - bar_length)
            print(f"    {field:15s} {bar} {conf:.1%}")
    
    if result['suggestions']:
        print(f"\n  💡 Suggestions: {', '.join(result['suggestions'])}")
    
    print(f"  ⚠️  Requires Confirmation: {'Yes' if result['requires_confirmation'] else 'No'}")

db.close()

print("\n" + "=" * 70)
print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
print("=" * 70)
