import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/models.dart';
import 'api_service.dart';
import 'calendar_service.dart';
import 'notification_service.dart';
import 'feedback_tracker.dart';
import 'demo_service.dart';

/// Sensor data state
class SensorData {
  final String activity;
  final double speed;
  final bool carBluetoothConnected;
  final String? wifiSsid;
  final String? locationVector;
  final DateTime lastUpdate;

  SensorData({
    required this.activity,
    required this.speed,
    required this.carBluetoothConnected,
    this.wifiSsid,
    this.locationVector,
    required this.lastUpdate,
  });

  SensorData copyWith({
    String? activity,
    double? speed,
    bool? carBluetoothConnected,
    String? wifiSsid,
    String? locationVector,
    DateTime? lastUpdate,
  }) {
    return SensorData(
      activity: activity ?? this.activity,
      speed: speed ?? this.speed,
      carBluetoothConnected: carBluetoothConnected ?? this.carBluetoothConnected,
      wifiSsid: wifiSsid ?? this.wifiSsid,
      locationVector: locationVector ?? this.locationVector,
      lastUpdate: lastUpdate ?? this.lastUpdate,
    );
  }
}

/// Sensor Service Provider with mock data for testing
class SensorService extends StateNotifier<SensorData> {
  final Ref ref;
  Timer? _updateTimer;
  Timer? _mockSensorTimer;

  SensorService(this.ref)
      : super(SensorData(
          activity: 'STILL',
          speed: 0.0,
          carBluetoothConnected: false,
          wifiSsid: 'HomeWiFi',
          locationVector: 'home',
          lastUpdate: DateTime.now(),
        )) {
    _initialize();
  }

  Future<void> _initialize() async {
    print('🚀 SensorService: Initializing mock sensors...');
    // Use mock data for testing (real sensors don't work on emulators)
    _startMockSensors();
    _startPeriodicUpdates();
    print('✅ SensorService: Initialization complete');
  }

  void _startMockSensors() {
    print('⏰ Starting mock sensor timer (30 second interval)');
    // Simulate sensor data changes every 30 seconds
    _mockSensorTimer = Timer.periodic(const Duration(seconds: 30), (timer) {
      // Only update if not in demo mode - check current state
      try {
        final demoService = ref.read(demoServiceProvider);
        if (!demoService.isDemoMode) {
          print('🔄 Mock sensor timer: Updating (demo mode OFF)');
          _updateMockSensorData();
        } else {
          print('⏸️  Mock sensor timer: Skipped (demo mode ON)');
        }
      } catch (e) {
        print('⚠️  Mock sensor timer error: $e');
      }
    });
    // Initial update (only if not in demo mode)
    print('🔧 Running initial sensor update...');
    try {
      final demoService = ref.read(demoServiceProvider);
      if (!demoService.isDemoMode) {
        print('📡 Initial update: Demo mode OFF');
        _updateMockSensorData();
      } else {
        print('📡 Initial update: Demo mode ON, skipping');
      }
    } catch (e) {
      // If demo service not available yet, update anyway
      print('📡 Initial update: Demo service not ready, updating anyway');
      _updateMockSensorData();
    }
  }

  /// Stop mock sensors (when entering demo mode)
  void stopMockSensors() {
    _mockSensorTimer?.cancel();
  }

  /// Restart mock sensors (when exiting demo mode)
  void restartMockSensors() {
    stopMockSensors();
    _startMockSensors();
  }

