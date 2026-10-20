"""
Unit and integration tests for AutoScaler.
Covers scale-out threshold, scale-in safety, cooldown window,
and min/max server constraints.
"""

import unittest
from simulator.models import CloudServer, CloudRequest, ServerState
from simulator.autoscaler import AutoScaler


class TestAutoScaler(unittest.TestCase):
    def setUp(self):
        self.scaler = AutoScaler(
            enabled=True,
            scale_out_threshold_pct=80.0,
            scale_in_threshold_pct=25.0,
            min_servers=2,
            max_servers=4,
            cooldown_sec=10.0
        )

    def test_scale_out_condition(self):
        """Test 10: High sustained CPU triggers scale-out decision."""
        s1 = CloudServer(1, "Server 1")
        s2 = CloudServer(2, "Server 2")
        # Give them active requests and high queue so utilization is 95%
        s1.active_request = CloudRequest("R1", "00:00", 0.0, "API", 500, 1)
        s1.pending_queue = [CloudRequest(f"Q{i}", "00:00", 0.0, "API", 200, 1) for i in range(5)]
        s2.active_request = CloudRequest("R2", "00:00", 0.0, "API", 500, 1)
        s2.pending_queue = [CloudRequest(f"Q{i}", "00:00", 0.0, "API", 200, 1) for i in range(5)]

        decision = self.scaler.evaluate(current_time_sec=10.0, servers=[s1, s2])
        self.assertIsNotNone(decision)
        self.assertEqual(decision.action, "SCALE_OUT")
        self.assertGreater(decision.avg_utilization_pct, 80.0)

    def test_scale_in_safety(self):
        """Test 11: Low utilization triggers safe scale-in candidate selection."""
        s1 = CloudServer(1, "Server 1")
        s2 = CloudServer(2, "Server 2")
        s3 = CloudServer(3, "Server 3")  # completely idle
        
        # All servers idle (0% CPU)
        decision = self.scaler.evaluate(current_time_sec=20.0, servers=[s1, s2, s3])
        self.assertIsNotNone(decision)
        self.assertEqual(decision.action, "SCALE_IN")
        self.assertEqual(decision.target_server_id, 3)

    def test_autoscaling_cooldown(self):
        """Test 12: Cooldown period suppresses rapid scaling actions."""
        s1 = CloudServer(1, "Server 1")
        s2 = CloudServer(2, "Server 2")
        s1.active_request = CloudRequest("R1", "00:00", 0.0, "API", 500, 1)
        s1.pending_queue = [CloudRequest("Q1", "00:00", 0.0, "API", 200, 1)]
        s2.active_request = CloudRequest("R2", "00:00", 0.0, "API", 500, 1)
        s2.pending_queue = [CloudRequest("Q2", "00:00", 0.0, "API", 200, 1)]

        # First evaluation triggers SCALE_OUT at t=5.0s
        d1 = self.scaler.evaluate(current_time_sec=5.0, servers=[s1, s2])
        self.assertEqual(d1.action, "SCALE_OUT")

        # Second evaluation at t=8.0s (only 3s later, cooldown is 10s) must NOOP
        d2 = self.scaler.evaluate(current_time_sec=8.0, servers=[s1, s2])
        self.assertIsNotNone(d2)
        self.assertEqual(d2.action, "NOOP")
        self.assertIn("cooldown", d2.trigger_reason)

    def test_max_server_capacity_limit(self):
        """Test 13: Cluster cannot scale out beyond max_servers limit."""
        servers = [CloudServer(i, f"Server {i}") for i in range(1, 5)]  # 4 servers = max
        for s in servers:
            s.active_request = CloudRequest(f"R{s.server_id}", "00:00", 0.0, "API", 500, 1)
            s.pending_queue = [CloudRequest(f"Q{s.server_id}", "00:00", 0.0, "API", 200, 1)]

        decision = self.scaler.evaluate(current_time_sec=50.0, servers=servers)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.action, "NOOP")
        self.assertIn("maximum cluster limit", decision.trigger_reason)

    def test_min_server_capacity_limit(self):
        """Test 14: Cluster cannot scale in beyond min_servers limit."""
        s1 = CloudServer(1, "Server 1")
        s2 = CloudServer(2, "Server 2")  # 2 servers = min

        # Idle
        decision = self.scaler.evaluate(current_time_sec=50.0, servers=[s1, s2])
        self.assertIsNotNone(decision)
        self.assertEqual(decision.action, "NOOP")
        self.assertIn("minimum cluster limit", decision.trigger_reason)


if __name__ == "__main__":
    unittest.main()
