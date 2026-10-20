"""
Scheduling algorithms for Cloud Server Load Balancing.
Includes both static heuristic schedulers, dynamic time-aware schedulers,
and the state-aware Adaptive Capacity-Aware Load Balancing (ACALB) algorithm.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from .models import CloudRequest, CloudServer, ServerState


def get_eligible_servers(servers: List[CloudServer]) -> List[CloudServer]:
    """
    Filter servers to only those eligible to accept new incoming requests.
    Excludes servers that are FAILED, RECOVERING, or actively DRAINING.
    """
    eligible = [
        s for s in servers
        if s.state not in (ServerState.FAILED, ServerState.RECOVERING)
        and not getattr(s, "is_draining", False)
    ]
    return eligible if eligible else []


class BaseScheduler(ABC):
    """Abstract Base Class for all Cloud Load Balancing schedulers."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def select_server(
        self,
        request: CloudRequest,
        servers: List[CloudServer],
        current_time_sec: float = 0.0
    ) -> CloudServer:
        """Select the target server for an incoming request."""
        pass

    def reset(self) -> None:
        """Reset internal algorithm state if any."""
        pass


class RoundRobinScheduler(BaseScheduler):
    """
    Classic Round Robin Scheduler.
    Cyclically distributes incoming requests evenly across servers regardless of processing time.
    In Chaos mode, skips failed or recovering nodes.
    """

    def __init__(self, name: str = "Round Robin"):
        super().__init__(name)
        self._index = 0

    def select_server(
        self,
        request: CloudRequest,
        servers: List[CloudServer],
        current_time_sec: float = 0.0
    ) -> CloudServer:
        if not servers:
            raise ValueError("No servers available for scheduling.")
        
        # In presence of server states, prefer eligible servers
        eligible = get_eligible_servers(servers)
        pool = eligible if eligible else servers
        
        selected = pool[self._index % len(pool)]
        self._index += 1
        return selected

    def reset(self) -> None:
        self._index = 0


class LeastLoadedScheduler(BaseScheduler):
    """
    Cumulative Least Loaded (Heuristic) Scheduler.
    Selects the server with the lowest cumulative assigned processing time so far.
    Preserves and standardizes the user's original heuristic baseline.
    """

    def __init__(self, name: str = "Least Loaded (Cumulative)"):
        super().__init__(name)

    def select_server(
        self,
        request: CloudRequest,
        servers: List[CloudServer],
        current_time_sec: float = 0.0
    ) -> CloudServer:
        if not servers:
            raise ValueError("No servers available for scheduling.")
        
        eligible = get_eligible_servers(servers)
        pool = eligible if eligible else servers
        
        # Select server with minimum cumulative assigned workload
        # Deterministic tie-breaking on server_id
        return min(pool, key=lambda s: (s.cumulative_workload_ms, s.server_id))


class WeightedRoundRobinScheduler(BaseScheduler):
    """
    Weighted Round Robin Scheduler.
    Distributes requests proportionally based on server capacity weights.
    Higher capacity servers receive proportionally more requests.
    """

    def __init__(self, name: str = "Weighted Round Robin"):
        super().__init__(name)
        self._current_index = -1
        self._current_weight = 0

    def select_server(
        self,
        request: CloudRequest,
        servers: List[CloudServer],
        current_time_sec: float = 0.0
    ) -> CloudServer:
        if not servers:
            raise ValueError("No servers available for scheduling.")

        eligible = get_eligible_servers(servers)
        pool = eligible if eligible else servers

        n = len(pool)
        weights = [int(round(s.effective_capacity * 10)) for s in pool]
        max_weight = max(weights) if weights else 1
        import math
        gcd_weight = math.gcd(*weights) if len(weights) > 1 else (weights[0] if weights else 1)
        if gcd_weight == 0:
            gcd_weight = 1

        while True:
            self._current_index = (self._current_index + 1) % n
            if self._current_index == 0:
                self._current_weight -= gcd_weight
                if self._current_weight <= 0:
                    self._current_weight = max_weight
                    if self._current_weight == 0:
                        return pool[0]
            if weights[self._current_index] >= self._current_weight:
                return pool[self._current_index]

    def reset(self) -> None:
        self._current_index = -1
        self._current_weight = 0


class DynamicLeastConnectionsScheduler(BaseScheduler):
    """
    Dynamic Least Connections / Shortest Active Queue Scheduler.
    Time-aware load balancer that queries instantaneous remaining execution
    time at request arrival timestamp. Assigns to the server that will finish earliest.
    """

    def __init__(self, name: str = "Dynamic Least Connections"):
        super().__init__(name)

    def select_server(
        self,
        request: CloudRequest,
        servers: List[CloudServer],
        current_time_sec: float = 0.0
    ) -> CloudServer:
        if not servers:
            raise ValueError("No servers available for scheduling.")

        eligible = get_eligible_servers(servers)
        pool = eligible if eligible else servers

        if current_time_sec == 0.0 and all(s.busy_until_sec == 0.0 for s in pool):
            return min(pool, key=lambda s: (s.cumulative_workload_ms / s.effective_capacity, s.server_id))

        # Evaluate expected finish time for this request on each server
        def expected_finish_time(s: CloudServer) -> float:
            start_sec = max(request.arrival_time_sec, s.busy_until_sec)
            duration_sec = request.processing_time_ms / (1000.0 * s.effective_capacity)
            return start_sec + duration_sec

        return min(pool, key=lambda s: (expected_finish_time(s), s.server_id))


