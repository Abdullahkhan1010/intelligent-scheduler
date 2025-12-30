import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../services/demo_service.dart';
import '../services/sensor_service.dart';

class DemoControlPanel extends ConsumerWidget {
  const DemoControlPanel({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final demoService = ref.watch(demoServiceProvider);

    if (!demoService.isDemoMode) {
      return const SizedBox.shrink();
    }

    final scenario = demoService.currentScenario;

    return Container(
      margin: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Colors.purple.shade700,
            Colors.deepPurple.shade900,
          ],
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.purple.withOpacity(0.3),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.1),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.play_circle_filled,
                        color: Colors.lightGreen.shade300,
                        size: 18,
                      ),
                      const SizedBox(width: 6),
                      const Text(
                        'DEMO MODE',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                          letterSpacing: 1.2,
                        ),
                      ),
                    ],
                  ),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.help_outline, color: Colors.white),
                  iconSize: 20,
                  onPressed: () => _showDemoInfo(context),
                ),
              ],
            ),
          ),

          // Scenario Info
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      scenario.name,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        '${demoService.currentScenarioIndex + 1}/${demoService.scenarios.length}',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  scenario.description,
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.8),
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 16),

                // Scenario Details Grid
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    _buildInfoChip(
                      icon: Icons.access_time,
                      label: DateFormat('EEE, h:mm a').format(scenario.time),
                      color: Colors.blue.shade300,
                    ),
                    _buildInfoChip(
                      icon: Icons.directions_walk,
                      label: scenario.activity,
                      color: Colors.green.shade300,
                    ),
                    _buildInfoChip(
                      icon: Icons.location_on,
                      label: scenario.location,
                      color: Colors.orange.shade300,
                    ),
                    if (scenario.speed > 0)
                      _buildInfoChip(
                        icon: Icons.speed,
                        label: '${scenario.speed.toInt()} km/h',
                        color: Colors.red.shade300,
                      ),
                    if (scenario.isCarConnected)
                      _buildInfoChip(
                        icon: Icons.bluetooth_connected,
                        label: 'Car BT',
                        color: Colors.cyan.shade300,
                      ),
                    if (scenario.wifiSsid != null)
                      _buildInfoChip(
                        icon: Icons.wifi,
                        label: scenario.wifiSsid!,
                        color: Colors.purple.shade300,
                      ),
                  ],
                ),
              ],
            ),
          ),

          // Navigation Controls
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.1),
              borderRadius: const BorderRadius.vertical(bottom: Radius.circular(16)),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _buildControlButton(
                  icon: Icons.skip_previous,
                  label: 'Previous',
                  onPressed: () {
                    ref.read(demoServiceProvider.notifier).previousScenario();
                    // Update sensor state immediately to match new scenario
                    ref.read(sensorServiceProvider.notifier).updateDemoSensorState();
                  },
                ),
                _buildControlButton(
                  icon: Icons.refresh,
                  label: 'Run Demo',
                  onPressed: () async {
                    final sensorService = ref.read(sensorServiceProvider.notifier);
                    try {
                      await sensorService.triggerInference();
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Row(
                              children: [
                                Icon(Icons.check_circle, color: Colors.white),
                                const SizedBox(width: 12),
                                Text('Demo scenario executed!'),
                              ],
                            ),
                            backgroundColor: Colors.green.shade700,
                            behavior: SnackBarBehavior.floating,
                            duration: const Duration(seconds: 2),
                          ),
                        );
                      }
                    } catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text('Demo failed: $e'),
                            backgroundColor: Colors.red.shade700,
                          ),
                        );
                      }
                    }
                  },
                  isPrimary: true,
                ),
                _buildControlButton(
                  icon: Icons.skip_next,
                  label: 'Next',
                  onPressed: () {
                    ref.read(demoServiceProvider.notifier).nextScenario();
                    // Update sensor state immediately to match new scenario
                    ref.read(sensorServiceProvider.notifier).updateDemoSensorState();
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoChip({
    required IconData icon,
    required String label,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 6),
          Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildControlButton({
    required IconData icon,
    required String label,
    required VoidCallback onPressed,
    bool isPrimary = false,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: isPrimary 
                ? Colors.white.withValues(alpha: 0.2)
                : Colors.transparent,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: Colors.white.withValues(alpha: isPrimary ? 0.5 : 0.3),
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                icon,
                color: Colors.white,
                size: isPrimary ? 24 : 20,
              ),
              const SizedBox(height: 4),
              Text(
                label,
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 11,
                  fontWeight: isPrimary ? FontWeight.bold : FontWeight.normal,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showDemoInfo(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            Icon(Icons.info_outline, color: Colors.purple.shade700),
            const SizedBox(width: 12),
            const Text('Demo Mode'),
          ],
        ),
        content: const SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Demo mode simulates different daily scenarios to showcase the AI\'s context-aware behavior.',
                style: TextStyle(fontSize: 15),
              ),
              SizedBox(height: 16),
              Text(
                '• Navigate scenarios with Previous/Next\n'
                '• Tap "Run Demo" to trigger inference\n'
                '• AI adapts suggestions based on context\n'
                '• No real-time waiting required\n'
                '• Safe to test without real sensor data',
                style: TextStyle(fontSize: 14, height: 1.6),
              ),
              SizedBox(height: 16),
              Text(
                '💡 Tip: Try giving feedback to train the AI across different scenarios!',
                style: TextStyle(
                  fontSize: 14,
                  fontStyle: FontStyle.italic,
                  color: Colors.grey,
                ),
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
}
