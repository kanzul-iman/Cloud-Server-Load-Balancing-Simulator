"""
Unit tests for Cloud Load Balancer Simulator.
Tests both static baseline equivalence and dynamic discrete-event behavior.
"""

import os
import unittest
from simulator.models import CloudRequest, CloudServer
from simulator.algorithms import (
    RoundRobinScheduler,
    LeastLoadedScheduler,
    WeightedRoundRobinScheduler,
    DynamicLeastConnectionsScheduler,
)
from simulator.engine import SimulationEngine


class TestSimulator(unittest.TestCase):
    def setUp(self):
        self.csv_path = os.path.join(
            os.path.dirname(__file__), "..", "cloud_load_balancer_dataset_1000.csv"
        )
        self.engine = SimulationEngine([
            CloudServer(1, "Server 1"),
            CloudServer(2, "Server 2"),
            CloudServer(3, "Server 3"),
        ])
        loaded = self.engine.load_dataset_from_csv(self.csv_path)
        self.assertEqual(loaded, 1000)

    def test_static_round_robin_equivalence(self):
        """Verify Static Round Robin matches historical values exactly."""
        rr = RoundRobinScheduler()
        res = self.engine.run(rr, mode="static")
        metrics = res.metrics

        self.assertEqual(metrics["Total_Workload_ms"], 195367)
        self.assertEqual(metrics["Server_Loads"]["Server 1"], 63127)
        self.assertEqual(metrics["Server_Loads"]["Server 2"], 67379)
        self.assertEqual(metrics["Server_Loads"]["Server 3"], 64861)
        self.assertEqual(metrics["Load_Imbalance_ms"], 4252)

    def test_static_least_loaded_equivalence(self):
        """Verify Static Least Loaded matches historical values exactly."""
        ll = LeastLoadedScheduler()
        res = self.engine.run(ll, mode="static")
        metrics = res.metrics

        self.assertEqual(metrics["Total_Workload_ms"], 195367)
        self.assertEqual(metrics["Server_Loads"]["Server 1"], 64981)
        self.assertEqual(metrics["Server_Loads"]["Server 2"], 64990)
        self.assertEqual(metrics["Server_Loads"]["Server 3"], 65396)
        self.assertEqual(metrics["Load_Imbalance_ms"], 415)

    def test_dynamic_simulation(self):
        """Verify Dynamic Discrete-Event Simulation generates valid metrics."""
        dlc = DynamicLeastConnectionsScheduler()
        res = self.engine.run(dlc, mode="dynamic")
        metrics = res.metrics

        self.assertEqual(metrics["Total_Requests"], 1000)
        self.assertGreater(metrics["Simulation_Makespan_sec"], 0)
        self.assertGreaterEqual(metrics["Avg_Waiting_Time_ms"], 0)
        self.assertGreater(metrics["Avg_Response_Time_ms"], 0)
        self.assertGreater(metrics["Overall_Utilization_Pct"], 0)

    def test_heterogeneous_weighted_round_robin(self):
        """Verify Weighted Round Robin distributes according to server weights."""
        hetero_servers = [
            CloudServer(1, "Server 1 (Fast)", capacity_weight=2.0),
            CloudServer(2, "Server 2 (Standard)", capacity_weight=1.0),
            CloudServer(3, "Server 3 (Standard)", capacity_weight=1.0),
        ]
        engine = SimulationEngine(hetero_servers)
        engine.load_dataset_from_csv(self.csv_path)

        wrr = WeightedRoundRobinScheduler()
        res = engine.run(wrr, mode="static")
        counts = res.metrics["Server_Counts"]
        # Fast server with 2.0x weight should receive roughly 500 requests (2 out of 4)
        self.assertEqual(counts["Server 1 (Fast)"], 500)
        self.assertEqual(counts["Server 2 (Standard)"], 250)
        self.assertEqual(counts["Server 3 (Standard)"], 250)


if __name__ == "__main__":
    unittest.main()
