// Widget tests for Intelligent Scheduler
//
// This test file validates the basic structure and navigation of the app.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:intelligent_scheduler/main.dart';

void main() {
  testWidgets('App loads and shows navigation', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(
      const ProviderScope(
        child: IntelligentSchedulerApp(),
      ),
    );

    // Wait for the app to load
    await tester.pumpAndSettle();

    // Verify that the app has navigation destinations
    expect(find.text('Home'), findsOneWidget);
    expect(find.text('Timeline'), findsOneWidget);
    expect(find.text('Chat'), findsOneWidget);
    
    // Verify that navigation icons are present
    expect(find.byIcon(Icons.home), findsOneWidget);
    expect(find.byIcon(Icons.schedule), findsOneWidget);
    expect(find.byIcon(Icons.chat_bubble), findsOneWidget);
  });

  testWidgets('Navigation works between screens', (WidgetTester tester) async {
    // Build our app
    await tester.pumpWidget(
      const ProviderScope(
        child: IntelligentSchedulerApp(),
      ),
    );

    await tester.pumpAndSettle();

    // Tap on Timeline tab
    await tester.tap(find.text('Timeline'));
    await tester.pumpAndSettle();
    
    // Verify Timeline screen is shown
    expect(find.text('Timeline'), findsAtLeastNWidgets(1));

    // Tap on Chat tab
    await tester.tap(find.text('Chat'));
    await tester.pumpAndSettle();
    
    // Verify Chat screen is shown
    expect(find.text('AI Assistant'), findsOneWidget);

    // Go back to Home
    await tester.tap(find.text('Home'));
    await tester.pumpAndSettle();
  });
}
