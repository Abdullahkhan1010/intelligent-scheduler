import 'package:workmanager/workmanager.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;

/// Background service for continuous task inference and notifications
class BackgroundService {
  static const String taskInferenceTask = 'taskInferenceTask';
  static const String calendarSyncTask = 'calendarSyncTask';
  
  static final FlutterLocalNotificationsPlugin _notifications = 
      FlutterLocalNotificationsPlugin();

  /// Initialize background tasks
  static Future<void> initialize() async {
    await Workmanager().initialize(
      callbackDispatcher,
    );
    
    // Initialize notifications
    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosSettings = DarwinInitializationSettings();
    const initSettings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );
    await _notifications.initialize(initSettings);
  }

  /// Start periodic background inference (every 15 minutes)
  static Future<void> startBackgroundInference() async {
    await Workmanager().registerPeriodicTask(
      'task-inference',
      taskInferenceTask,
      frequency: const Duration(minutes: 15),
      constraints: Constraints(
        networkType: NetworkType.connected,
      ),
    );
    print('✅ Background inference started (every 15 minutes)');
  }

  /// Start periodic calendar sync (every 2 hours)
  static Future<void> startCalendarSync() async {
    await Workmanager().registerPeriodicTask(
      'calendar-sync',
      calendarSyncTask,
      frequency: const Duration(hours: 2),
      constraints: Constraints(
        networkType: NetworkType.connected,
      ),
    );
    print('✅ Background calendar sync started (every 2 hours)');
  }

  /// Stop all background tasks
  static Future<void> stopAll() async {
    await Workmanager().cancelAll();
    print('🛑 All background tasks stopped');
  }

  /// Show notification for suggested task
  static Future<void> showTaskNotification({
    required int id,
    required String title,
    required String body,
    required double confidence,
  }) async {
    const androidDetails = AndroidNotificationDetails(
      'task_suggestions',
      'Task Suggestions',
      channelDescription: 'Intelligent task reminders based on your context',
      importance: Importance.high,
      priority: Priority.high,
      icon: '@mipmap/ic_launcher',
    );
    
    const iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
    );
    
    final details = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );
    
    await _notifications.show(
      id,
      title,
      '$body • ${(confidence * 100).toInt()}% confidence',
      details,
    );
  }
}

/// Background callback dispatcher (runs in isolate)
@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    print('🔄 Background task executing: $task');
    
    try {
      if (task == BackgroundService.taskInferenceTask) {
        await _performInference();
      } else if (task == BackgroundService.calendarSyncTask) {
        await _syncCalendar();
      }
      return Future.value(true);
    } catch (e) {
      print('❌ Background task error: $e');
      return Future.value(false);
    }
  });
}

/// Perform inference and show notifications
Future<void> _performInference() async {
  try {
    // Get current context from device (simplified)
    final context = {
      'activity_type': 'STILL',
      'speed': 0.0,
      'location_vector': 'unknown',
      'is_connected_to_car_bluetooth': false,
    };
    
    // Call inference endpoint
    final response = await http.post(
      Uri.parse('http://10.0.2.2:8000/infer'),  // Android emulator localhost
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(context),
    ).timeout(const Duration(seconds: 10));
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      final tasks = data['suggested_tasks'] as List;
      
      print('✅ Got ${tasks.length} suggested tasks in background');
      
      // Show notifications for high-confidence tasks
      for (var i = 0; i < tasks.length && i < 3; i++) {
        final task = tasks[i];
        final confidence = task['confidence'] as double;
        
        if (confidence >= 0.6) {
          await BackgroundService.showTaskNotification(
            id: task['rule_id'],
            title: task['task_name'],
            body: task['reasoning'],
            confidence: confidence,
          );
        }
      }
    }
  } catch (e) {
    print('Error performing background inference: $e');
  }
}

/// Sync calendar in background
Future<void> _syncCalendar() async {
  print('🗓️ Background calendar sync...');
  // Calendar sync requires authentication, which is handled in foreground
  // This is a placeholder for future implementation
}
