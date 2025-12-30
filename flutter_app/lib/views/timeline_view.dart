import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:timeline_tile/timeline_tile.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/models.dart';
import '../services/sensor_service.dart';
import '../services/feedback_tracker.dart';
import '../services/demo_service.dart';
import '../services/calendar_service.dart';
import '../widgets/demo_control_panel.dart';

class TimelineView extends ConsumerStatefulWidget {
  const TimelineView({super.key});

  @override
  ConsumerState<TimelineView> createState() => _TimelineViewState();
}

class _TimelineViewState extends ConsumerState<TimelineView> {
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    // Schedule refresh after first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _refreshSchedule();
    });
  }

  Future<void> _refreshSchedule() async {
    if (!mounted) return;
    setState(() => _isLoading = true);
    try {
      final sensorService = ref.read(sensorServiceProvider.notifier);
      final response = await sensorService.triggerInference();
      if (mounted) {
        ref.read(inferredTasksProvider.notifier).state = response.suggestedTasks;
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load schedule: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _handleFeedback(InferredTask task, bool isPositive) async {
    // Check if feedback already given
    if (task.feedbackGiven) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('You have already provided feedback for this task'),
            backgroundColor: Colors.orange,
          ),
        );
      }
      return;
    }

    // OPTIMISTIC UPDATE: Update UI immediately before backend call
    setState(() {
      task.feedbackGiven = true;
    });

    final feedbackTracker = FeedbackTracker();
    
    // Mark feedback locally (optimistic)
    await feedbackTracker.markFeedbackGiven(task);

    // Show immediate feedback to user
    if (mounted) {
      final message = isPositive 
          ? '✓ Feedback recorded! AI confidence will increase for similar contexts.'
          : '✓ Feedback recorded! AI will adjust timing for this task.';
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              Icon(
                isPositive ? Icons.thumb_up : Icons.thumb_down,
                color: Colors.white,
                size: 20,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(message),
              ),
            ],
          ),
          backgroundColor: isPositive ? const Color(0xFF10B981) : const Color(0xFFF59E0B),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          duration: const Duration(seconds: 2),
        ),
      );
    }

    // Send feedback to backend asynchronously (non-blocking)
    _sendFeedbackToBackend(task, isPositive, feedbackTracker);
  }

  void _sendFeedbackToBackend(
    InferredTask task, 
    bool isPositive, 
    FeedbackTracker feedbackTracker
  ) async {
    try {
      final apiService = ref.read(apiServiceProvider);
      final outcome = isPositive ? 'positive' : 'negative';
      
      // Send to backend
      await apiService.sendFeedback(
        ruleId: task.ruleId,
        outcome: outcome,
        contextSnapshot: task.matchedConditions,
      );

      // Refresh in background to get updated confidence levels
      await Future.delayed(const Duration(milliseconds: 500));
      if (mounted) {
        await _refreshSchedule();
      }
      
    } catch (e) {
      // GRACEFUL ERROR HANDLING: Rollback optimistic update on failure
      if (mounted) {
        setState(() {
          task.feedbackGiven = false;
        });
        
        // Remove local feedback mark
        final prefs = await SharedPreferences.getInstance();
        final key = feedbackTracker.generateKey(task);
        await prefs.remove(key);
        await prefs.remove('${key}_timestamp');
        
        // Show user-friendly error message
        if (!mounted) return;
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.error_outline, color: Colors.white, size: 20),
                const SizedBox(width: 12),
                Expanded(
                  child: Text('Failed to sync feedback: ${_getErrorMessage(e)}'),
                ),
                TextButton(
                  onPressed: () {
                    ScaffoldMessenger.of(context).hideCurrentSnackBar();
                    _handleFeedback(task, isPositive); // Retry
                  },
                  child: const Text(
                    'RETRY',
                    style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            backgroundColor: Colors.red.shade700,
            behavior: SnackBarBehavior.floating,
            duration: const Duration(seconds: 5),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        );
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
      return 'Please try again';
    }
  }

  @override
  Widget build(BuildContext context) {
    final tasks = ref.watch(inferredTasksProvider);
    final sensorData = ref.watch(sensorServiceProvider);
    final demoService = ref.watch(demoServiceProvider);
    final theme = Theme.of(context);

    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              demoService.isDemoMode 
                  ? Colors.purple.shade700
                  : theme.colorScheme.primary,
              demoService.isDemoMode
                  ? Colors.deepPurple.shade900
                  : theme.colorScheme.secondary,
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
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Timeline',
                          style: TextStyle(
                            fontSize: 28,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                        if (demoService.isDemoMode)
                          Container(
                            margin: const EdgeInsets.only(top: 4),
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(
                                  Icons.play_circle_filled,
                                  color: Colors.lightGreen.shade300,
                                  size: 14,
                                ),
                                const SizedBox(width: 4),
                                const Text(
                                  'DEMO MODE',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                    letterSpacing: 1,
                                  ),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
                    Row(
                      children: [
                        Container(
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: IconButton(
                            icon: Icon(
                              demoService.isDemoMode 
                                  ? Icons.videogame_asset 
                                  : Icons.videogame_asset_off,
                              color: Colors.white,
                            ),
                            tooltip: demoService.isDemoMode ? 'Exit Demo Mode' : 'Enter Demo Mode',
                            onPressed: () async {
                              ref.read(demoServiceProvider.notifier).toggleDemoMode();
                              final sensorService = ref.read(sensorServiceProvider.notifier);
                              
                              // If entering demo mode, update sensors to match demo scenario
                              if (demoService.isDemoMode) {
                                sensorService.updateDemoSensorState();
                              } else {
                                // If exiting demo mode, force sensor update to real data
                                sensorService.forceUpdateSensors();
                                
                                // Refresh tasks with real sensor data
                                await _refreshSchedule();
                              }
                              
                              if (mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    content: Text(
                                      demoService.isDemoMode 
                                          ? 'Demo mode enabled'
                                          : 'Demo mode disabled - reverted to real sensors',
                                    ),
                                    duration: const Duration(seconds: 2),
                                    behavior: SnackBarBehavior.floating,
                                  ),
                                );
                              }
                            },
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: IconButton(
                            icon: const Icon(Icons.refresh, color: Colors.white),
                            onPressed: _isLoading ? null : _refreshSchedule,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              
              // Main Content
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    color: theme.scaffoldBackgroundColor,
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(30),
                      topRight: Radius.circular(30),
                    ),
                  ),
                  child: _isLoading
                      ? Center(
                          child: CircularProgressIndicator(
                            color: theme.colorScheme.primary,
                          ),
                        )
                      : CustomScrollView(
                          slivers: [
                            SliverToBoxAdapter(
                              child: Column(
                                children: [
                                  const SizedBox(height: 20),
                                  
                                  // Demo Control Panel (when in demo mode)
                                  if (demoService.isDemoMode)
                                    const DemoControlPanel(),
                                  
                                  // Context Summary Card
                                  _buildContextCard(sensorData),
                                  
                                  const SizedBox(height: 8),
                                ],
                              ),
                            ),
                            
                            // Timeline
                            tasks.isEmpty
                                ? SliverFillRemaining(
                                    child: _buildEmptyState(),
                                  )
                                : SliverList(
                                    delegate: SliverChildBuilderDelegate(
                                      (context, index) {
                                        return Padding(
                                          padding: const EdgeInsets.symmetric(horizontal: 16),
                                          child: _buildTimelineTask(
                                            tasks[index],
                                            isFirst: index == 0,
                                            isLast: index == tasks.length - 1,
                                          ),
                                        );
                                      },
                                      childCount: tasks.length,
                                    ),
                                  ),
                            
                            // Bottom padding
                            const SliverToBoxAdapter(
                              child: SizedBox(height: 16),
                            ),
                          ],
                        ),
                ),
              ),
            ],
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _syncCalendar,
        icon: const Icon(Icons.calendar_today),
        label: const Text('Sync Calendar'),
        backgroundColor: Colors.deepPurple,
      ),
    );
  }

  Widget _buildUrgentNotifications(List<InferredTask> tasks) {
    // Filter tasks that have scheduled_time in matched_conditions
    final urgentTasks = tasks.where((t) => 
      t.matchedConditions.containsKey('scheduled_time')
    ).toList();

    if (urgentTasks.isEmpty) return const SizedBox.shrink();

    return Container(
      margin: const EdgeInsets.fromLTRB(20, 0, 20, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            children: [
              Icon(Icons.notifications_active, color: Colors.orange.shade600, size: 20),
              const SizedBox(width: 8),
              const Text(
                'Happening Now',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF1F2937),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Urgent task cards
          ...urgentTasks.map((task) => Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  Colors.orange.shade400,
                  Colors.deepOrange.shade500,
                ],
              ),
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: Colors.orange.shade300.withValues(alpha: 0.5),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Row(
              children: [
                // Icon
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.alarm,
                    color: Colors.white,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 16),
                // Content
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        task.taskName,
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Scheduled: ${task.matchedConditions['scheduled_time']}',
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.white.withValues(alpha: 0.9),
                        ),
                      ),
                    ],
                  ),
                ),
                // Confidence badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '${(task.confidence * 100).toInt()}%',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: Colors.orange.shade700,
                    ),
                  ),
                ),
              ],
            ),
          )),
        ],
      ),
    );
  }

  Widget _buildContextCard(SensorData sensorData) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 20,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFF6366F1).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.sensors,
                  color: Color(0xFF6366F1),
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                'Current Context',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _buildContextRow(
            Icons.directions_walk,
            'Activity',
            _humanizeActivity(sensorData.activity),
          ),
          _buildContextRow(
            Icons.speed,
            'Speed',
            '${sensorData.speed.toStringAsFixed(1)} km/h',
          ),
          _buildContextRow(
            Icons.location_on,
            'Location',
            sensorData.locationVector ?? 'Unknown',
          ),
          _buildContextRow(
            Icons.bluetooth,
            'Car Audio',
            sensorData.carBluetoothConnected ? 'Connected' : 'Disconnected',
          ),
          const SizedBox(height: 12),
          Divider(color: Colors.grey.shade200),
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(Icons.access_time, size: 14, color: Colors.grey.shade600),
              const SizedBox(width: 6),
              Text(
                'Last updated: ${DateFormat('HH:mm:ss').format(sensorData.lastUpdate)}',
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildContextRow(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 18, color: const Color(0xFF8B5CF6)),
          const SizedBox(width: 12),
          Text(
            '$label: ',
            style: const TextStyle(
              fontWeight: FontWeight.w600,
              fontSize: 14,
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey.shade700,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTimelineTask(InferredTask task, {required bool isFirst, required bool isLast}) {
    return TimelineTile(
      isFirst: isFirst,
      isLast: isLast,
      beforeLineStyle: LineStyle(
        color: _getConfidenceColor(task.confidence).withValues(alpha: 0.3),
        thickness: 3,
      ),
      indicatorStyle: IndicatorStyle(
        width: 50,
        height: 50,
        indicator: Container(
          decoration: BoxDecoration(
            color: _getConfidenceColor(task.confidence),
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: _getConfidenceColor(task.confidence).withValues(alpha: 0.4),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  '${(task.confidence * 100).toInt()}%',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Container(
                  margin: const EdgeInsets.only(top: 2),
                  width: 24,
                  height: 3,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.5),
                    borderRadius: BorderRadius.circular(2),
                  ),
                  child: FractionallySizedBox(
                    alignment: Alignment.centerLeft,
                    widthFactor: task.confidence,
                    child: Container(
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
      endChild: GestureDetector(
        onTap: () => _showTaskExplanation(task),
        child: Container(
        margin: const EdgeInsets.only(left: 16, bottom: 24),
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: _getConfidenceColor(task.confidence).withValues(alpha: 0.15),
              blurRadius: 15,
              offset: const Offset(0, 5),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Task Name with Confidence Bar
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        task.taskName,
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      // Visual Confidence Bar
                      Row(
                        children: [
                          Expanded(
                            child: Container(
                              height: 8,
                              decoration: BoxDecoration(
                                color: Colors.grey.shade200,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: FractionallySizedBox(
                                alignment: Alignment.centerLeft,
                                widthFactor: task.confidence,
                                child: Container(
                                  decoration: BoxDecoration(
                                    gradient: LinearGradient(
                                      colors: [
                                        _getConfidenceColor(task.confidence),
                                        _getConfidenceColor(task.confidence).withValues(alpha: 0.7),
                                      ],
                                    ),
                                    borderRadius: BorderRadius.circular(4),
                                    boxShadow: [
                                      BoxShadow(
                                        color: _getConfidenceColor(task.confidence).withValues(alpha: 0.3),
                                        blurRadius: 4,
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          _buildConfidenceBadge(task.confidence),
                        ],
                      ),
                    ],
                  ),
                ),
                // Tap to explain indicator
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF6366F1).withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    Icons.info_outline,
                    size: 20,
                    color: const Color(0xFF6366F1),
                  ),
                ),
              ],
            ),
            
            if (task.taskDescription != null) ...[
              const SizedBox(height: 12),
              Text(
                task.taskDescription!,
                style: TextStyle(
                  color: Colors.grey.shade600,
                  fontSize: 14,
                ),
              ),
            ],
            
            const SizedBox(height: 12),
            
            // Quick reasoning preview (shortened)
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.grey.shade50,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.grey.shade200),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.lightbulb_outline,
                    size: 18,
                    color: Colors.grey.shade600,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      task.reasoning.length > 60
                          ? '${task.reasoning.substring(0, 60)}...'
                          : task.reasoning,
                      style: TextStyle(
                        color: Colors.grey.shade700,
                        fontSize: 12,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Icon(
                    Icons.arrow_forward_ios,
                    size: 12,
                    color: Colors.grey.shade400,
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 16),
            
            // Feedback Buttons or Status
            task.feedbackGiven
                ? Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.grey.shade100,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.grey.shade300),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.check_circle, color: Colors.grey.shade600, size: 20),
                        const SizedBox(width: 8),
                        Text(
                          'Feedback already provided',
                          style: TextStyle(
                            color: Colors.grey.shade700,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  )
                : Row(
                    children: [
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () => _handleFeedback(task, true),
                          icon: const Icon(Icons.check, size: 18),
                          label: const Text('Accept'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.green,
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => _handleFeedback(task, false),
                          icon: const Icon(Icons.close, size: 18),
                          label: const Text('Reject'),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: Colors.red,
                            side: const BorderSide(color: Colors.red),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
          ],
        ),
      ),
      ), // Close GestureDetector
    ); // Close TimelineTile
  }

  Widget _buildConfidenceBadge(double confidence) {
    final confidenceLevel = _getConfidenceLevel(confidence);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            _getConfidenceColor(confidence),
            _getConfidenceColor(confidence).withValues(alpha: 0.8),
          ],
        ),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: _getConfidenceColor(confidence).withValues(alpha: 0.3),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            confidenceLevel['icon'] as IconData,
            size: 14,
            color: Colors.white,
          ),
          const SizedBox(width: 4),
          Text(
            '${(confidence * 100).toInt()}%',
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.bold,
              color: Colors.white,
            ),
          ),
        ],
      ),
    );
  }

  Color _getConfidenceColor(double confidence) {
    if (confidence >= 0.75) return const Color(0xFF10B981); // Green - High confidence
    if (confidence >= 0.5) return const Color(0xFFF59E0B);  // Amber - Medium confidence
    return const Color(0xFFEF4444); // Red - Low confidence
  }

  Map<String, dynamic> _getConfidenceLevel(double confidence) {
    if (confidence >= 0.75) {
      return {
        'level': 'High',
        'icon': Icons.check_circle,
        'description': 'Strong evidence supporting this recommendation',
      };
    } else if (confidence >= 0.5) {
      return {
        'level': 'Medium',
        'icon': Icons.info,
        'description': 'Moderate evidence, system is still learning your patterns',
      };
    } else {
      return {
        'level': 'Low',
        'icon': Icons.warning_amber_rounded,
        'description': 'Limited data, this is an exploratory suggestion',
      };
    }
  }

  void _showTaskExplanation(InferredTask task) {
    final confidenceLevel = _getConfidenceLevel(task.confidence);
    
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => Container(
        margin: const EdgeInsets.only(top: 80),
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(25)),
        ),
        child: DraggableScrollableSheet(
          initialChildSize: 1.0,
          minChildSize: 0.5,
          maxChildSize: 1.0,
          builder: (context, scrollController) => ListView(
            controller: scrollController,
            padding: const EdgeInsets.all(24),
            children: [
              // Drag handle
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: 20),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade300,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              
              // Header
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [
                          _getConfidenceColor(task.confidence),
                          _getConfidenceColor(task.confidence).withValues(alpha: 0.7),
                        ],
                      ),
                      borderRadius: BorderRadius.circular(12),
                      boxShadow: [
                        BoxShadow(
                          color: _getConfidenceColor(task.confidence).withValues(alpha: 0.3),
                          blurRadius: 8,
                          offset: const Offset(0, 4),
                        ),
                      ],
                    ),
                    child: Icon(
                      confidenceLevel['icon'] as IconData,
                      color: Colors.white,
                      size: 28,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          task.taskName,
                          style: const TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'AI Confidence Breakdown',
                          style: TextStyle(
                            fontSize: 14,
                            color: Colors.grey.shade600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              
              const SizedBox(height: 24),
              
              // Confidence Section
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      _getConfidenceColor(task.confidence).withValues(alpha: 0.1),
                      _getConfidenceColor(task.confidence).withValues(alpha: 0.05),
                    ],
                  ),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: _getConfidenceColor(task.confidence).withValues(alpha: 0.3),
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Confidence Level',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: Colors.grey.shade700,
                          ),
                        ),
                        _buildConfidenceBadge(task.confidence),
                      ],
                    ),
                    const SizedBox(height: 12),
                    
                    // Visual bar
                    Container(
                      height: 12,
                      decoration: BoxDecoration(
                        color: Colors.grey.shade200,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: FractionallySizedBox(
                        alignment: Alignment.centerLeft,
                        widthFactor: task.confidence,
                        child: Container(
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              colors: [
                                _getConfidenceColor(task.confidence),
                                _getConfidenceColor(task.confidence).withValues(alpha: 0.7),
                              ],
                            ),
                            borderRadius: BorderRadius.circular(6),
                            boxShadow: [
                              BoxShadow(
                                color: _getConfidenceColor(task.confidence).withValues(alpha: 0.4),
                                blurRadius: 8,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                    
                    const SizedBox(height: 12),
                    Text(
                      confidenceLevel['description'] as String,
                      style: TextStyle(
                        fontSize: 13,
                        color: Colors.grey.shade600,
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
              
              const SizedBox(height: 24),
              
              // Why Section
              _buildExplanationSection(
                'Why This Reminder?',
                Icons.psychology,
                task.reasoning,
                Colors.purple,
              ),
              
              const SizedBox(height: 16),
              
              // Matched Conditions
              _buildExplanationSection(
                'Matched Patterns',
                Icons.pattern,
                task.matchedConditions.entries
                    .map((e) => '${e.key}: ${e.value}')
                    .join('\n'),
                Colors.blue,
              ),
              
              const SizedBox(height: 24),
              
              // Feedback section
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.grey.shade50,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.grey.shade200),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.feedback_outlined, size: 20, color: Colors.grey.shade700),
                        const SizedBox(width: 8),
                        Text(
                          'Help AI Learn',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                            color: Colors.grey.shade800,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Your feedback helps improve future recommendations and adjust confidence levels.',
                      style: TextStyle(
                        fontSize: 13,
                        color: Colors.grey.shade600,
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
              
              const SizedBox(height: 16),
              
              // Close button
              ElevatedButton(
                onPressed: () => Navigator.pop(context),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF6366F1),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  'Got It',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildExplanationSection(
    String title,
    IconData icon,
    String content,
    Color color,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, size: 18, color: color),
              ),
              const SizedBox(width: 12),
              Text(
                title,
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 15,
                  color: Colors.grey.shade800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            content,
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey.shade700,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: SingleChildScrollView(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.event_available, size: 64, color: Colors.grey.shade300),
            const SizedBox(height: 16),
            Text(
              'No tasks suggested',
              style: TextStyle(fontSize: 18, color: Colors.grey.shade600),
            ),
            const SizedBox(height: 8),
            Text(
              'Pull to refresh or wait for context changes',
              style: TextStyle(fontSize: 14, color: Colors.grey.shade500),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _syncCalendar() async {
    final calendarService = CalendarService();
    
    try {
      // Check if already signed in
      if (!calendarService.isSignedIn) {
        // Show sign-in dialog
        final shouldSignIn = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Google Calendar'),
            content: const Text(
              'Connect your Google Calendar to receive intelligent reminders for your events.\n\n'
              'The app will:\n'
              '• Parse event priority and timing\n'
              '• Calculate optimal reminder times\n'
              '• Suggest preparation for meetings\n'
              '• Include birthdays and all-day events\n'
              '• Adapt to your schedule'
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Cancel'),
              ),
              ElevatedButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Connect'),
              ),
            ],
          ),
        );
        
        if (shouldSignIn != true) return;
        
        // Sign in
        final success = await calendarService.signIn();
        if (!success) {
          if (!mounted) return;
          
          // Show detailed error dialog
          showDialog(
            context: context,
            builder: (context) => AlertDialog(
              title: const Row(
                children: [
                  Icon(Icons.error_outline, color: Colors.red),
                  SizedBox(width: 8),
                  Text('Google Sign-In Failed'),
                ],
              ),
              content: const SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Google Calendar integration requires OAuth 2.0 configuration.',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    SizedBox(height: 16),
                    Text('Required Setup:'),
                    SizedBox(height: 8),
                    Text('1. Create project in Google Cloud Console'),
                    Text('2. Enable Google Calendar API'),
                    Text('3. Configure OAuth 2.0 credentials'),
                    Text('4. Add SHA-1 certificate fingerprint'),
                    Text('5. Download google-services.json'),
                    SizedBox(height: 16),
                    Text(
                      'For testing: Calendar sync is currently disabled. '
                      'The app works with manual task rules.',
                      style: TextStyle(fontSize: 13, color: Colors.grey),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('OK'),
                ),
              ],
            ),
          );
          return;
        }
      } else {
        // Already signed in, just sync
        print('🔄 Manually syncing calendar events (including all-day events)...');
        await calendarService.syncCalendarEvents();
      }
      
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Row(
            children: [
              Icon(Icons.check_circle, color: Colors.white),
              SizedBox(width: 12),
              Text('Calendar synced! Birthdays & events added.'),
            ],
          ),
          backgroundColor: Colors.green,
        ),
      );
      
      // Refresh schedule to show calendar tasks
      await _refreshSchedule();
      
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Calendar sync failed: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  String _humanizeActivity(String activity) {
    const activityMap = {
      'STILL': 'Stationary',
      'WALKING': 'Walking',
      'RUNNING': 'Running',
      'IN_VEHICLE': 'Driving',
      'ON_BICYCLE': 'Cycling',
      'ON_FOOT': 'On Foot',
    };
    return activityMap[activity] ?? activity;
  }
}
