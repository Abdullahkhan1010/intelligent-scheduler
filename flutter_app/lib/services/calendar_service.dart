import 'package:googleapis/calendar/v3.dart' as calendar;
import 'package:google_sign_in/google_sign_in.dart';
import 'package:http/http.dart' as http;
import 'api_service.dart';

/// Google Calendar integration service
class CalendarService {
  static final CalendarService _instance = CalendarService._internal();
  factory CalendarService() => _instance;
  CalendarService._internal();

  final GoogleSignIn _googleSignIn = GoogleSignIn(
    scopes: [calendar.CalendarApi.calendarReadonlyScope],
    serverClientId: '486547516612-qg53m5kjem14c0j3pc1l5r97k9ar67f2.apps.googleusercontent.com',
  );

  GoogleSignInAccount? _currentUser;
  calendar.CalendarApi? _calendarApi;

  /// Sign in to Google and initialize Calendar API
  Future<bool> signIn() async {
    try {
      print('🔐 Starting Google Sign-In...');
      _currentUser = await _googleSignIn.signIn();
      
      if (_currentUser == null) {
        print('❌ User cancelled sign-in');
        return false;
      }

      print('✅ User signed in: ${_currentUser!.email}');
      print('📡 Getting auth headers...');
      
      final authHeaders = await _currentUser!.authHeaders;
      final authenticateClient = GoogleAuthClient(authHeaders);
      _calendarApi = calendar.CalendarApi(authenticateClient);
      
      print('✅ Calendar API initialized');
      
      // Sync events after successful sign-in
      await syncCalendarEvents();
      
      return true;
    } catch (e) {
      print('❌ Google Sign-In error: $e');
      print('Error type: ${e.runtimeType}');
      if (e.toString().contains('DEVELOPER_ERROR')) {
        print('⚠️  Google Sign-In not configured properly');
        print('   This requires OAuth credentials from Google Cloud Console');
      }
      return false;
    }
  }

  /// Sign out from Google
  Future<void> signOut() async {
    await _googleSignIn.signOut();
    _currentUser = null;
    _calendarApi = null;
  }

  /// Check if user is signed in
  bool get isSignedIn => _currentUser != null && _calendarApi != null;

  /// Sync calendar events to backend for intelligent reminders
  Future<bool> syncCalendarEvents({int hoursAhead = 72}) async {
    if (!isSignedIn) {
      print('Not signed in to Google Calendar');
      return false;
    }

    try {
      final events = await getUpcomingEvents(hoursAhead: hoursAhead);
      
      if (events.isEmpty) {
        print('No upcoming events to sync');
        return true;
      }

      // Convert to backend format
      final eventsList = events.map((event) => {
        'event_id': event.id,
        'summary': event.summary,
        'description': event.description,
        'start_time': event.startTime.toIso8601String(),
        'end_time': event.endTime.toIso8601String(),
        'location': event.location,
        'is_all_day': event.summary.toLowerCase().contains('birthday') || 
                       event.summary.toLowerCase().contains('holiday'),
        'recurrence': null,
        'recurring_event_id': null,
        'attendees': null,
      }).toList();

      // Send to backend
      final apiService = ApiService();
      final response = await apiService.syncCalendarEvents(eventsList);
      
      print('✅ Synced ${events.length} calendar events to backend');
      print('   Created: ${response['events_created']}, Updated: ${response['events_updated']}');
      print('   Tasks generated: ${response['tasks_generated']}');
      
      return true;
    } catch (e) {
      print('❌ Error syncing calendar events: $e');
      return false;
    }
  }

  /// Get upcoming events for the next N hours
  Future<List<CalendarEvent>> getUpcomingEvents({int hoursAhead = 24}) async {
    if (!isSignedIn) {
      throw Exception('Not signed in to Google Calendar');
    }

    final now = DateTime.now();
    final timeMin = now.toUtc();
    final timeMax = now.add(Duration(hours: hoursAhead)).toUtc();

    try {
      final events = await _calendarApi!.events.list(
        'primary',
        timeMin: timeMin,
        timeMax: timeMax,
        singleEvents: true,
        orderBy: 'startTime',
      );

      if (events.items == null || events.items!.isEmpty) {
        return [];
      }

      return events.items!
          .where((event) => event.start?.dateTime != null || event.start?.date != null)
          .map((event) {
            // Handle all-day events (birthdays, holidays)
            DateTime startTime;
            DateTime endTime;
            if (event.start?.dateTime != null) {
              startTime = event.start!.dateTime!;
              endTime = event.end?.dateTime ?? startTime.add(const Duration(hours: 1));
            } else {
              // All-day event - date is a DateTime object
              final date = event.start!.date!;
              startTime = DateTime(date.year, date.month, date.day, 9, 0);
              endTime = startTime.add(const Duration(hours: 1));
            }
            
            return CalendarEvent(
              id: event.id ?? '',
              summary: event.summary ?? 'Untitled Event',
              description: event.description,
              startTime: startTime,
              endTime: endTime,
              location: event.location,
            );
          })
          .toList();
    } catch (e) {
      print('Error fetching calendar events: $e');
      return [];
    }
  }

  /// Check if there's a meeting in the next N minutes
  Future<bool> hasUpcomingMeeting({int minutesAhead = 30}) async {
    if (!isSignedIn) return false;

    final events = await getUpcomingEvents(hoursAhead: 1);
    final now = DateTime.now();
    final threshold = now.add(Duration(minutes: minutesAhead));

    return events.any((event) => 
      event.startTime.isAfter(now) && 
      event.startTime.isBefore(threshold)
    );
  }

  /// Get current ongoing meeting (if any)
  Future<CalendarEvent?> getCurrentMeeting() async {
    if (!isSignedIn) return null;

    final events = await getUpcomingEvents(hoursAhead: 1);
    final now = DateTime.now();

    for (final event in events) {
      if (event.startTime.isBefore(now) && event.endTime.isAfter(now)) {
        return event;
      }
    }

    return null;
  }
}

/// Calendar event model
class CalendarEvent {
  final String id;
  final String summary;
  final String? description;
  final DateTime startTime;
  final DateTime endTime;
  final String? location;

  CalendarEvent({
    required this.id,
    required this.summary,
    this.description,
    required this.startTime,
    required this.endTime,
    this.location,
  });

  /// Convert to JSON for backend context
  Map<String, dynamic> toJson() => {
    'id': id,
    'summary': summary,
    'description': description,
    'start_time': startTime.toIso8601String(),
    'end_time': endTime.toIso8601String(),
    'location': location,
  };
}

/// HTTP client with authentication headers
class GoogleAuthClient extends http.BaseClient {
  final Map<String, String> _headers;
  final http.Client _client = http.Client();

  GoogleAuthClient(this._headers);

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) {
    return _client.send(request..headers.addAll(_headers));
  }
}