  /// Update mock sensor data - simulates REAL sensor readings
  /// Provides RAW sensor data, location is INFERRED from the combination
  void _updateMockSensorData() {
    print('🔍 _updateMockSensorData() called');
    final now = DateTime.now();
    final hour = now.hour;
    final dayOfWeek = now.weekday; // 1=Monday, 6=Saturday, 7=Sunday
    // Explicit weekend check: 6 or 7
    final isWeekend = (dayOfWeek == 6 || dayOfWeek == 7);
    
    print('📅 Mock sensors: ${isWeekend ? "WEEKEND" : "WEEKDAY"} (day=$dayOfWeek), hour=$hour, Sat=${DateTime.saturday}, Sun=${DateTime.sunday}');
    
    // Simulate raw sensor readings (like a real device would provide)
    double speed = 0.0;
    String activity = 'STILL';
    bool bluetoothConnected = false;
    String? wifiSsid = 'HomeWiFi'; // Default: at home
    
    // WEEKEND SCENARIOS - most people stay home or do light activities
    if (isWeekend) {
      print('🏖️  Weekend scenario: Stationary at home (speed=0, wifi=HomeWiFi, bt=false)');
      // Weekend - people typically stay home, especially mornings
      speed = 0.0;
      activity = 'STILL';
      bluetoothConnected = false;
      wifiSsid = 'HomeWiFi';
    }
    // WEEKDAY SCENARIOS
    else {
      // Morning commute (7am-10am)
      if (hour >= 7 && hour < 10) {
        print('🚗 Weekday morning commute');
        speed = 20.0;
        activity = 'IN_VEHICLE';
        bluetoothConnected = true;
        wifiSsid = null; // No wifi in car
      }
      // Work hours (10am-5pm)
      else if (hour >= 10 && hour < 17) {
        print('💼 Weekday at office');
        speed = 0.0;
        activity = 'STILL';
        bluetoothConnected = false;
        wifiSsid = 'OfficeWiFi';
      }
      // Evening commute (5pm-8pm)
      else if (hour >= 17 && hour < 20) {
        print('🚗 Weekday evening commute');
        speed = 25.0;
        activity = 'IN_VEHICLE';
        bluetoothConnected = true;
        wifiSsid = null; // No wifi in car
      }
      // Early morning or late night - at home
      else {
        print('🏠 Weekday at home');
        speed = 0.0;
        activity = 'STILL';
        bluetoothConnected = false;
        wifiSsid = 'HomeWiFi';
      }
    }
    
    // INFER LOCATION from sensor combination (like real logic would)
    String inferredLocation = _inferLocationFromSensors(
      speed: speed,
      wifiSsid: wifiSsid,
      bluetoothConnected: bluetoothConnected,
      activity: activity,
    );
    
    print('📍 Inferred location: $inferredLocation (speed=$speed, wifi=$wifiSsid, bt=$bluetoothConnected)');
    
    state = state.copyWith(
      activity: activity,
      speed: speed,
      carBluetoothConnected: bluetoothConnected,
      wifiSsid: wifiSsid,
      locationVector: inferredLocation,
      lastUpdate: now,
    );
  }
  
  /// Infer semantic location from raw sensor data
  /// This simulates how a real app would determine location context
  String _inferLocationFromSensors({
    required double speed,
    required String? wifiSsid,
    required bool bluetoothConnected,
    required String activity,
  }) {
    // Rule 1: If moving in vehicle with bluetooth → leaving somewhere
    if (speed > 10 && bluetoothConnected && activity == 'IN_VEHICLE') {
      // Check wifi to determine if leaving home or work
      if (wifiSsid == null) {
        // No wifi, probably in transit
        final hour = DateTime.now().hour;
        if (hour >= 7 && hour < 12) return 'leaving_home';
        if (hour >= 17 && hour < 21) return 'leaving_work';
        return 'in_transit';
      }
    }
    
    // Rule 2: If stationary with home wifi → at home
    if (speed < 5 && wifiSsid == 'HomeWiFi' && !bluetoothConnected) {
      return 'home';
    }
    
    // Rule 3: If stationary with office wifi → at work
    if (speed < 5 && wifiSsid == 'OfficeWiFi' && !bluetoothConnected) {
      return 'work';
    }
    
    // Rule 4: If walking with no wifi → near home or outdoors
    if (speed > 0 && speed < 10 && activity == 'WALKING' && wifiSsid == null) {
      return 'near_home';
    }
    
    // Rule 5: If stationary with bluetooth but no movement → sitting in parked car
    if (speed < 5 && bluetoothConnected && activity == 'STILL') {
      return 'in_parked_vehicle';
    }
    
    // Default: unknown location
    return 'unknown';
  }

