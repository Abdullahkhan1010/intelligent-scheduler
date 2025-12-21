"""
Deterministic Testing Framework for Bayesian Learning System
Tests feedback learning without real-time delays
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from models import UserContextSchema, get_db
from learning_service import LearningService
from inference import BayesianTimingOptimizer
import random


class SimulatedClock:
    """
    Mock clock for deterministic time-based testing.
    Allows fast-forwarding time without actual delays.
    """
    
    def __init__(self, start_time: datetime):
        self.current_time = start_time
        self.time_log = []
    
    def now(self) -> datetime:
        """Get current simulated time"""
        return self.current_time
    
    def advance(self, minutes: int = 0, hours: int = 0, days: int = 0):
        """Fast-forward simulated time"""
        delta = timedelta(minutes=minutes, hours=hours, days=days)
        self.current_time += delta
        self.time_log.append({
            'action': 'advance',
            'delta': delta,
            'new_time': self.current_time
        })
    
    def set_time(self, new_time: datetime):
        """Jump to specific time"""
        self.current_time = new_time
        self.time_log.append({
            'action': 'set',
            'new_time': new_time
        })
    
    def reset(self, start_time: datetime):
        """Reset clock to starting time"""
        self.current_time = start_time
        self.time_log = []


class ContextSimulator:
    """
    Generates realistic simulated user contexts for testing.
    Produces deterministic, varied contexts.
    """
    
    def __init__(self, seed: int = 42):
        """Initialize with seed for deterministic randomness"""
        random.seed(seed)
        self.seed = seed
    
    def generate_morning_home_context(self, timestamp: datetime) -> UserContextSchema:
        """Morning routine context: stationary at home"""
        return UserContextSchema(
            timestamp=timestamp,
            activity_type='STILL',
            speed=0.0,
            is_connected_to_car_bluetooth=False,
            wifi_ssid='HomeNetwork',
            location_vector='home',
            additional_data={'simulated': True}
        )
    
    def generate_commute_context(self, timestamp: datetime) -> UserContextSchema:
        """Commuting context: in vehicle"""
        return UserContextSchema(
            timestamp=timestamp,
            activity_type='IN_VEHICLE',
            speed=random.uniform(30, 60),
            is_connected_to_car_bluetooth=True,
            wifi_ssid=None,
            location_vector='traveling',
            additional_data={'simulated': True}
        )
    
    def generate_work_context(self, timestamp: datetime) -> UserContextSchema:
        """At work context"""
        return UserContextSchema(
            timestamp=timestamp,
            activity_type='STILL',
            speed=0.0,
            is_connected_to_car_bluetooth=False,
            wifi_ssid='OfficeWiFi',
            location_vector='work',
            additional_data={'simulated': True}
        )
    
    def generate_evening_home_context(self, timestamp: datetime) -> UserContextSchema:
        """Evening context: relaxing at home"""
        return UserContextSchema(
            timestamp=timestamp,
            activity_type='STILL',
            speed=0.0,
            is_connected_to_car_bluetooth=False,
            wifi_ssid='HomeNetwork',
            location_vector='home',
            additional_data={'simulated': True}
        )
    
    def generate_gym_context(self, timestamp: datetime) -> UserContextSchema:
        """Gym workout context"""
        return UserContextSchema(
            timestamp=timestamp,
            activity_type='WALKING',
            speed=random.uniform(3, 8),
            is_connected_to_car_bluetooth=False,
            wifi_ssid='GymWiFi',
            location_vector='gym',
            additional_data={'simulated': True}
        )
    
    def generate_context_by_time(self, timestamp: datetime) -> UserContextSchema:
        """Generate context based on time of day (realistic patterns)"""
        hour = timestamp.hour
        
        if 6 <= hour < 9:
            # Morning: either home or commuting
            return self.generate_morning_home_context(timestamp) if random.random() > 0.3 else self.generate_commute_context(timestamp)
        elif 9 <= hour < 17:
            # Work hours
            return self.generate_work_context(timestamp)
        elif 17 <= hour < 19:
            # Evening commute
            return self.generate_commute_context(timestamp)
        elif 19 <= hour < 22:
            # Evening at home or gym
            return self.generate_evening_home_context(timestamp) if random.random() > 0.2 else self.generate_gym_context(timestamp)
        else:
            # Night: home
            return self.generate_evening_home_context(timestamp)


class FeedbackSimulator:
    """
    Simulates user feedback patterns for testing.
    Can model user preferences and behavioral patterns.
    """
    
    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.feedback_log = []
    
    def simulate_preference(
        self,
        task_type: str,
        context: UserContextSchema,
        timing_window: int,
        user_profile: Dict[str, Any]
    ) -> str:
        """
        Simulate user feedback based on preferences.
        
        Args:
            task_type: Type of task
            context: User context
            timing_window: Proposed timing window
            user_profile: User preferences (e.g., preferred times, activities)
        
        Returns:
            'accept' or 'reject'
        """
        # Extract context features
        hour = context.timestamp.hour
        activity = context.activity_type
        location = context.location_vector
        
        # Base acceptance rate
        acceptance_rate = 0.5
        
        # Adjust based on user profile preferences
        preferred_windows = user_profile.get('preferred_windows', [30])
        if timing_window in preferred_windows:
            acceptance_rate += 0.3
        
        preferred_activities = user_profile.get('preferred_activities', [])
        if activity in preferred_activities:
            acceptance_rate += 0.2
        
        preferred_locations = user_profile.get('preferred_locations', [])
        if location in preferred_locations:
            acceptance_rate += 0.2
        
        # Time-based preferences
        preferred_hours = user_profile.get('preferred_hours', [])
        if hour in preferred_hours:
            acceptance_rate += 0.2
        
        # Avoid notifications during commute (unless task is related)
        if activity == 'IN_VEHICLE' and task_type != 'Get Fuel':
            acceptance_rate -= 0.4
        
        # Cap at [0, 1]
        acceptance_rate = max(0.0, min(1.0, acceptance_rate))
        
        # Make decision
        feedback = 'accept' if random.random() < acceptance_rate else 'reject'
        
        self.feedback_log.append({
            'task_type': task_type,
            'timing_window': timing_window,
            'activity': activity,
            'location': location,
            'hour': hour,
            'acceptance_rate': acceptance_rate,
            'feedback': feedback
        })
        
        return feedback
    
    def get_acceptance_rate(self, task_type: str = None) -> float:
        """Calculate actual acceptance rate from simulated feedback"""
        logs = self.feedback_log
        if task_type:
            logs = [l for l in logs if l['task_type'] == task_type]
        
        if not logs:
            return 0.0
        
        accepts = sum(1 for l in logs if l['feedback'] == 'accept')
        return accepts / len(logs)


class LearningTestFramework:
    """
    Main testing framework that orchestrates simulations and validations.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.clock = SimulatedClock(datetime(2025, 12, 19, 8, 0))
        self.context_sim = ContextSimulator(seed=42)
        self.feedback_sim = FeedbackSimulator(seed=42)
        self.learning_service = LearningService(db_session)
        self.optimizer = BayesianTimingOptimizer(db_session)
        self.test_results = []
    
    def run_learning_cycle(
        self,
        task_type: str,
        context: UserContextSchema,
        timing_window: int,
        feedback: str,
        iterations: int = 1
    ) -> Dict[str, Any]:
        """
        Run learning cycle: present task, receive feedback, update Beta distribution.
        
        Returns:
            Results including confidence trajectory
        """
        confidence_trajectory = []
        
        for i in range(iterations):
            # Get current confidence before feedback
            timing_result = self.optimizer.get_optimal_timing(task_type, context)
            current_confidence = next(
                (w['confidence'] for w in timing_result['all_windows'] if w['window'] == timing_window),
                0.5
            )
            
            # Record feedback
            result = self.learning_service.record_feedback(
                task_id=1,
                task_type=task_type,
                context=context,
                timing_window=timing_window,
                feedback=feedback
            )
            
            confidence_trajectory.append({
                'iteration': i,
                'confidence_before': current_confidence,
                'confidence_after': result['beta_distribution']['confidence'],
                'alpha': result['beta_distribution']['alpha'],
                'beta': result['beta_distribution']['beta']
            })
            
            # Advance simulated time
            self.clock.advance(hours=24)
        
        return {
            'task_type': task_type,
            'timing_window': timing_window,
            'feedback': feedback,
            'iterations': iterations,
            'trajectory': confidence_trajectory,
            'final_confidence': confidence_trajectory[-1]['confidence_after'] if confidence_trajectory else 0.5
        }
    
    def test_confidence_increases_with_accepts(self) -> Dict[str, Any]:
        """
        Test: Confidence should increase with repeated accepts.
        """
        task_type = "Check Email"
        context = self.context_sim.generate_morning_home_context(self.clock.now())
        timing_window = 30
        
        result = self.run_learning_cycle(
            task_type=task_type,
            context=context,
            timing_window=timing_window,
            feedback='accept',
            iterations=10
        )
        
        # Verify confidence increased
        initial_conf = result['trajectory'][0]['confidence_before']
        final_conf = result['final_confidence']
        
        passed = final_conf > initial_conf
        
        return {
            'test_name': 'Confidence Increases with Accepts',
            'passed': passed,
            'initial_confidence': round(initial_conf, 3),
            'final_confidence': round(final_conf, 3),
            'change': round(final_conf - initial_conf, 3),
            'expected': 'positive change',
            'details': result
        }
    
    def test_confidence_decreases_with_rejects(self) -> Dict[str, Any]:
        """
        Test: Confidence should decrease with repeated rejects.
        """
        task_type = "Morning Workout"
        context = self.context_sim.generate_morning_home_context(self.clock.now())
        timing_window = 60
        
        result = self.run_learning_cycle(
            task_type=task_type,
            context=context,
            timing_window=timing_window,
            feedback='reject',
            iterations=10
        )
        
        # Verify confidence decreased
        initial_conf = result['trajectory'][0]['confidence_before']
        final_conf = result['final_confidence']
        
        passed = final_conf < initial_conf
        
        return {
            'test_name': 'Confidence Decreases with Rejects',
            'passed': passed,
            'initial_confidence': round(initial_conf, 3),
            'final_confidence': round(final_conf, 3),
            'change': round(final_conf - initial_conf, 3),
            'expected': 'negative change',
            'details': result
        }
    
    def test_timing_optimization_shifts_to_better_window(self) -> Dict[str, Any]:
        """
        Test: System should shift timing recommendations toward higher acceptance windows.
        """
        task_type = "Team Meeting Reminder"
        context = self.context_sim.generate_work_context(self.clock.now())
        
        # Simulate user preferring 30-minute window over 60-minute
        # Give positive feedback for 30min, negative for 60min
        
        # First, negative feedback for 60min window (10 iterations)
        for i in range(10):
            self.learning_service.record_feedback(
                task_id=1,
                task_type=task_type,
                context=context,
                timing_window=60,
                feedback='reject'
            )
            self.clock.advance(hours=24)
        
        # Then, positive feedback for 30min window (10 iterations)
        for i in range(10):
            self.learning_service.record_feedback(
                task_id=1,
                task_type=task_type,
                context=context,
                timing_window=30,
                feedback='accept'
            )
            self.clock.advance(hours=24)
        
        # Now get optimal timing
        timing_result = self.optimizer.get_optimal_timing(task_type, context)
        optimal_window = timing_result['timing_window']
        
        # Verify 30min is now preferred over 60min
        window_30_conf = next((w['confidence'] for w in timing_result['all_windows'] if w['window'] == 30), 0)
        window_60_conf = next((w['confidence'] for w in timing_result['all_windows'] if w['window'] == 60), 0)
        
        passed = optimal_window == 30 and window_30_conf > window_60_conf
        
        return {
            'test_name': 'Timing Optimization Shifts to Better Window',
            'passed': passed,
            'optimal_window': optimal_window,
            'window_30_confidence': round(window_30_conf, 3),
            'window_60_confidence': round(window_60_conf, 3),
            'expected': '30min window preferred',
            'all_windows': timing_result['all_windows']
        }
    
    def test_realistic_user_behavior_simulation(self) -> Dict[str, Any]:
        """
        Test: Simulate realistic user with preferences and verify learning adapts.
        """
        task_type = "Gym Reminder"
        
        # Define user profile: prefers evening, at home, 30-minute advance notice
        user_profile = {
            'preferred_windows': [30],
            'preferred_activities': ['STILL', 'WALKING'],
            'preferred_locations': ['home'],
            'preferred_hours': [18, 19, 20]  # Evening
        }
        
        # Simulate 50 interactions across different contexts
        for i in range(50):
            # Generate realistic context based on time
            context = self.context_sim.generate_context_by_time(self.clock.now())
            
            # Choose random timing window
            timing_window = random.choice([60, 30, 10])
            
            # Simulate user feedback based on preferences
            feedback = self.feedback_sim.simulate_preference(
                task_type=task_type,
                context=context,
                timing_window=timing_window,
                user_profile=user_profile
            )
            
            # Record feedback
            self.learning_service.record_feedback(
                task_id=1,
                task_type=task_type,
                context=context,
                timing_window=timing_window,
                feedback=feedback
            )
            
            # Advance time by random interval (simulate irregular usage)
            self.clock.advance(hours=random.randint(1, 48))
        
        # Now test if system learned the preference
        evening_home_context = self.context_sim.generate_evening_home_context(
            datetime(2025, 12, 20, 19, 0)  # 7 PM at home
        )
        
        timing_result = self.optimizer.get_optimal_timing(task_type, evening_home_context)
        optimal_window = timing_result['timing_window']
        
        # Calculate actual acceptance rate from simulation
        actual_acceptance_rate = self.feedback_sim.get_acceptance_rate(task_type)
        
        # System should have learned that 30min is preferred in evening at home
        passed = optimal_window == 30 and actual_acceptance_rate > 0.4
        
        return {
            'test_name': 'Realistic User Behavior Simulation',
            'passed': passed,
            'optimal_window': optimal_window,
            'total_interactions': 50,
            'acceptance_rate': round(actual_acceptance_rate, 3),
            'confidence': timing_result['confidence'],
            'expected': '30min window in evening at home',
            'user_profile': user_profile
        }
    
    def test_deterministic_behavior(self) -> Dict[str, Any]:
        """
        Test: Same input sequence should produce same output (deterministic).
        """
        task_type = "Determinism Test Task"  # Use unique task type to avoid conflicts
        
        # Run sequence twice with same seed
        results_run1 = []
        results_run2 = []
        
        # First run
        self.context_sim = ContextSimulator(seed=100)
        self.feedback_sim = FeedbackSimulator(seed=100)
        self.clock.reset(datetime(2025, 12, 19, 8, 0))
        
        for i in range(5):
            context = self.context_sim.generate_morning_home_context(self.clock.now())
            result = self.learning_service.record_feedback(
                task_id=1,
                task_type=task_type,
                context=context,
                timing_window=30,
                feedback='accept'
            )
            results_run1.append(result['beta_distribution']['confidence'])
            self.clock.advance(hours=24)
        
        # Get final state from run 1
        timing_result_1 = self.optimizer.get_optimal_timing(
            task_type,
            self.context_sim.generate_morning_home_context(self.clock.now())
        )
        final_conf_1 = timing_result_1['confidence']
        
        # Reset simulators and run again with same seed on different task type
        task_type_2 = "Determinism Test Task 2"  # Different task to get clean state
        self.context_sim = ContextSimulator(seed=100)
        self.feedback_sim = FeedbackSimulator(seed=100)
        self.clock.reset(datetime(2025, 12, 19, 8, 0))
        
        for i in range(5):
            context = self.context_sim.generate_morning_home_context(self.clock.now())
            result = self.learning_service.record_feedback(
                task_id=1,
                task_type=task_type_2,
                context=context,
                timing_window=30,
                feedback='accept'
            )
            results_run2.append(result['beta_distribution']['confidence'])
            self.clock.advance(hours=24)
        
        # Get final state from run 2
        timing_result_2 = self.optimizer.get_optimal_timing(
            task_type_2,
            self.context_sim.generate_morning_home_context(self.clock.now())
        )
        final_conf_2 = timing_result_2['confidence']
        
        # Verify both runs produced identical confidence progressions
        # (they should since both start from Beta(1,1) prior and receive same feedback)
        passed = results_run1 == results_run2 and abs(final_conf_1 - final_conf_2) < 0.001
        
        return {
            'test_name': 'Deterministic Behavior',
            'passed': passed,
            'run1_confidences': [round(c, 3) for c in results_run1],
            'run2_confidences': [round(c, 3) for c in results_run2],
            'final_conf_1': round(final_conf_1, 3),
            'final_conf_2': round(final_conf_2, 3),
            'expected': 'identical results',
            'match': passed
        }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run complete test suite"""
        print("🧪 Running Bayesian Learning Test Suite\n")
        print("=" * 70)
        
        tests = [
            self.test_confidence_increases_with_accepts,
            self.test_confidence_decreases_with_rejects,
            self.test_timing_optimization_shifts_to_better_window,
            self.test_realistic_user_behavior_simulation,
            self.test_deterministic_behavior
        ]
        
        results = []
        passed_count = 0
        
        for test_func in tests:
            result = test_func()
            results.append(result)
            
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            print(f"\n{status} - {result['test_name']}")
            
            if result['passed']:
                passed_count += 1
            
            # Print key metrics
            for key, value in result.items():
                if key not in ['test_name', 'passed', 'details']:
                    print(f"  {key}: {value}")
        
        print("\n" + "=" * 70)
        print(f"Test Summary: {passed_count}/{len(tests)} tests passed")
        print("=" * 70)
        
        return {
            'total_tests': len(tests),
            'passed': passed_count,
            'failed': len(tests) - passed_count,
            'pass_rate': round(passed_count / len(tests) * 100, 1),
            'results': results
        }


# Convenience function to run tests
def run_learning_tests():
    """Run all learning tests"""
    # Create fresh database session
    db = next(get_db())
    
    try:
        # Initialize test framework
        framework = LearningTestFramework(db)
        
        # Run all tests
        summary = framework.run_all_tests()
        
        return summary
    
    finally:
        db.close()


if __name__ == "__main__":
    # Run tests when script is executed directly
    results = run_learning_tests()
    
    if results['pass_rate'] == 100.0:
        print("\n🎉 All tests passed! Learning system is working correctly.")
    else:
        print(f"\n⚠️  {results['failed']} test(s) failed. Review results above.")
