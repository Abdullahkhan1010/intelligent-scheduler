import 'package:shared_preferences/shared_preferences.dart';
import '../models/models.dart';

/// Tracks feedback state to ensure users can only give feedback once per recommendation
class FeedbackTracker {
  static final FeedbackTracker _instance = FeedbackTracker._internal();
  factory FeedbackTracker() => _instance;
  FeedbackTracker._internal();

  static const String _feedbackPrefix = 'feedback_';
  
  /// Generate unique key for a task suggestion
  /// Format: feedback_<taskName>_<date>_<hour>
  String generateKey(InferredTask task) {
    final date = task.suggestedAt;
    final dateStr = '${date.year}${date.month.toString().padLeft(2, '0')}${date.day.toString().padLeft(2, '0')}';
    final hourStr = date.hour.toString().padLeft(2, '0');
    return '$_feedbackPrefix${task.taskName}_${dateStr}_$hourStr';
  }

  /// Check if feedback has already been given for this task
  Future<bool> hasFeedback(InferredTask task) async {
    final prefs = await SharedPreferences.getInstance();
    final key = generateKey(task);
    return prefs.getBool(key) ?? false;
  }

  /// Mark feedback as given for this task
  Future<void> markFeedbackGiven(InferredTask task) async {
    final prefs = await SharedPreferences.getInstance();
    final key = generateKey(task);
    await prefs.setBool(key, true);
    
    // Also store timestamp for analytics
    final timestampKey = '${key}_timestamp';
    await prefs.setInt(timestampKey, DateTime.now().millisecondsSinceEpoch);
  }

  /// Check and update feedback status for multiple tasks
  Future<List<InferredTask>> updateFeedbackStatus(List<InferredTask> tasks) async {
    final updatedTasks = <InferredTask>[];
    
    for (final task in tasks) {
      final hasFeedback = await this.hasFeedback(task);
      task.feedbackGiven = hasFeedback;
      updatedTasks.add(task);
    }
    
    return updatedTasks;
  }

  /// Clear old feedback records (older than 7 days)
  Future<void> cleanOldRecords() async {
    final prefs = await SharedPreferences.getInstance();
    final keys = prefs.getKeys().where((key) => key.startsWith(_feedbackPrefix));
    final now = DateTime.now().millisecondsSinceEpoch;
    final sevenDaysAgo = now - (7 * 24 * 60 * 60 * 1000);
    
    for (final key in keys) {
      final timestampKey = '${key}_timestamp';
      final timestamp = prefs.getInt(timestampKey);
      
      if (timestamp != null && timestamp < sevenDaysAgo) {
        await prefs.remove(key);
        await prefs.remove(timestampKey);
      }
    }
  }

  /// Get feedback statistics
  Future<Map<String, int>> getFeedbackStats() async {
    final prefs = await SharedPreferences.getInstance();
    final keys = prefs.getKeys().where((key) => 
      key.startsWith(_feedbackPrefix) && !key.endsWith('_timestamp')
    );
    
    return {
      'total_feedback_given': keys.length,
    };
  }
}