  /// Force sensor data update (used when exiting demo mode)
  void forceUpdateSensors() {
    _updateMockSensorData();
  }

  void _startPeriodicUpdates() {
    // Send updates to backend every 10 minutes or on significant change
    _updateTimer = Timer.periodic(const Duration(minutes: 10), (timer) {
      _sendContextToBackend();
    });
  }

  Future<void> _sendContextToBackend() async {
    try {
      final apiService = ref.read(apiServiceProvider);
      final context = UserContext(
        timestamp: DateTime.now(),
        activityType: state.activity,
        speed: state.speed,
        isConnectedToCarBluetooth: state.carBluetoothConnected,
        wifiSsid: state.wifiSsid,
        locationVector: state.locationVector,
      );

      await apiService.inferSchedule(context);
    } catch (e) {
      print('Failed to send context to backend: $e');
    }
  }

  /// Update sensor state to match demo scenario (called when scenario changes)
  void updateDemoSensorState() {
    final demoService = ref.read(demoServiceProvider);
    if (demoService.isDemoMode) {
      final scenario = demoService.currentScenario;
      state = state.copyWith(
        activity: scenario.activity,
        speed: scenario.speed,
        carBluetoothConnected: scenario.isCarConnected,
        wifiSsid: scenario.wifiSsid,
        locationVector: scenario.location,
        lastUpdate: scenario.time,
      );
    }
  }

  /// Manual trigger for immediate inference with notifications and feedback tracking
  Future<InferenceResponse> triggerInference() async {
    final apiService = ref.read(apiServiceProvider);
    final calendarService = CalendarService();
    final notificationService = NotificationService();
    final feedbackTracker = FeedbackTracker();
    final demoService = ref.read(demoServiceProvider);
    
    // Use demo context if in demo mode
    UserContext context;
    if (demoService.isDemoMode) {
      context = demoService.getCurrentDemoContext();
      // Update sensor state to match demo scenario
      updateDemoSensorState();
    } else {
      // Revert to real mock sensor data when exiting demo mode
      _updateMockSensorData();
      
      // Check for calendar events (only in real mode)
      bool hasUpcomingMeeting = false;
      if (calendarService.isSignedIn) {
        hasUpcomingMeeting = await calendarService.hasUpcomingMeeting();
      }
      
      context = UserContext(
        timestamp: DateTime.now(),
        activityType: state.activity,
        speed: state.speed,
        isConnectedToCarBluetooth: state.carBluetoothConnected,
        wifiSsid: state.wifiSsid,
        locationVector: state.locationVector,
        additionalData: {
          'has_upcoming_meeting': hasUpcomingMeeting,
        },
      );
    }

    final response = await apiService.inferSchedule(context);
    
    // Update feedback status for all tasks
    final tasksWithFeedback = await feedbackTracker.updateFeedbackStatus(
      response.suggestedTasks
    );
    
    // Show notifications for high-confidence tasks (>= 60%) that haven't received feedback
    for (final task in tasksWithFeedback) {
      if (!task.feedbackGiven && task.confidence >= 0.60) {
        await notificationService.showTaskNotification(task);
      }
    }
    
    // Store updated tasks
    ref.read(inferredTasksProvider.notifier).state = tasksWithFeedback;
    
    return response;
  }

  @override
  void dispose() {
    _updateTimer?.cancel();
    _mockSensorTimer?.cancel();
    super.dispose();
  }
}

// Providers
final apiServiceProvider = Provider<ApiService>((ref) {
  return ApiService();
});

final sensorServiceProvider = StateNotifierProvider<SensorService, SensorData>((ref) {
  return SensorService(ref);
});

final inferredTasksProvider = StateProvider<List<InferredTask>>((ref) => []);
