import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/models.dart';

class ApiService {
  // For Android emulator use: 10.0.2.2:8000
  // For real phone on same WiFi use your Mac's IP: 192.168.209.106:8000
  // Current Mac IP detected: 192.168.209.106
  static const String baseUrl = 'http://192.168.209.106:8000';
  
  final http.Client _client = http.Client();

  /// Send sensor context to backend and get inferred tasks
  Future<InferenceResponse> inferSchedule(UserContext context) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/infer'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(context.toJson()),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return InferenceResponse.fromJson(jsonDecode(response.body));
      } else {
        throw Exception('Failed to infer schedule: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  /// Send user feedback for reinforcement learning
  Future<Map<String, dynamic>> sendFeedback({
    required int ruleId,
    required String outcome, // 'positive' or 'negative'
    Map<String, dynamic>? contextSnapshot,
  }) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/feedback'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'rule_id': ruleId,
          'outcome': outcome,
          'context_snapshot': contextSnapshot,
        }),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Failed to send feedback: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Feedback error: $e');
    }
  }

  /// Send natural language chat input
  Future<Map<String, dynamic>> sendChatMessage(
    String message, {
    Map<String, dynamic>? context,
  }) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/chat-input'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'user_message': message,
          'context': context,
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Failed to process chat: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Chat error: $e');
    }
  }

  /// Parse natural language into structured task with confidence
  Future<ParsedTask> parseTask(String userInput, {Map<String, dynamic>? currentContext}) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/parse-task'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'user_input': userInput,
          'current_context': currentContext,
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return ParsedTask.fromJson(jsonDecode(response.body));
      } else {
        throw Exception('Failed to parse task: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Parse error: $e');
    }
  }

  /// Create a confirmed task
  Future<TaskRule> createTask(TaskCreationRequest taskRequest) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/create-task'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(taskRequest.toJson()),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return TaskRule.fromJson(jsonDecode(response.body));
      } else {
        throw Exception('Failed to create task: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Task creation error: $e');
    }
  }

  /// Get all task rules
  Future<List<Map<String, dynamic>>> getRules() async {
    try {
      final response = await _client.get(
        Uri.parse('$baseUrl/rules'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        return List<Map<String, dynamic>>.from(jsonDecode(response.body));
      } else {
        throw Exception('Failed to get rules: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Rules fetch error: $e');
    }
  }

  /// Sync calendar events to backend for intelligent reminders
  Future<Map<String, dynamic>> syncCalendarEvents(List<Map<String, dynamic>> events) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/calendar/sync'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'events': events,
        }),
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Failed to sync calendar: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Calendar sync error: $e');
    }
  }

  /// Get upcoming calendar events from backend
  Future<List<Map<String, dynamic>>> getUpcomingCalendarTasks({int hoursAhead = 24}) async {
    try {
      final response = await _client.get(
        Uri.parse('$baseUrl/calendar/upcoming?hours_ahead=$hoursAhead'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return List<Map<String, dynamic>>.from(data['events'] ?? []);
      } else {
        throw Exception('Failed to get calendar tasks: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Calendar fetch error: $e');
    }
  }

  /// Health check
  Future<bool> healthCheck() async {
    try {
      final response = await _client.get(
        Uri.parse('$baseUrl/'),
      ).timeout(const Duration(seconds: 3));

      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  void dispose() {
    _client.close();
  }
}
