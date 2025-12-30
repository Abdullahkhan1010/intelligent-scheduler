import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../models/models.dart';
import '../services/sensor_service.dart';

class ChatView extends ConsumerStatefulWidget {
  const ChatView({super.key});

  @override
  ConsumerState<ChatView> createState() => _ChatViewState();
}

class _ChatViewState extends ConsumerState<ChatView> {
  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<ChatMessage> _messages = [];
  bool _isProcessing = false;

  @override
  void initState() {
    super.initState();
    // Add welcome message
    _messages.add(
      ChatMessage(
        message: 'Hi! I\'m your intelligent scheduler. You can:\n\n'
            '• Tell me about appointments\n'
            '• Ask about your schedule\n'
            '• Provide feedback on suggestions\n\n'
            'Try: "I have a dentist appointment on the way home at 5 PM"',
        isUser: false,
        timestamp: DateTime.now(),
      ),
    );
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      Future.delayed(const Duration(milliseconds: 300), () {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      });
    }
  }

  Future<void> _sendMessage(String text) async {
    if (text.trim().isEmpty) return;

    // OPTIMISTIC UPDATE: Add user message and show processing immediately
    setState(() {
      _messages.add(
        ChatMessage(
          message: text,
          isUser: true,
          timestamp: DateTime.now(),
        ),
      );
      _messages.add(
        ChatMessage(
          message: '🤔 Analyzing your request...',
          isUser: false,
          timestamp: DateTime.now(),
        ),
      );
      _isProcessing = true;
    });

    _messageController.clear();
    _scrollToBottom();

    // Parse in background (non-blocking)
    _parseTaskInBackground(text);
  }

  void _parseTaskInBackground(String text) async {
    try {
      final apiService = ref.read(apiServiceProvider);
      final sensorData = ref.read(sensorServiceProvider);
      
      // Parse task with confidence scoring
      final parsedTask = await apiService.parseTask(
        text,
        currentContext: {
          'current_activity': sensorData.activity,
          'current_location': sensorData.locationVector,
        },
      );

      // Replace loading message with parsed result
      if (mounted) {
        setState(() {
          _messages.removeLast(); // Remove "Analyzing..." message
          _messages.add(
            ChatMessage(
              message: _generateParseMessage(parsedTask),
              isUser: false,
              timestamp: DateTime.now(),
              interpretation: _generateInterpretation(parsedTask),
              parsedTask: parsedTask,
            ),
          );
        });
        _scrollToBottom();
      }
    } catch (e) {
      // GRACEFUL ERROR HANDLING
      if (mounted) {
        setState(() {
          _messages.removeLast(); // Remove "Analyzing..." message
          _messages.add(
            ChatMessage(
              message: '❌ ${_getErrorMessage(e)}\n\nPlease try rephrasing or check your connection.',
              isUser: false,
              timestamp: DateTime.now(),
            ),
          );
        });
        _scrollToBottom();
      }
    } finally {
      if (mounted) {
        setState(() => _isProcessing = false);
      }
    }
  }

  String _generateParseMessage(ParsedTask task) {
    if (!task.success) {
      return 'I had trouble understanding that. ${task.suggestions.join(" ")}';
    }

    String message = 'I understood: "${task.parsedTaskName}"';
    
    if (task.parsedTime != null || task.parsedDate != null) {
      message += '\n📅 ';
      if (task.parsedDate != null) message += 'Date: ${task.parsedDate} ';
      if (task.parsedTime != null) message += 'Time: ${task.parsedTime}';
    }
    
    if (task.parsedLocation != null) {
      message += '\n📍 Location: ${task.parsedLocation}';
    }
    
    if (task.parsedPriority != null) {
      final emoji = task.parsedPriority == 'high' ? '🔴' : 
                    task.parsedPriority == 'low' ? '🟢' : '🟡';
      message += '\n$emoji Priority: ${task.parsedPriority}';
    }

    if (task.suggestions.isNotEmpty) {
      message += '\n\n💡 ${task.suggestions.first}';
    }

    return message;
  }

  String _generateInterpretation(ParsedTask task) {
    if (!task.success) return 'Failed to parse task';
    
    final details = <String>[];
    task.extractionDetails.forEach((key, value) {
      if (value != null && value.toString().isNotEmpty) {
        details.add('$key: $value');
      }
    });
    
    return details.join('\n');
  }

  Future<void> _confirmAndCreateTask(ParsedTask parsedTask) async {
    // OPTIMISTIC UPDATE: Show success message immediately
    setState(() {
      _messages.add(
        ChatMessage(
          message: '⏳ Creating task...',
          isUser: false,
          timestamp: DateTime.now(),
        ),
      );
      _isProcessing = true;
    });

    _scrollToBottom();

    // Create task in background
    _createTaskInBackground(parsedTask);
  }

  void _createTaskInBackground(ParsedTask parsedTask) async {
    try {
      final apiService = ref.read(apiServiceProvider);
      
      // Convert parsed task to creation request
      DateTime? scheduledTime;
      if (parsedTask.parsedDate != null && parsedTask.parsedTime != null) {
        scheduledTime = DateTime.parse('${parsedTask.parsedDate}T${parsedTask.parsedTime}:00');
      } else if (parsedTask.parsedDate != null) {
        scheduledTime = DateTime.parse(parsedTask.parsedDate!);
      }

      final taskRequest = TaskCreationRequest(
        taskName: parsedTask.parsedTaskName ?? 'Unnamed Task',
        taskDescription: parsedTask.parsedDescription ?? parsedTask.originalInput,
        scheduledTime: scheduledTime,
        locationContext: parsedTask.parsedLocation,
        priority: parsedTask.parsedPriority ?? 'medium',
        durationMinutes: parsedTask.parsedDurationMinutes,
      );

      final createdTask = await apiService.createTask(taskRequest);

      // Update the loading message with success
      if (mounted) {
        setState(() {
          // Replace loading message with success message
          _messages.removeLast();
          _messages.add(
            ChatMessage(
              message: '✅ Task created successfully!\n'
                  'ID: #${createdTask.id}\n'
                  'You\'ll be notified at the optimal time.',
              isUser: false,
              timestamp: DateTime.now(),
            ),
          );
        });
        _scrollToBottom();
      }
    } catch (e) {
      // GRACEFUL ERROR HANDLING
      if (mounted) {
        setState(() {
          // Replace loading message with error message
          _messages.removeLast();
          _messages.add(
            ChatMessage(
              message: '❌ Failed to create task: ${_getErrorMessage(e)}\n\n'
                  'Tap retry to try again.',
              isUser: false,
              timestamp: DateTime.now(),
            ),
          );
          
          // Add retry option
          _messages.add(
            ChatMessage(
              message: '🔄 Retry creating task?',
              isUser: false,
              timestamp: DateTime.now(),
              parsedTask: parsedTask, // Keep parsed task for retry
            ),
          );
        });
        _scrollToBottom();
      }
    } finally {
      if (mounted) {
        setState(() => _isProcessing = false);
      }
    }
  }

  String _getErrorMessage(dynamic error) {
    final errorStr = error.toString();
    if (errorStr.contains('SocketException') || errorStr.contains('Connection')) {
      return 'No network connection';
    } else if (errorStr.contains('TimeoutException') || errorStr.contains('timeout')) {
      return 'Server timeout';
    } else if (errorStr.contains('404')) {
      return 'Service unavailable';
    } else {
      return errorStr.replaceAll('Exception:', '').trim();
    }
  }



  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              theme.colorScheme.primary,
              theme.colorScheme.secondary,
            ],
            stops: const [0.0, 0.3],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              // Custom App Bar
              Padding(
                padding: const EdgeInsets.all(20),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'AI Assistant',
                          style: TextStyle(
                            fontSize: 28,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                        SizedBox(height: 4),
                        Text(
                          'Chat with your scheduler',
                          style: TextStyle(
                            fontSize: 14,
                            color: Colors.white70,
                          ),
                        ),
                      ],
                    ),
                    Container(
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: IconButton(
                        icon: const Icon(Icons.info_outline, color: Colors.white),
                        onPressed: _showHelpDialog,
                      ),
                    ),
                  ],
                ),
              ),
              
              // Chat Area
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    color: theme.scaffoldBackgroundColor,
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(30),
                      topRight: Radius.circular(30),
                    ),
                  ),
                  child: Column(
                    children: [
                      // Chat Messages
                      Expanded(
                        child: ListView.builder(
                          controller: _scrollController,
                          padding: const EdgeInsets.all(20),
                          itemCount: _messages.length,
                          itemBuilder: (context, index) {
                            return _buildChatBubble(_messages[index]);
                          },
                        ),
                      ),

                      // Processing Indicator
                      if (_isProcessing)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                          child: Row(
                            children: [
                              SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: theme.colorScheme.primary,
                                ),
                              ),
                              const SizedBox(width: 12),
                              Text(
                                'AI is thinking...',
                                style: TextStyle(
                                  color: Colors.grey.shade600,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ],
                          ),
                        ),

                      // Input Field
                      Container(
                        padding: const EdgeInsets.all(20),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.05),
                              blurRadius: 20,
                              offset: const Offset(0, -5),
                            ),
                          ],
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Expanded(
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                                decoration: BoxDecoration(
                                  color: Colors.grey.shade100,
                                  borderRadius: BorderRadius.circular(24),
                                ),
                                child: TextField(
                                  controller: _messageController,
                                  decoration: const InputDecoration(
                                    hintText: 'Type your message...',
                                    border: InputBorder.none,
                                    hintStyle: TextStyle(fontSize: 15),
                                  ),
                                  maxLines: null,
                                  textCapitalization: TextCapitalization.sentences,
                                  onSubmitted: _isProcessing ? null : _sendMessage,
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Container(
                              decoration: BoxDecoration(
                                gradient: LinearGradient(
                                  colors: [
                                    theme.colorScheme.primary,
                                    theme.colorScheme.secondary,
                                  ],
                                ),
                                borderRadius: BorderRadius.circular(20),
                                boxShadow: [
                                  BoxShadow(
                                    color: theme.colorScheme.primary.withValues(alpha: 0.3),
                                    blurRadius: 12,
                                    offset: const Offset(0, 4),
                                  ),
                                ],
                              ),
                              child: Material(
                                color: Colors.transparent,
                                child: InkWell(
                                  onTap: _isProcessing
                                      ? null
                                      : () => _sendMessage(_messageController.text),
                                  borderRadius: BorderRadius.circular(20),
                                  child: Container(
                                    padding: const EdgeInsets.all(14),
                                    child: const Icon(
                                      Icons.send_rounded,
                                      color: Colors.white,
                                      size: 22,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildChatBubble(ChatMessage message) {
    final isUser = message.isUser;
    final theme = Theme.of(context);
    
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 20),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.8,
        ),
        child: Column(
          crossAxisAlignment:
              isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
              decoration: BoxDecoration(
                gradient: isUser
                    ? LinearGradient(
                        colors: [
                          theme.colorScheme.primary,
                          theme.colorScheme.secondary,
                        ],
                      )
                    : null,
                color: isUser ? null : Colors.white,
                borderRadius: BorderRadius.circular(20).copyWith(
                  bottomRight: isUser ? const Radius.circular(4) : null,
                  bottomLeft: !isUser ? const Radius.circular(4) : null,
                ),
                boxShadow: [
                  BoxShadow(
                    color: (isUser ? theme.colorScheme.primary : Colors.grey).withValues(alpha: 0.15),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Confidence badge for parsed tasks
                  if (message.parsedTask != null && !isUser)
                    _buildConfidenceBadge(message.parsedTask!),
                  
                  Text(
                    message.message,
                    style: TextStyle(
                      color: isUser ? Colors.white : Colors.black87,
                      fontSize: 15,
                      height: 1.4,
                    ),
                  ),
                  
                  // Parsed task details
                  if (message.parsedTask != null && !isUser)
                    _buildParsedTaskDetails(message.parsedTask!),
                  
                  if (message.interpretation != null) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: isUser
                            ? Colors.white.withValues(alpha: 0.2)
                            : Colors.amber.shade50,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(
                          color: isUser
                              ? Colors.white.withValues(alpha: 0.3)
                              : Colors.amber.shade200,
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            Icons.psychology,
                            size: 16,
                            color: isUser ? Colors.white : Colors.amber.shade700,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              message.interpretation!,
                              style: TextStyle(
                                color: isUser ? Colors.white.withValues(alpha: 0.9) : Colors.black87,
                                fontSize: 12,
                                fontStyle: FontStyle.italic,
                              ),
                              maxLines: 3,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                  
                  // Confirmation buttons for parsed tasks
                  if (message.parsedTask != null && 
                      message.parsedTask!.success && 
                      !isUser)
                    _buildTaskConfirmationButtons(message.parsedTask!),
                ],
              ),
            ),
            const SizedBox(height: 6),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: Text(
                DateFormat('HH:mm').format(message.timestamp),
                style: TextStyle(
                  fontSize: 11,
                  color: Colors.grey.shade500,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConfidenceBadge(ParsedTask task) {
    final confidence = task.confidence;
    final confidencePercent = (confidence * 100).round();
    
    Color badgeColor;
    IconData badgeIcon;
    String confidenceLevel;
    
    if (confidence >= 0.8) {
      badgeColor = Colors.green;
      badgeIcon = Icons.check_circle;
      confidenceLevel = 'High Confidence';
    } else if (confidence >= 0.6) {
      badgeColor = Colors.amber;
      badgeIcon = Icons.warning_amber_rounded;
      confidenceLevel = 'Medium Confidence';
    } else {
      badgeColor = Colors.red;
      badgeIcon = Icons.help_outline;
      confidenceLevel = 'Low Confidence';
    }
    
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: badgeColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: badgeColor.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(badgeIcon, size: 14, color: badgeColor),
          const SizedBox(width: 6),
          Text(
            '$confidenceLevel ($confidencePercent%)',
            style: TextStyle(
              color: badgeColor,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildParsedTaskDetails(ParsedTask task) {
    if (!task.success) return const SizedBox.shrink();
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (task.confidenceBreakdown.isNotEmpty) ...[
          const SizedBox(height: 12),
          GestureDetector(
            onTap: () => _showConfidenceBreakdown(task),
            child: Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: Colors.blue.shade200),
              ),
              child: Row(
                children: [
                  Icon(Icons.info_outline, size: 16, color: Colors.blue.shade700),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Tap to see detailed confidence breakdown',
                      style: TextStyle(
                        color: Colors.blue.shade700,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  Icon(Icons.arrow_forward_ios, size: 12, color: Colors.blue.shade700),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildTaskConfirmationButtons(ParsedTask task) {
    return Container(
      margin: const EdgeInsets.only(top: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          // Cancel button
          TextButton(
            onPressed: () {
              setState(() {
                _messages.add(
                  ChatMessage(
                    message: 'Task cancelled. Let me know if you need to create a different task.',
                    isUser: false,
                    timestamp: DateTime.now(),
                  ),
                );
              });
              _scrollToBottom();
            },
            style: TextButton.styleFrom(
              foregroundColor: Colors.grey.shade600,
            ),
            child: const Text('Cancel'),
          ),
          const SizedBox(width: 8),
          // Confirm button
          ElevatedButton.icon(
            onPressed: () => _confirmAndCreateTask(task),
            icon: const Icon(Icons.check, size: 18),
            label: const Text('Confirm'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.primary,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showConfidenceBreakdown(ParsedTask task) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        minChildSize: 0.4,
        maxChildSize: 0.9,
        builder: (context, scrollController) => Container(
          decoration: BoxDecoration(
            color: Theme.of(context).scaffoldBackgroundColor,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
          ),
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'AI Confidence Breakdown',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(context),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                'How confident the AI is about each extracted field',
                style: TextStyle(
                  color: Colors.grey.shade600,
                  fontSize: 14,
                ),
              ),
              const SizedBox(height: 24),
              
              // Overall confidence
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      Theme.of(context).colorScheme.primary.withValues(alpha: 0.1),
                      Theme.of(context).colorScheme.secondary.withValues(alpha: 0.1),
                    ],
                  ),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.3),
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Overall Confidence',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Text(
                      '${(task.confidence * 100).round()}%',
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              
              // Field-by-field breakdown
              Expanded(
                child: ListView(
                  controller: scrollController,
                  children: [
                    ...task.confidenceBreakdown.entries.map((entry) {
                      final field = entry.key;
                      final confidence = entry.value;
                      final confidencePercent = (confidence * 100).round();
                      
                      return Container(
                        margin: const EdgeInsets.only(bottom: 16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  field.replaceAll('_', ' ').toUpperCase(),
                                  style: const TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    letterSpacing: 0.5,
                                  ),
                                ),
                                Text(
                                  '$confidencePercent%',
                                  style: TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.bold,
                                    color: _getConfidenceColor(confidence),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            ClipRRect(
                              borderRadius: BorderRadius.circular(4),
                              child: LinearProgressIndicator(
                                value: confidence,
                                backgroundColor: Colors.grey.shade200,
                                valueColor: AlwaysStoppedAnimation(
                                  _getConfidenceColor(confidence),
                                ),
                                minHeight: 8,
                              ),
                            ),
                            if (task.extractionDetails[field] != null) ...[
                              const SizedBox(height: 4),
                              Text(
                                task.extractionDetails[field].toString(),
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey.shade600,
                                  fontStyle: FontStyle.italic,
                                ),
                              ),
                            ],
                          ],
                        ),
                      );
                    }),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Color _getConfidenceColor(double confidence) {
    if (confidence >= 0.8) return Colors.green;
    if (confidence >= 0.6) return Colors.amber;
    return Colors.red;
  }

  void _showHelpDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('How to Use'),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              _buildHelpItem(
                '📅 Create Tasks',
                'Example: "I have a meeting at 3 PM on the way to the office"',
              ),
              _buildHelpItem(
                '🔔 Set Reminders',
                'Example: "Remind me to call the dentist when I get home"',
              ),
              _buildHelpItem(
                '🚗 Location-Based',
                'Example: "Buy groceries when leaving work"',
              ),
              _buildHelpItem(
                '💡 Ask Questions',
                'Example: "What\'s my schedule for today?"',
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Got it'),
          ),
        ],
      ),
    );
  }

  Widget _buildHelpItem(String title, String example) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          Text(
            example,
            style: TextStyle(
              fontSize: 13,
              color: Colors.grey.shade700,
              fontStyle: FontStyle.italic,
            ),
          ),
        ],
      ),
    );
  }
}
