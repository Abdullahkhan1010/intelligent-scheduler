import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/models.dart';
import 'api_service.dart';
import 'feedback_tracker.dart';

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  final FlutterLocalNotificationsPlugin _notifications = FlutterLocalNotificationsPlugin();
  bool _initialized = false;
  
  // Callback to refresh tasks after feedback
  Function()? onFeedbackGiven;

  /// Initialize notification service with feedback callback
  Future<void> initialize({Function()? onFeedbackGiven}) async {
    if (_initialized) {
      // Update callback if provided
      if (onFeedbackGiven != null) {
        this.onFeedbackGiven = onFeedbackGiven;
      }
      return;
    }

    this.onFeedbackGiven = onFeedbackGiven;

    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    const initSettings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    await _notifications.initialize(
      initSettings,
      onDidReceiveNotificationResponse: _onNotificationTapped,
    );

    // Request permissions for Android 13+
    await _notifications
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
        ?.requestNotificationsPermission();

    _initialized = true;
  }

  /// Handle notification tap and action button presses
  void _onNotificationTapped(NotificationResponse response) {
    debugPrint('Notification response: ${response.payload}, actionId: ${response.actionId}');
    
    // Check if this is an action button press (Accept/Reject)
    if (response.actionId != null) {
      _handleActionButton(response);
      return;
    }
    
    // Regular notification tap - just log it
    debugPrint('Notification tapped: ${response.payload}');
  }
  
  /// Handle Accept/Reject button presses from notifications
  Future<void> _handleActionButton(NotificationResponse response) async {
    final actionId = response.actionId!;
    final payload = response.payload;
    
    if (payload == null) return;
    
    // Parse payload: format is "ruleId|taskName"
    final parts = payload.split('|');
    if (parts.length != 2) return;
    
    final ruleId = int.tryParse(parts[0]);
    final taskName = parts[1];
    
    if (ruleId == null) return;
    
    // Determine if this is accept or reject
    final isAccept = actionId.startsWith('accept_');
    final outcome = isAccept ? 'positive' : 'negative';
    
    print('📱 Notification action: ${isAccept ? "ACCEPT" : "REJECT"} for task "$taskName" (rule $ruleId)');
    print('   Sending feedback: outcome=$outcome to backend');
    
    try {
      // Send feedback to backend
      final apiService = ApiService();
      await apiService.sendFeedback(
        ruleId: ruleId,
        outcome: outcome,
        contextSnapshot: {}, // Context not available here, but backend will use recent context
      );
      
      print('✅ Feedback sent successfully! Task weight will ${isAccept ? "INCREASE" : "DECREASE"}');
      
      // Mark feedback as given locally
      final feedbackTracker = FeedbackTracker();
      // Note: We can't access the full InferredTask here, so we'll rely on backend update
      
      // Trigger refresh callback to update UI
      if (onFeedbackGiven != null) {
        print('🔄 Triggering inference refresh...');
        onFeedbackGiven!();
      }
      
    } catch (e) {
      print('❌ Failed to send notification feedback: $e');
    }
  }

  /// Show notification for high-confidence task (>= 60%)
  Future<void> showTaskNotification(InferredTask task) async {
    if (!_initialized) await initialize();

    // Only show notifications for tasks with >= 60% confidence
    if (task.confidence < 0.60) return;
    
    // Check if notification already shown for this task
    final alreadyShown = await _hasNotificationBeenShown(task);
    if (alreadyShown) {
      print('⏭️  Notification already shown for "${task.taskName}" - skipping');
      return;
    }

    // Create notification message
    final String title = task.taskName;
    final String body = _buildNotificationBody(task);

    // Add action buttons (Accept/Reject)
    final androidDetails = AndroidNotificationDetails(
      'task_suggestions',
      'Task Suggestions',
      channelDescription: 'AI-powered context-aware task recommendations',
      importance: Importance.high,
      priority: Priority.high,
      showWhen: true,
      enableVibration: true,
      enableLights: true,
      actions: <AndroidNotificationAction>[
        AndroidNotificationAction(
          'accept_${task.ruleId}',
          '✓ Accept',
          showsUserInterface: true,
        ),
        AndroidNotificationAction(
          'reject_${task.ruleId}',
          '✗ Reject',
          showsUserInterface: true,
        ),
      ],
    );

    const iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
    );

    final notificationDetails = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );

    await _notifications.show(
      task.ruleId, // Use rule ID as notification ID
      title,
      body,
      notificationDetails,
      payload: '${task.ruleId}|${task.taskName}', // Pass rule ID and task name
    );
    
    // Mark notification as shown
    await _markNotificationShown(task);
    print('📬 Notification sent for "${task.taskName}" (confidence: ${(task.confidence * 100).toInt()}%)');
  }
  
  /// Generate unique key for notification tracking
  /// Format: notification_<taskName>_<date>_<hour>
  String _generateNotificationKey(InferredTask task) {
    final date = task.suggestedAt;
    final dateStr = '${date.year}${date.month.toString().padLeft(2, '0')}${date.day.toString().padLeft(2, '0')}';
    final hourStr = date.hour.toString().padLeft(2, '0');
    return 'notification_${task.taskName}_${dateStr}_$hourStr';
  }
  
  /// Check if notification has already been shown for this task
  Future<bool> _hasNotificationBeenShown(InferredTask task) async {
    final prefs = await SharedPreferences.getInstance();
    final key = _generateNotificationKey(task);
    return prefs.getBool(key) ?? false;
  }
  
  /// Mark notification as shown for this task
  Future<void> _markNotificationShown(InferredTask task) async {
    final prefs = await SharedPreferences.getInstance();
    final key = _generateNotificationKey(task);
    await prefs.setBool(key, true);
    
    // Also store timestamp for cleanup
    final timestampKey = '${key}_timestamp';
    await prefs.setInt(timestampKey, DateTime.now().millisecondsSinceEpoch);
  }
  
  /// Clean old notification records (older than 24 hours)
  Future<void> cleanOldNotificationRecords() async {
    final prefs = await SharedPreferences.getInstance();
    final keys = prefs.getKeys().where((key) => key.startsWith('notification_'));
    final now = DateTime.now().millisecondsSinceEpoch;
    final oneDayAgo = now - (24 * 60 * 60 * 1000);
    
    for (final key in keys) {
      if (key.endsWith('_timestamp')) continue;
      final timestampKey = '${key}_timestamp';
      final timestamp = prefs.getInt(timestampKey);
      
      if (timestamp != null && timestamp < oneDayAgo) {
        await prefs.remove(key);
        await prefs.remove(timestampKey);
      }
    }
  }

  /// Build notification message with context
  String _buildNotificationBody(InferredTask task) {
    final buffer = StringBuffer();
    buffer.write(task.taskDescription ?? task.taskName);

    // Add context clues from matched conditions
    final conditions = task.matchedConditions;
    if (conditions.containsKey('activity')) {
      final activity = conditions['activity'];
      if (activity == 'STILL') {
        buffer.write(' - You are stationary');
      } else if (activity == 'IN_VEHICLE') {
        buffer.write(' - You are driving');
      }
    }

    if (conditions.containsKey('time')) {
      buffer.write(' at ${conditions['time']}');
    }

    return buffer.toString();
  }

  /// Show multiple notifications for tasks above threshold
  Future<void> showTaskNotifications(List<InferredTask> tasks) async {
    for (final task in tasks) {
      if (task.confidence >= 0.40) {
        await showTaskNotification(task);
      }
    }
  }

  /// Cancel all notifications
  Future<void> cancelAll() async {
    await _notifications.cancelAll();
  }

  /// Cancel specific notification by task name
  Future<void> cancelNotification(String taskName) async {
    await _notifications.cancel(taskName.hashCode);
  }
}
