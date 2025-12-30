import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'views/home_view.dart';
import 'views/timeline_view.dart';
import 'views/chat_view.dart';
import 'services/notification_service.dart';
import 'services/feedback_tracker.dart';
import 'services/sensor_service.dart';
import 'services/background_service.dart';
import 'package:flutter/services.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Set system UI overlay style
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
    ),
  );
  
  // Initialize notification service
  await NotificationService().initialize();
  
  // TODO: Background service - requires additional Android configuration
  // Temporarily disabled to allow app to run
  // await BackgroundService.initialize();
  // await BackgroundService.startBackgroundInference();
  // print('✅ Background service started - app will run continuously');
  
  // Clean old feedback and notification records
  await FeedbackTracker().cleanOldRecords();
  await NotificationService().cleanOldNotificationRecords();
  
  runApp(
    const ProviderScope(
      child: IntelligentSchedulerApp(),
    ),
  );
}

class IntelligentSchedulerApp extends StatelessWidget {
  const IntelligentSchedulerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Intelligent Scheduler',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF6366F1), // Indigo
          primary: const Color(0xFF6366F1),
          secondary: const Color(0xFF8B5CF6), // Purple
          tertiary: const Color(0xFF06B6D4), // Cyan
          brightness: Brightness.light,
        ),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF8FAFC),
        appBarTheme: const AppBarTheme(
          centerTitle: true,
          elevation: 0,
          backgroundColor: Colors.transparent,
          foregroundColor: Colors.white,
          systemOverlayStyle: SystemUiOverlayStyle.light,
        ),
        cardTheme: CardThemeData(
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            elevation: 2,
            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
            ),
          ),
        ),
        floatingActionButtonTheme: FloatingActionButtonThemeData(
          elevation: 4,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(16),
            borderSide: BorderSide.none,
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(16),
            borderSide: BorderSide.none,
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(16),
            borderSide: const BorderSide(color: Color(0xFF6366F1), width: 2),
          ),
          contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        ),
        textTheme: const TextTheme(
          displayLarge: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, letterSpacing: -0.5),
          displayMedium: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, letterSpacing: -0.5),
          displaySmall: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, letterSpacing: -0.5),
          headlineMedium: TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
          bodyLarge: TextStyle(fontSize: 16, fontWeight: FontWeight.normal, height: 1.5),
          bodyMedium: TextStyle(fontSize: 14, fontWeight: FontWeight.normal, height: 1.5),
        ),
      ),
      home: const MainNavigation(),
    );
  }
}

class MainNavigation extends ConsumerStatefulWidget {
  const MainNavigation({super.key});

  @override
  ConsumerState<MainNavigation> createState() => _MainNavigationState();
}

class _MainNavigationState extends ConsumerState<MainNavigation> {
  int _currentIndex = 0;

  final List<Widget> _screens = [
    const HomeView(),
    const TimelineView(),
    const ChatView(),
  ];

  @override
  void initState() {
    super.initState();
    // Setup notification callback after first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _setupNotificationCallback();
    });
  }

  void _setupNotificationCallback() {
    // Setup callback for when feedback is given via notification actions
    NotificationService().initialize(
      onFeedbackGiven: () async {
        debugPrint('🔔 Notification feedback received, refreshing tasks...');
        // Trigger inference refresh
        final sensorService = ref.read(sensorServiceProvider.notifier);
        try {
          final response = await sensorService.triggerInference();
          ref.read(inferredTasksProvider.notifier).state = response.suggestedTasks;
          debugPrint('✅ Tasks refreshed with updated confidences');
        } catch (e) {
          debugPrint('❌ Failed to refresh tasks: $e');
        }
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.1),
              blurRadius: 20,
              offset: const Offset(0, -5),
            ),
          ],
        ),
        child: NavigationBar(
          selectedIndex: _currentIndex,
          onDestinationSelected: (int index) {
            setState(() {
              _currentIndex = index;
            });
          },
          elevation: 0,
          backgroundColor: Colors.white,
          indicatorColor: const Color(0xFF6366F1).withValues(alpha: 0.1),
          height: 70,
          labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.home_outlined),
              selectedIcon: Icon(Icons.home, color: Color(0xFF6366F1)),
              label: 'Home',
            ),
            NavigationDestination(
              icon: Icon(Icons.schedule_outlined),
              selectedIcon: Icon(Icons.schedule, color: Color(0xFF6366F1)),
              label: 'Timeline',
            ),
            NavigationDestination(
              icon: Icon(Icons.chat_bubble_outline),
              selectedIcon: Icon(Icons.chat_bubble, color: Color(0xFF6366F1)),
              label: 'Chat',
            ),
          ],
        ),
      ),
    );
  }
}
