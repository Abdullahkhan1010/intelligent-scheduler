# Context-Aware Intelligent Scheduler
## University AI Project: Inductive Reasoning & Reinforcement Learning

![Project Status](https://img.shields.io/badge/status-ready_for_development-green)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flutter](https://img.shields.io/badge/Flutter-3.0+-blue)

---

## 📋 Project Overview

An intelligent mobile scheduling application that **learns user behavior** through sensor data and provides context-aware task suggestions using **inductive reasoning** and **reinforcement learning**.

### Core Innovation
- **Context Detection**: Uses mobile sensors (activity, location, Bluetooth) to understand user state
- **Probabilistic Inference**: Each task rule has a confidence weight that determines suggestion likelihood
- **Reinforcement Learning**: User feedback (Accept/Reject) dynamically adjusts rule weights
- **Natural Language Processing**: Simple NLP for conversational task creation

---

## 🎯 Key Features

### Backend (Python + FastAPI)
✅ **Probability-Based Inference Engine**
- Evaluates sensor context against task rules
- Returns tasks only when confidence > 0.6 threshold
- Supports complex multi-condition triggers

✅ **Reinforcement Learning Loop**
- Positive feedback: +0.05 to probability weight
- Negative feedback: -0.10 to probability weight
- Continuous adaptation to user preferences

✅ **Pre-Seeded Scenarios**
- Morning fuel reminders (driving + time)
- Grocery suggestions (leaving work + evening)
- Car meeting alerts (Bluetooth + calendar)

✅ **Natural Language Parser**
- Converts text to task rules
- Example: "I have a dentist appointment on the way home at 5 PM"

### Frontend (Flutter + Riverpod)
✅ **Live Schedule Timeline**
- Vertical timeline with confidence indicators
- Each task shows **reasoning** (why it was suggested)
- Accept/Reject feedback buttons

✅ **AI Chat Assistant**
- Conversational task creation
- Context-aware responses
- Natural language understanding

✅ **Sensor Integration**
- Activity recognition (Walking/Driving/Still)
- Location tracking with speed
- Bluetooth car detection
- Background periodic updates (every 10 min)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FLUTTER APP                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Timeline    │  │     Chat     │  │   Sensors    │  │
│  │     View     │  │   Assistant  │  │   Service    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                           │                              │
│                    Riverpod Providers                    │
└───────────────────────────┬─────────────────────────────┘
                            │ HTTP/JSON
                            ▼
┌─────────────────────────────────────────────────────────┐
│                  PYTHON BACKEND                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │              FastAPI Routes                      │  │
│  │  /infer  /feedback  /chat-input  /rules          │  │
│  └──────────────────────────────────────────────────┘  │
│                           │                              │
│  ┌──────────────────┐    │    ┌────────────────────┐   │
│  │  Inference       │◄───┼───►│  NLP Parser        │   │
│  │  Engine          │    │    │                    │   │
│  │  (Probability)   │    │    │  (Text → Rules)    │   │
│  └──────────────────┘    │    └────────────────────┘   │
│                           │                              │
│                           ▼                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │         SQLite Database                          │  │
│  │  • UserContext  • TaskRules  • FeedbackLogs     │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Flutter 3.0+
- Android Studio / Xcode
- pip, flutter command line tools

### Backend Setup (5 minutes)

```bash
# Navigate to backend
cd backend

# Install dependencies
pip install -r requirements.txt

# Seed database with initial rules
python seed_db.py

# Start server
python main.py
```

Server runs at: `http://localhost:8000`

**Verify**: Open `http://localhost:8000` in browser

### Frontend Setup (10 minutes)

```bash
# Navigate to Flutter app
cd flutter_app

# Install dependencies
flutter pub get

# Update API URL in lib/services/api_service.dart
# For Android emulator: http://10.0.2.2:8000
# For iOS simulator: http://localhost:8000
# For physical device: http://YOUR_LOCAL_IP:8000

# Run on connected device/emulator
flutter run
```

---

## 📚 How It Works

### 1. Sensor Data Collection
The Flutter app continuously monitors:
- **Activity**: Walking, Driving, Still (using Activity Recognition)
- **Location**: GPS coordinates + speed calculation
- **Bluetooth**: Detects car audio connections
- **WiFi**: Current network SSID

### 2. Context Inference
When sensor data changes significantly or periodically (every 10 min):
1. Send context to backend `/infer` endpoint
2. Backend evaluates all active task rules
3. Check if conditions match (80%+ match required)
4. Apply probability weight (only return if > 0.6)
5. Return high-confidence tasks with reasoning

### 3. Task Display
Timeline view shows:
- **Task name** (e.g., "Get Fuel")
- **Confidence badge** (e.g., "75% confident")
- **Reasoning box** (e.g., "You are driving • Time is 08:30 AM • Location: Leaving Home")
- **Feedback buttons** (Accept ✓ / Reject ✗)

### 4. Reinforcement Learning
When user provides feedback:
- **Accept**: Probability weight increases by 0.05
- **Reject**: Probability weight decreases by 0.10
- System becomes more accurate over time

### 5. Natural Language Input
Chat assistant can parse text like:
- "I have a dentist appointment on the way home at 5 PM"
- Creates a new task rule with appropriate triggers
- Responds with interpretation and confirmation

---

## 🧪 Testing Scenarios

### Scenario 1: Morning Commute
**Context:**
- Activity: IN_VEHICLE
- Time: 08:30 AM
- Location: leaving_home
- Speed: 45 km/h

**Expected Result:**
- Task: "Get Fuel"
- Reasoning: "You are driving • Time is 08:30 AM • Location: Leaving Home"

**Test:**
```bash
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{
    "activity_type": "IN_VEHICLE",
    "speed": 45.0,
    "is_connected_to_car_bluetooth": true,
    "location_vector": "leaving_home",
    "timestamp": "2025-12-01T08:30:00"
  }'
```

### Scenario 2: Evening Return
**Context:**
- Activity: IN_VEHICLE
- Time: 17:30
- Location: leaving_work
- WiFi: disconnected

**Expected Result:**
- Task: "Buy Groceries"
- Reasoning: "WiFi disconnected • Time is 05:30 PM • Location: Leaving Work"

### Scenario 3: Feedback Loop
1. Accept "Get Fuel" suggestion → Weight: 0.75 → 0.80
2. Reject "Buy Groceries" → Weight: 0.70 → 0.60
3. Reject again → Weight: 0.60 → 0.50 (below threshold, won't appear)

---

## 📊 Database Schema

### TaskRule Table
```sql
id                        INTEGER PRIMARY KEY
task_name                 TEXT
task_description          TEXT
trigger_condition         JSON
current_probability_weight FLOAT (0.0 - 1.0)
is_active                 INTEGER (0 or 1)
created_at                DATETIME
updated_at                DATETIME
```

### Example Rule:
```json
{
  "task_name": "Get Fuel",
  "trigger_condition": {
    "activity": "IN_VEHICLE",
    "time_range": "07:00-10:00",
    "location_vector": "leaving_home",
    "min_speed": 20.0
  },
  "current_probability_weight": 0.75
}
```

---

## 🔧 Configuration

### Backend Configuration
Edit `backend/main.py`:
```python
# CORS origins (for production)
allow_origins=["https://your-flutter-app-domain.com"]

# Database URL (default: SQLite)
SQLALCHEMY_DATABASE_URL = "sqlite:///./scheduler.db"
```

### Frontend Configuration
Edit `flutter_app/lib/services/api_service.dart`:
```dart
static const String baseUrl = 'http://YOUR_IP:8000';
```

Edit `flutter_app/lib/services/sensor_service.dart`:
```dart
// Adjust update frequency
_updateTimer = Timer.periodic(const Duration(minutes: 10), ...);
```

---

## 📱 Mobile Permissions

### Android (`AndroidManifest.xml`)
```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACTIVITY_RECOGNITION" />
<uses-permission android:name="android.permission.BLUETOOTH_SCAN" />
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />
```

### iOS (`Info.plist`)
```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>Context-aware task suggestions</string>
<key>NSMotionUsageDescription</key>
<string>Activity recognition</string>
<key>NSBluetoothAlwaysUsageDescription</key>
<string>Car audio detection</string>
```

---

## 🐛 Troubleshooting

### Backend Issues
**Problem**: `ImportError: No module named 'fastapi'`
**Solution**: `pip install -r requirements.txt`

**Problem**: Database locked error
**Solution**: Close other connections, restart server

### Frontend Issues
**Problem**: Package not found errors
**Solution**: `flutter pub get` then `flutter clean`

**Problem**: Sensors not working
**Solution**: Test on physical device (emulators have limited sensors)

**Problem**: Backend connection failed
**Solution**: 
- Check backend is running
- Verify IP address in `api_service.dart`
- Disable firewall for testing

---

## 📈 Future Enhancements

### Phase 3 (Advanced Features)
- [ ] Calendar integration (Google Calendar API)
- [ ] Weather-based suggestions (rain → bring umbrella)
- [ ] Traffic data integration (Waze/Google Maps)
- [ ] Smart home integration (leaving home → lights off)
- [ ] Voice input (speech-to-text)

### Phase 4 (ML Improvements)
- [ ] Replace probability weights with neural network
- [ ] Clustering for user behavior patterns
- [ ] Anomaly detection (unusual patterns)
- [ ] Multi-user support with user profiles

### Phase 5 (Production)
- [ ] Cloud deployment (AWS/GCP)
- [ ] PostgreSQL database
- [ ] Redis caching
- [ ] Push notifications
- [ ] Analytics dashboard

---

## 📝 Project Structure

```
AI/
├── backend/                    # Python FastAPI Backend
│   ├── main.py                 # FastAPI app with all routes
│   ├── models.py               # SQLAlchemy models + Pydantic schemas
│   ├── inference.py            # Probability engine + NLP parser
│   ├── seed_db.py              # Database seeding script
│   ├── requirements.txt        # Python dependencies
│   ├── scheduler.db            # SQLite database (generated)
│   └── README.md               # Backend documentation
│
└── flutter_app/                # Flutter Mobile App
    ├── lib/
    │   ├── main.dart           # App entry point + navigation
    │   ├── models/
    │   │   └── models.dart     # Data models
    │   ├── services/
    │   │   ├── api_service.dart      # HTTP client
    │   │   └── sensor_service.dart   # Sensor providers
    │   └── views/
    │       ├── timeline_view.dart    # Schedule timeline
    │       └── chat_view.dart        # Chat assistant
    ├── android/                # Android config
    ├── ios/                    # iOS config
    ├── pubspec.yaml            # Flutter dependencies
    └── README.md               # Frontend documentation
```

---

## 🎓 Academic Report Structure

### Suggested Sections:
1. **Introduction**: Problem statement, motivation
2. **Literature Review**: Related work in context-aware computing
3. **Methodology**: 
   - Inductive reasoning approach
   - Reinforcement learning algorithm
   - Sensor fusion techniques
4. **Implementation**: System architecture, tech stack
5. **Results**: Test scenarios, accuracy improvements over time
6. **Discussion**: Limitations, privacy considerations
7. **Conclusion**: Achievements, future work

### Key Metrics to Report:
- Accuracy improvement after N feedback iterations
- False positive/negative rates
- User satisfaction scores
- Battery consumption
- Inference latency

---

## 👥 Credits

**Developed by**: Abdullah
**Course**: University AI Project
**Date**: December 2025
**Tech Stack**: Python, FastAPI, Flutter, Riverpod, SQLite

---

## 📄 License

This is an academic project. Feel free to use and modify for educational purposes.

---

## 🤝 Contributing

For academic collaboration:
1. Fork the repository
2. Create feature branch
3. Commit changes
4. Submit pull request

---

## 📞 Support

For questions or issues:
- Check troubleshooting section
- Review backend/frontend READMEs
- Test with provided curl commands
- Verify sensor permissions on device

---

**Happy Coding! 🚀**
