// Data Models for Flutter App

class UserContext {
  final DateTime timestamp;
  final String activityType;
  final double speed;
  final bool isConnectedToCarBluetooth;
  final String? wifiSsid;
  final String? locationVector;
  final Map<String, dynamic>? additionalData;

  UserContext({
    required this.timestamp,
    required this.activityType,
    this.speed = 0.0,
    this.isConnectedToCarBluetooth = false,
    this.wifiSsid,
    this.locationVector,
    this.additionalData,
  });

  Map<String, dynamic> toJson() => {
        'timestamp': timestamp.toIso8601String(),
        'activity_type': activityType,
        'speed': speed,
        'is_connected_to_car_bluetooth': isConnectedToCarBluetooth,
        'wifi_ssid': wifiSsid,
        'location_vector': locationVector,
        'additional_data': additionalData,
      };
}

class InferredTask {
  final int ruleId;
  final String taskName;
  final String? taskDescription;
  final double confidence;
  final String reasoning;
  final Map<String, dynamic> matchedConditions;
  bool feedbackGiven; // Track if user already provided feedback
  final DateTime suggestedAt; // When this task was suggested

  InferredTask({
    required this.ruleId,
    required this.taskName,
    this.taskDescription,
    required this.confidence,
    required this.reasoning,
    required this.matchedConditions,
    this.feedbackGiven = false,
    DateTime? suggestedAt,
  }) : suggestedAt = suggestedAt ?? DateTime.now();

  factory InferredTask.fromJson(Map<String, dynamic> json) {
    return InferredTask(
      ruleId: json['rule_id'],
      taskName: json['task_name'],
      taskDescription: json['task_description'],
      confidence: (json['confidence'] as num).toDouble(),
      reasoning: json['reasoning'],
      matchedConditions: json['matched_conditions'] ?? {},
    );
  }
}

class InferenceResponse {
  final DateTime timestamp;
  final Map<String, dynamic> contextSummary;
  final List<InferredTask> suggestedTasks;
  final int totalRulesEvaluated;

  InferenceResponse({
    required this.timestamp,
    required this.contextSummary,
    required this.suggestedTasks,
    required this.totalRulesEvaluated,
  });

  factory InferenceResponse.fromJson(Map<String, dynamic> json) {
    return InferenceResponse(
      timestamp: DateTime.parse(json['timestamp']),
      contextSummary: json['context_summary'],
      suggestedTasks: (json['suggested_tasks'] as List)
          .map((task) => InferredTask.fromJson(task))
          .toList(),
      totalRulesEvaluated: json['total_rules_evaluated'],
    );
  }
}

class ChatMessage {
  final String message;
  final bool isUser;
  final DateTime timestamp;
  final String? interpretation;
  final ParsedTask? parsedTask; // Optional parsed task data

  ChatMessage({
    required this.message,
    required this.isUser,
    required this.timestamp,
    this.interpretation,
    this.parsedTask,
  });
}

class ParsedTask {
  final bool success;
  final double confidence;
  final String? parsedTaskName;
  final String? parsedDescription;
  final String? parsedTime;
  final String? parsedDate;
  final String? parsedLocation;
  final String? parsedPriority;
  final int? parsedDurationMinutes;
  final Map<String, dynamic> extractionDetails;
  final Map<String, double> confidenceBreakdown;
  final bool requiresConfirmation;
  final List<String> suggestions;
  final String originalInput;

  ParsedTask({
    required this.success,
    required this.confidence,
    this.parsedTaskName,
    this.parsedDescription,
    this.parsedTime,
    this.parsedDate,
    this.parsedLocation,
    this.parsedPriority,
    this.parsedDurationMinutes,
    required this.extractionDetails,
    required this.confidenceBreakdown,
    required this.requiresConfirmation,
    required this.suggestions,
    required this.originalInput,
  });

  factory ParsedTask.fromJson(Map<String, dynamic> json) {
    return ParsedTask(
      success: json['success'] ?? false,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      parsedTaskName: json['parsed_task_name'],
      parsedDescription: json['parsed_description'],
      parsedTime: json['parsed_time'],
      parsedDate: json['parsed_date'],
      parsedLocation: json['parsed_location'],
      parsedPriority: json['parsed_priority'],
      parsedDurationMinutes: json['parsed_duration_minutes'],
      extractionDetails: Map<String, dynamic>.from(json['extraction_details'] ?? {}),
      confidenceBreakdown: (json['confidence_breakdown'] as Map<String, dynamic>?)
              ?.map((key, value) => MapEntry(key, (value as num).toDouble())) ??
          {},
      requiresConfirmation: json['requires_confirmation'] ?? true,
      suggestions: List<String>.from(json['suggestions'] ?? []),
      originalInput: json['original_input'] ?? '',
    );
  }
}

class TaskCreationRequest {
  final String taskName;
  final String taskDescription;
  final DateTime? scheduledTime;
  final String? locationContext;
  final String priority;
  final int? durationMinutes;
  final Map<String, dynamic>? triggerConditions;

  TaskCreationRequest({
    required this.taskName,
    required this.taskDescription,
    this.scheduledTime,
    this.locationContext,
    this.priority = 'medium',
    this.durationMinutes,
    this.triggerConditions,
  });

  Map<String, dynamic> toJson() => {
        'task_name': taskName,
        'task_description': taskDescription,
        'scheduled_time': scheduledTime?.toIso8601String(),
        'location_context': locationContext,
        'priority': priority,
        'duration_minutes': durationMinutes,
        'trigger_conditions': triggerConditions,
      };
}

class TaskRule {
  final int id;
  final String taskName;
  final String? taskDescription;
  final Map<String, dynamic> triggerCondition;
  final double currentProbabilityWeight;
  final bool isActive;
  final DateTime createdAt;
  final DateTime updatedAt;

  TaskRule({
    required this.id,
    required this.taskName,
    this.taskDescription,
    required this.triggerCondition,
    required this.currentProbabilityWeight,
    required this.isActive,
    required this.createdAt,
    required this.updatedAt,
  });

  factory TaskRule.fromJson(Map<String, dynamic> json) {
    return TaskRule(
      id: json['id'],
      taskName: json['task_name'],
      taskDescription: json['task_description'],
      triggerCondition: Map<String, dynamic>.from(json['trigger_condition'] ?? {}),
      currentProbabilityWeight:
          (json['current_probability_weight'] as num).toDouble(),
      isActive: json['is_active'] ?? true,
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }}