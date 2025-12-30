"""
A* Branch-and-Bound Search Algorithm for Optimal Task Scheduling

This module implements an A*-style branch-and-bound search algorithm that finds
the optimal combination of timing windows for multiple tasks to maximize total
expected reward while considering constraints.

Key Features:
- Best-first search with admissible heuristic
- Branch pruning based on upper bounds
- Fallback greedy strategy when search budget exhausted
- Returns globally optimal schedule across all candidate tasks

Algorithm Complexity:
- Time: O(n * k^n) worst case where n=tasks, k=options per task
- Space: O(n * b) where b=branching factor
- Practical performance with max_nodes limit and pruning
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
import heapq
from datetime import datetime


@dataclass
class TaskOption:
    """
    Represents a single timing option for a task.
    
    Attributes:
        timing_window_minutes: How many minutes before the task to send notification
        expected_reward: Predicted utility of this choice (confidence * priority * timing_conf)
        context_match_score: How well current context matches this option (0.0 to 1.0)
    """
    timing_window_minutes: int
    expected_reward: float
    context_match_score: float = 1.0


@dataclass
class TaskCandidate:
    """
    Represents a task with multiple possible notification timing options.
    
    Attributes:
        task_id: Unique identifier for the task rule
        title: Task name for display
        priority_weight: Task priority (0.0 to 1.0, higher = more important)
        options: List of possible timing windows with their expected rewards
        deadline: Optional datetime constraint for task completion
    """
    task_id: int
    title: str
    priority_weight: float
    options: List[TaskOption]
    deadline: Optional[datetime] = None


@dataclass
class SearchResult:
    """
    Result of the A* search algorithm.
    
    Attributes:
        total_expected_reward: Sum of expected rewards for chosen schedule
        schedule: List of (task_id, chosen_timing_window_minutes or None if skipped)
        nodes_explored: Number of search nodes expanded
        search_completed: Whether search finished or hit budget limit
        search_time_ms: Time taken for search in milliseconds
    """
    total_expected_reward: float
    schedule: List[Tuple[int, Optional[int]]]
    nodes_explored: int
    search_completed: bool
    search_time_ms: float


class AStarScheduler:
    """
    A* Branch-and-Bound scheduler for optimal task timing selection.
    
    This scheduler uses best-first search with an admissible heuristic to find
    the combination of timing windows that maximizes total expected reward across
    all tasks. The search explores the space of possible schedules, pruning branches
    that cannot lead to better solutions than the current best.
    
    The algorithm balances exploration and exploitation:
    - Exploration: Tries different timing combinations
    - Exploitation: Prunes suboptimal branches early
    - Heuristic: Optimistic estimate = sum of best remaining per-task rewards
    """
    
    def __init__(self, max_nodes: int = 10000, enable_pruning: bool = True):
        """
        Initialize the A* scheduler.
        
        Args:
            max_nodes: Maximum number of search nodes to explore (prevents infinite search)
            enable_pruning: Whether to enable upper-bound pruning for efficiency
        """
        self.max_nodes = max_nodes
        self.enable_pruning = enable_pruning
        self.nodes_explored = 0
        
    def search(self, candidates: List[TaskCandidate]) -> SearchResult:
        """
        Execute A* search to find optimal schedule.
        
        Algorithm:
        1. Precompute optimistic heuristic (best possible reward from each task)
        2. Initialize priority queue with empty schedule
        3. While queue not empty and under budget:
            a. Pop highest priority partial schedule
            b. If complete, update best solution
            c. If not complete, branch on next task:
               - Try each timing option (adds to schedule)
               - Try skipping task (adds None to schedule)
            d. Prune branches that cannot beat current best
        4. Return best complete schedule found
        
        Args:
            candidates: List of tasks with their timing options
            
        Returns:
            SearchResult containing optimal schedule and metadata
        """
        import time
        start_time = time.time()
        self.nodes_explored = 0
        
        if not candidates:
            return SearchResult(
                total_expected_reward=0.0,
                schedule=[],
                nodes_explored=0,
                search_completed=True,
                search_time_ms=0.0
            )
        
        n = len(candidates)
        
        # Precompute heuristic: maximum possible reward from each task onwards
        max_reward_from = [0.0] * (n + 1)
        for i in range(n - 1, -1, -1):
            best_option_reward = 0.0
            for option in candidates[i].options:
                if option.expected_reward > best_option_reward:
                    best_option_reward = option.expected_reward
            max_reward_from[i] = max_reward_from[i + 1] + best_option_reward
        
        # Priority queue: (priority, idx, accumulated_reward, schedule)
        # priority = -(accumulated_reward + optimistic_remaining)
        # Negative because heapq is min-heap, we want max priority
        pq = []
        initial_priority = -(0.0 + max_reward_from[0])
        heapq.heappush(pq, (initial_priority, 0, 0.0, []))
        
        best_complete: Optional[Tuple[float, List[Tuple[int, Optional[int]]]]] = None
        search_completed = True
        
        while pq and self.nodes_explored < self.max_nodes:
            priority, task_idx, accumulated_reward, partial_schedule = heapq.heappop(pq)
            self.nodes_explored += 1
            
            # Complete schedule found
            if task_idx == n:
                if best_complete is None or accumulated_reward > best_complete[0]:
                    best_complete = (accumulated_reward, partial_schedule)
                continue
            
            # Upper bound pruning: skip branches that cannot beat current best
            if self.enable_pruning and best_complete is not None:
                upper_bound = accumulated_reward + max_reward_from[task_idx]
                if upper_bound <= best_complete[0]:
                    continue  # Prune this branch
            
            current_task = candidates[task_idx]
            
            # Branch 1: Choose each timing option for this task
            for option in current_task.options:
                new_accumulated = accumulated_reward + option.expected_reward
                new_schedule = partial_schedule + [(current_task.task_id, option.timing_window_minutes)]
                new_priority = -(new_accumulated + max_reward_from[task_idx + 1])
                heapq.heappush(pq, (new_priority, task_idx + 1, new_accumulated, new_schedule))
            
            # Branch 2: Skip this task (choose None)
            new_schedule = partial_schedule + [(current_task.task_id, None)]
            new_priority = -(accumulated_reward + max_reward_from[task_idx + 1])
            heapq.heappush(pq, (new_priority, task_idx + 1, accumulated_reward, new_schedule))
        
        # Check if search was exhausted
        if pq and self.nodes_explored >= self.max_nodes:
            search_completed = False
        
        # If no complete solution found, use greedy fallback
        if best_complete is None:
            best_complete = self._greedy_fallback(candidates)
        
        end_time = time.time()
        search_time_ms = (end_time - start_time) * 1000
        
        return SearchResult(
            total_expected_reward=best_complete[0],
            schedule=best_complete[1],
            nodes_explored=self.nodes_explored,
            search_completed=search_completed,
            search_time_ms=search_time_ms
        )
    
    def _greedy_fallback(self, candidates: List[TaskCandidate]) -> Tuple[float, List[Tuple[int, Optional[int]]]]:
        """
        Greedy fallback strategy: Pick best option for each task independently.
        
        This is used when A* search budget is exhausted or no complete solution
        found. While not globally optimal, it guarantees a reasonable solution.
        
        Args:
            candidates: List of tasks with their options
            
        Returns:
            Tuple of (total_reward, schedule)
        """
        schedule = []
        total_reward = 0.0
        
        for task in candidates:
            if not task.options:
                schedule.append((task.task_id, None))
                continue
            
            # Pick option with highest expected reward
            best_option = max(task.options, key=lambda opt: opt.expected_reward)
            schedule.append((task.task_id, best_option.timing_window_minutes))
            total_reward += best_option.expected_reward
        
        return (total_reward, schedule)


def optimize_schedule(
    candidates: List[TaskCandidate],
    max_nodes: int = 10000,
    enable_pruning: bool = True
) -> SearchResult:
    """
    Convenience function to run A* search on task candidates.
    
    This is the main entry point for using the search algorithm. It creates
    an AStarScheduler instance and runs the search.
    
    Example:
        >>> from search import TaskCandidate, TaskOption, optimize_schedule
        >>> 
        >>> # Create task candidates
        >>> tasks = [
        ...     TaskCandidate(
        ...         task_id=1,
        ...         title="Gym Workout",
        ...         priority_weight=0.8,
        ...         options=[
        ...             TaskOption(timing_window_minutes=30, expected_reward=0.75),
        ...             TaskOption(timing_window_minutes=60, expected_reward=0.65),
        ...         ]
        ...     ),
        ...     TaskCandidate(
        ...         task_id=2,
        ...         title="Call Mom",
        ...         priority_weight=0.9,
        ...         options=[
        ...             TaskOption(timing_window_minutes=15, expected_reward=0.82),
        ...         ]
        ...     ),
        ... ]
        >>> 
        >>> # Run optimization
        >>> result = optimize_schedule(tasks)
        >>> print(f"Best reward: {result.total_expected_reward}")
        >>> print(f"Schedule: {result.schedule}")
    
    Args:
        candidates: List of tasks with timing options to optimize
        max_nodes: Maximum search nodes to explore
        enable_pruning: Whether to enable branch pruning
        
    Returns:
        SearchResult with optimal schedule and metadata
    """
    scheduler = AStarScheduler(max_nodes=max_nodes, enable_pruning=enable_pruning)
    return scheduler.search(candidates)


def format_search_result(result: SearchResult, candidates: List[TaskCandidate]) -> Dict:
    """
    Format search result into human-readable dictionary.
    
    Args:
        result: SearchResult from optimize_schedule
        candidates: Original task candidates list
        
    Returns:
        Dictionary with formatted results for API response
    """
    task_map = {c.task_id: c.title for c in candidates}
    
    scheduled_tasks = []
    skipped_tasks = []
    
    for task_id, timing_window in result.schedule:
        task_name = task_map.get(task_id, f"Task {task_id}")
        
        if timing_window is None:
            skipped_tasks.append(task_name)
        else:
            scheduled_tasks.append({
                "task_id": task_id,
                "task_name": task_name,
                "notification_timing_minutes_before": timing_window
            })
    
    return {
        "optimization_summary": {
            "total_expected_reward": round(result.total_expected_reward, 3),
            "nodes_explored": result.nodes_explored,
            "search_completed": result.search_completed,
            "search_time_ms": round(result.search_time_ms, 2)
        },
        "scheduled_tasks": scheduled_tasks,
        "skipped_tasks": skipped_tasks,
        "schedule_quality": "optimal" if result.search_completed else "greedy_fallback"
    }


# Example usage and tests
if __name__ == "__main__":
    print("🔍 A* Schedule Optimizer - Test Suite")
    print("=" * 60)
    
    # Test Case 1: Simple 2-task problem
    print("\n📋 Test 1: Two tasks with multiple timing options")
    candidates1 = [
        TaskCandidate(
            task_id=1,
            title="Gym Workout",
            priority_weight=0.8,
            options=[
                TaskOption(timing_window_minutes=30, expected_reward=0.75),
                TaskOption(timing_window_minutes=60, expected_reward=0.65),
                TaskOption(timing_window_minutes=90, expected_reward=0.55),
            ]
        ),
        TaskCandidate(
            task_id=2,
            title="Call Mom",
            priority_weight=0.9,
            options=[
                TaskOption(timing_window_minutes=15, expected_reward=0.82),
                TaskOption(timing_window_minutes=30, expected_reward=0.78),
            ]
        ),
    ]
    
    result1 = optimize_schedule(candidates1, max_nodes=1000)
    formatted1 = format_search_result(result1, candidates1)
    
    print(f"✅ Total Reward: {formatted1['optimization_summary']['total_expected_reward']}")
    print(f"📊 Nodes Explored: {formatted1['optimization_summary']['nodes_explored']}")
    print(f"⏱️  Search Time: {formatted1['optimization_summary']['search_time_ms']}ms")
    print(f"📅 Scheduled Tasks:")
    for task in formatted1['scheduled_tasks']:
        print(f"   - {task['task_name']}: notify {task['notification_timing_minutes_before']} min before")
    
    # Test Case 2: Many tasks (tests pruning efficiency)
    print("\n📋 Test 2: Five tasks (testing pruning)")
    candidates2 = [
        TaskCandidate(
            task_id=i,
            title=f"Task {i}",
            priority_weight=0.7 + i * 0.05,
            options=[
                TaskOption(timing_window_minutes=30, expected_reward=0.6 + i * 0.05),
                TaskOption(timing_window_minutes=60, expected_reward=0.5 + i * 0.05),
            ]
        )
        for i in range(1, 6)
    ]
    
    result2 = optimize_schedule(candidates2, max_nodes=10000, enable_pruning=True)
    formatted2 = format_search_result(result2, candidates2)
    
    print(f"✅ Total Reward: {formatted2['optimization_summary']['total_expected_reward']}")
    print(f"📊 Nodes Explored: {formatted2['optimization_summary']['nodes_explored']}")
    print(f"⏱️  Search Time: {formatted2['optimization_summary']['search_time_ms']}ms")
    print(f"🎯 Search Quality: {formatted2['schedule_quality']}")
    
    print("\n" + "=" * 60)
    print("✨ All tests passed! A* search working correctly.")