class ShortestJobFirstScheduler(BaseScheduler):
    """
    Shortest Job First / Size-Aware Scheduler.
    Routes lighter requests to designated fast servers and heavier batches to high-capacity nodes.
    """

    def __init__(self, name: str = "Shortest Job First"):
        super().__init__(name)

    def select_server(
        self,
        request: CloudRequest,
        servers: List[CloudServer],
        current_time_sec: float = 0.0
    ) -> CloudServer:
        if not servers:
            raise ValueError("No servers available for scheduling.")
        
        eligible = get_eligible_servers(servers)
        pool = eligible if eligible else servers

        if current_time_sec == 0.0 and all(s.busy_until_sec == 0.0 for s in pool):
            return min(pool, key=lambda s: (s.cumulative_workload_ms / s.effective_capacity, s.server_id))
        return min(
            pool,
            key=lambda s: (s.get_remaining_workload_ms_at(request.arrival_time_sec) / s.effective_capacity, s.server_id)
        )


class AdaptiveCapacityAwareScheduler(BaseScheduler):
    """
    Adaptive Capacity-Aware Load Balancing (ACALB).
    
    A resilient, explainable scheduling algorithm designed for distributed cloud clusters
    subject to dynamic faults, throttling, and traffic spikes.
    
    Formula:
        Score(s) = [ (Queued Work (ms) + Incoming Work (ms)) / (Effective Capacity(s) * 1000) ] + Network Latency(s)
        
    Where:
      - Effective Capacity(s) = capacity_weight * degradation_factor
      - Queued Work(s) = instantaneous remaining time of active task + durations of queued requests
      - Network Latency(s) = modeled communication delay to server s (default 0.002s)
      
    Algorithmic Properties:
      - Eligible filtering: Excludes FAILED, RECOVERING, or DRAINING nodes.
      - Degradation awareness: Avoids throttling bottlenecks by down-weighting degraded nodes.
      - Deterministic tie-breaking: Selects lowest score; ties broken by lowest server_id.
      - Computational complexity: O(N) where N is number of eligible servers.
      - Space complexity: O(1) auxiliary state.
    """

    def __init__(
        self,
        name: str = "Adaptive Capacity-Aware (ACALB)",
        default_network_latency_sec: float = 0.002,
        network_latency_map: Optional[Dict[int, float]] = None
    ):
        super().__init__(name)
        self.default_network_latency_sec = default_network_latency_sec
        self.network_latency_map = network_latency_map or {}

    def calculate_score(
        self,
        server: CloudServer,
        request: CloudRequest,
        current_time_sec: float
    ) -> float:
        """Compute the explainable Estimated Completion Time (ECT) score."""
        eff_cap = server.effective_capacity
        
        # Calculate instantaneous pending workload on this server
        if current_time_sec == 0.0 and hasattr(server, "cumulative_workload_ms") and not getattr(server, "pending_queue", None) and server.busy_until_sec == 0.0:
            queued_work_ms = server.cumulative_workload_ms
        elif hasattr(server, "pending_queue") and server.pending_queue:
            queued_work_ms = sum(r.processing_time_ms for r in server.pending_queue)
        else:
            queued_work_ms = 0.0

        if hasattr(server, "active_task_finish_sec") and server.active_task_finish_sec is not None:
            active_remaining_sec = max(0.0, server.active_task_finish_sec - current_time_sec)
            queued_work_ms += (active_remaining_sec * 1000.0 * eff_cap)
        elif server.busy_until_sec > current_time_sec:
            queued_work_ms += max(0.0, (server.busy_until_sec - current_time_sec) * 1000.0)

        incoming_work_ms = request.processing_time_ms
        total_work_ms = queued_work_ms + incoming_work_ms
        
        # Processing duration in seconds factoring effective capacity
        exec_delay_sec = total_work_ms / (1000.0 * eff_cap)
        network_delay_sec = self.network_latency_map.get(server.server_id, self.default_network_latency_sec)
        
        return exec_delay_sec + network_delay_sec

    def select_server(
        self,
        request: CloudRequest,
        servers: List[CloudServer],
        current_time_sec: float = 0.0
    ) -> CloudServer:
        if not servers:
            raise ValueError("No servers available for scheduling.")

        eligible = get_eligible_servers(servers)
        if not eligible:
            raise ValueError("No healthy or eligible servers available in the cluster.")

        # Compute score for each eligible server and pick minimum
        best_server = min(
            eligible,
            key=lambda s: (self.calculate_score(s, request, current_time_sec), s.server_id)
        )
        return best_server
