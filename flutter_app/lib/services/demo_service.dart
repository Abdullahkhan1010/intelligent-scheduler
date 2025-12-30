import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/models.dart';

/// Demo Mode Service for simulating various scenarios
class DemoService {
  bool _isDemoMode = false;
  int _currentScenarioIndex = 0;
  
  bool get isDemoMode => _isDemoMode;
  int get currentScenarioIndex => _currentScenarioIndex;

  void toggleDemoMode() {
    _isDemoMode = !_isDemoMode;
  }

  void setScenario(int index) {
    _currentScenarioIndex = index;
  }

  /// Predefined demo scenarios
  final List<DemoScenario> scenarios = [
    DemoScenario(
      name: '🏠 Morning at Home',
      description: 'Simulates waking up at home on a weekday',
      time: DateTime(2025, 12, 19, 7, 30),
      activity: 'STILL',
      location: 'home',
      speed: 0.0,
      isCarConnected: false,
      wifiSsid: 'HomeNetwork',
    ),
    DemoScenario(
      name: '🚗 Commute to Work',
      description: 'Driving to work in the morning',
      time: DateTime(2025, 12, 19, 8, 15),
      activity: 'IN_VEHICLE',
      location: 'leaving_home',
      speed: 45.0,
      isCarConnected: true,
      wifiSsid: null,
    ),
    DemoScenario(
      name: '💼 At the Office',
      description: 'Working at the office during lunch time',
      time: DateTime(2025, 12, 19, 12, 30),
      activity: 'STILL',
      location: 'work',
      speed: 0.0,
      isCarConnected: false,
      wifiSsid: 'OfficeWiFi',
    ),
    DemoScenario(
      name: '🚗 Leaving Work',
      description: 'Driving home from work in the evening',
      time: DateTime(2025, 12, 19, 17, 45),
      activity: 'IN_VEHICLE',
      location: 'leaving_work',
      speed: 40.0,
      isCarConnected: true,
      wifiSsid: null,
    ),
    DemoScenario(
      name: '🏠 Evening at Home',
      description: 'Relaxing at home after work',
      time: DateTime(2025, 12, 19, 19, 00),
      activity: 'STILL',
      location: 'home',
      speed: 0.0,
      isCarConnected: false,
      wifiSsid: 'HomeNetwork',
    ),
    DemoScenario(
      name: '🏃 Weekend Walk',
      description: 'Walking around the neighborhood on Saturday',
      time: DateTime(2025, 12, 21, 10, 00),
      activity: 'WALKING',
      location: 'near_home',
      speed: 5.0,
      isCarConnected: false,
      wifiSsid: null,
    ),
    DemoScenario(
      name: '🛒 Weekend Errands',
      description: 'Driving around town on Saturday afternoon',
      time: DateTime(2025, 12, 21, 14, 30),
      activity: 'IN_VEHICLE',
      location: 'downtown',
      speed: 30.0,
      isCarConnected: true,
      wifiSsid: null,
    ),
  ];

  DemoScenario get currentScenario => scenarios[_currentScenarioIndex];

  UserContext getCurrentDemoContext() {
    final scenario = currentScenario;
    return UserContext(
      timestamp: scenario.time,
      activityType: scenario.activity,
      speed: scenario.speed,
      isConnectedToCarBluetooth: scenario.isCarConnected,
      wifiSsid: scenario.wifiSsid,
      locationVector: scenario.location,
      additionalData: {
        'demo_mode': true,
        'scenario_name': scenario.name,
      },
    );
  }

  void nextScenario() {
    _currentScenarioIndex = (_currentScenarioIndex + 1) % scenarios.length;
  }

  void previousScenario() {
    _currentScenarioIndex = (_currentScenarioIndex - 1 + scenarios.length) % scenarios.length;
  }
}

class DemoScenario {
  final String name;
  final String description;
  final DateTime time;
  final String activity;
  final String location;
  final double speed;
  final bool isCarConnected;
  final String? wifiSsid;

  DemoScenario({
    required this.name,
    required this.description,
    required this.time,
    required this.activity,
    required this.location,
    required this.speed,
    required this.isCarConnected,
    this.wifiSsid,
  });

  String get timeOfDay {
    final hour = time.hour;
    if (hour < 12) return 'Morning';
    if (hour < 17) return 'Afternoon';
    if (hour < 21) return 'Evening';
    return 'Night';
  }

  String get dayType {
    final weekday = time.weekday;
    return weekday < 6 ? 'Weekday' : 'Weekend';
  }
}

/// Provider for demo service
final demoServiceProvider = StateNotifierProvider<DemoServiceNotifier, DemoService>((ref) {
  return DemoServiceNotifier();
});

class DemoServiceNotifier extends StateNotifier<DemoService> {
  DemoServiceNotifier() : super(DemoService());

  void toggleDemoMode() {
    state.toggleDemoMode();
    state = DemoService()
      .._isDemoMode = state._isDemoMode
      .._currentScenarioIndex = state._currentScenarioIndex;
  }

  void setScenario(int index) {
    state.setScenario(index);
    state = DemoService()
      .._isDemoMode = state._isDemoMode
      .._currentScenarioIndex = index;
  }

  void nextScenario() {
    state.nextScenario();
    state = DemoService()
      .._isDemoMode = state._isDemoMode
      .._currentScenarioIndex = state._currentScenarioIndex;
  }

  void previousScenario() {
    state.previousScenario();
    state = DemoService()
      .._isDemoMode = state._isDemoMode
      .._currentScenarioIndex = state._currentScenarioIndex;
  }
}
