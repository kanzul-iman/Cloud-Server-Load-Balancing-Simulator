"""
Unit tests for Adaptive Capacity-Aware Load Balancing (ACALB) Scheduler.
Tests capacity awareness, health awareness, degradation responsiveness,
queue evaluation, and deterministic tie-breaking.
"""

import unittest
from simulator.models import CloudServer, CloudRequest, ServerState
from simulator.algorithms import AdaptiveCapacityAwareScheduler, get_eligible_servers


class TestAdaptiveAlgorithm(unittest.TestCase):
    def setUp(self):
        self.scheduler = AdaptiveCapacityAwareScheduler(
            default_network_latency_sec=0.001
        )

    def test_routes_away_from_failed_server(self):
        """ACALB must never route requests to a FAILED or RECOVERING server."""
        s1 = CloudServer(1, "Server 1", capacity_weight=2.0)
        s1.state = ServerState.FAILED
        s2 = CloudServer(2, "Server 2", capacity_weight=1.0)
        s2.state = ServerState.HEALTHY

        req = CloudRequest("REQ-1", "00:00", 0.0, "API", 500.0, 1.0)
        chosen = self.scheduler.select_server(req, [s1, s2], current_time_sec=1.0)
        self.assertEqual(chosen.server_id, 2)

    def test_routes_away_from_degraded_server(self):
        """ACALB prefers a normal server over a throttled/degraded server."""
        s1 = CloudServer(1, "Server 1", capacity_weight=1.0)
        s1.degradation_factor = 0.25  # 25% CPU throttle
        s2 = CloudServer(2, "Server 2", capacity_weight=1.0)
        s2.degradation_factor = 1.0   # 100% normal CPU

        req = CloudRequest("REQ-2", "00:00", 0.0, "Compute", 1000.0, 5.0)
        chosen = self.scheduler.select_server(req, [s1, s2], current_time_sec=0.0)
        self.assertEqual(chosen.server_id, 2)

    def test_prefers_higher_capacity_server_when_queues_empty(self):
        """ACALB routes to higher capacity server when both are idle."""
        s1 = CloudServer(1, "Server 1 (Slow)", capacity_weight=1.0)
        s2 = CloudServer(2, "Server 2 (Fast)", capacity_weight=2.0)

        req = CloudRequest("REQ-3", "00:00", 0.0, "Batch", 800.0, 10.0)
        chosen = self.scheduler.select_server(req, [s1, s2], current_time_sec=0.0)
        self.assertEqual(chosen.server_id, 2)

    def test_routes_to_shorter_queue_when_capacities_equal(self):
        """ACALB factors in existing queued work when picking a node."""
        s1 = CloudServer(1, "Server 1", capacity_weight=1.0)
        s1.pending_queue = [CloudRequest("Q1", "00:00", 0.0, "API", 600.0, 1.0)]
        s2 = CloudServer(2, "Server 2", capacity_weight=1.0)
        s2.pending_queue = []  # Empty

        req = CloudRequest("REQ-4", "00:00", 0.0, "API", 200.0, 1.0)
        chosen = self.scheduler.select_server(req, [s1, s2], current_time_sec=0.0)
        self.assertEqual(chosen.server_id, 2)

    def test_deterministic_tie_breaking(self):
        """Identical scores break ties deterministically on lower server_id."""
        s1 = CloudServer(1, "Server 1", capacity_weight=1.0)
        s2 = CloudServer(2, "Server 2", capacity_weight=1.0)

        req = CloudRequest("REQ-5", "00:00", 0.0, "API", 200.0, 1.0)
        chosen = self.scheduler.select_server(req, [s1, s2], current_time_sec=0.0)
        self.assertEqual(chosen.server_id, 1)

    def test_raises_when_all_servers_unavailable(self):
        """ACALB raises ValueError when zero healthy servers are present."""
        s1 = CloudServer(1, "Server 1")
        s1.state = ServerState.FAILED
        req = CloudRequest("REQ-6", "00:00", 0.0, "API", 200.0, 1.0)

        with self.assertRaises(ValueError):
            self.scheduler.select_server(req, [s1], current_time_sec=0.0)


if __name__ == "__main__":
    unittest.main()
