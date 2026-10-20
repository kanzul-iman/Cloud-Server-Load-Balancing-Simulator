"""
Unit and integration tests for ChaosSimulationEngine.
Covers discrete-event scheduling, fault injection, degradation, traffic spikes,
deterministic ordering, pause/resume, metric accuracy, and request conservation.
"""

import unittest
import copy
from simulator.models import CloudRequest, CloudServer, ServerState, RecoveryPolicy
from simulator.algorithms import (
    RoundRobinScheduler,
    LeastLoadedScheduler,
    AdaptiveCapacityAwareScheduler
)
from simulator.chaos_engine import ChaosSimulationEngine


def make_test_requests(n: int = 20) -> list[CloudRequest]:
    """Generate a sequence of synthetic test requests."""
    reqs = []
    for i in range(n):
        reqs.append(CloudRequest(
            request_id=f"TEST-{i+1:03d}",
            arrival_time_str=f"00:{i:02d}.000",
            arrival_time_sec=float(i) * 0.5,
            request_type="Web-API",
            processing_time_ms=200.0,
            data_size_mb=5.0
        ))
    return reqs


class TestChaosEngine(unittest.TestCase):
    def setUp(self):
        self.servers = [
            CloudServer(server_id=1, name="Server 1", capacity_weight=1.0),
            CloudServer(server_id=2, name="Server 2", capacity_weight=1.0),
            CloudServer(server_id=3, name="Server 3", capacity_weight=1.0),
        ]
        self.engine = ChaosSimulationEngine(
            servers=self.servers,
            scheduler=AdaptiveCapacityAwareScheduler(),
            failure_detection_delay_sec=1.0
        )

    def test_deterministic_event_ordering(self):
        """Test 16: Ensure simulation executes events strictly by timestamp order."""
        reqs = make_test_requests(10)
        self.engine.initialize_workload(reqs)
        
        last_t = 0.0
        events_processed = 0
        while self.engine._event_queue:
            ev = self.engine.step()
            if ev is None:
                break
            self.assertGreaterEqual(ev.timestamp, last_t)
            last_t = ev.timestamp
            events_processed += 1
            
        self.assertGreater(events_processed, 10)

    def test_server_failure_detection(self):
        """Test 1: Verify server failure causes failure detection with configured latency."""
        reqs = make_test_requests(15)
        self.engine.initialize_workload(reqs)
        
        # Schedule crash of Server 2 at t=1.0s
        self.engine.inject_server_crash(2, timestamp_sec=1.0)
        self.engine.run_all()
        
        server2 = self.engine.get_server_by_id(2)
        self.assertEqual(server2.state, ServerState.FAILED)
        self.assertIsNotNone(server2.failure_timestamp)
        self.assertIsNotNone(server2.detection_timestamp)
        self.assertAlmostEqual(server2.detection_timestamp - server2.failure_timestamp, 1.0, places=1)

    def test_server_crash_during_active_request(self):
        """Test 2: Server crashes while processing a request; work is lost and request retried."""
        req = CloudRequest("ACTIVE-1", "00:00.000", 0.0, "Compute", 1000.0, 10.0)
        single_server_engine = ChaosSimulationEngine(
            servers=[
                CloudServer(1, "Server 1"),
                CloudServer(2, "Server 2")
            ],
            scheduler=RoundRobinScheduler(),
            failure_detection_delay_sec=0.5
        )
        single_server_engine.initialize_workload([req])
        # Crash Server 1 at t=0.2s while it is executing
        single_server_engine.inject_server_crash(1, timestamp_sec=0.2)
        single_server_engine.run_all()

        self.assertEqual(len(single_server_engine.completed_requests), 1)
        completed = single_server_engine.completed_requests[0]
        self.assertEqual(completed.retry_count, 1)
        self.assertTrue(completed.is_recovered)
        self.assertGreater(completed.lost_work_ms, 0.0)
        self.assertEqual(completed.assigned_server, "Server 2")

    def test_server_recovery(self):
        """Test 7: Recovering server rejoins cluster and accepts subsequent requests."""
        reqs = make_test_requests(15)
        self.engine.initialize_workload(reqs)
        
        self.engine.inject_server_crash(1, timestamp_sec=0.5)
        self.engine.inject_server_recovery(1, timestamp_sec=2.0)
        self.engine.run_all()

        server1 = self.engine.get_server_by_id(1)
        self.assertIn(server1.state, (ServerState.HEALTHY, ServerState.IDLE, ServerState.BUSY))
        self.assertGreater(len(server1.completed_requests), 0)

    def test_traffic_spike_injection(self):
        """Test 8: Sudden traffic spike increases queue and throughput."""
        reqs = make_test_requests(10)
        self.engine.initialize_workload(reqs)
        
        initial_count = len(self.engine.submitted_requests)
        self.engine.inject_traffic_spike(count=30, arrival_rate_rps=10.0, duration_sec=3.0, profile="medium")
        self.assertEqual(len(self.engine.submitted_requests), initial_count + 30)

        self.engine.run_all()
        m = self.engine.compute_comprehensive_metrics()
        self.assertEqual(m["Completed_Requests"], initial_count + 30)

    def test_cpu_degradation(self):
        """Test 9: Server CPU degradation increases execution duration."""
        req = CloudRequest("DEG-1", "00:00.000", 0.0, "Compute", 1000.0, 10.0)
        eng = ChaosSimulationEngine(
            servers=[CloudServer(1, "Server 1", capacity_weight=1.0)],
            scheduler=RoundRobinScheduler()
        )
        eng.initialize_workload([req])
        eng.inject_server_degradation(1, 0.5, timestamp_sec=0.0)  # 50% capacity
        eng.run_all()

        # At 1.0x capacity, 1000ms request takes 1.0s. At 0.5x capacity, takes 2.0s
        self.assertEqual(len(eng.completed_requests), 1)
        completed = eng.completed_requests[0]
        self.assertAlmostEqual(completed.completion_time_sec, 2.0, places=1)

    def test_request_conservation(self):
        """Test 18: Strict conservation: submitted == completed + in_flight + queued + failed."""
        reqs = make_test_requests(40)
        self.engine.initialize_workload(reqs)
        self.engine.inject_server_crash(1, timestamp_sec=2.0)
        self.engine.inject_traffic_spike(count=20, duration_sec=2.0, timestamp_sec=3.0)
        self.engine.run_all()

        m = self.engine.compute_comprehensive_metrics()
        self.assertTrue(m["Request_Conservation_Passed"])
        self.assertEqual(m["Total_Submitted_Requests"], m["Completed_Requests"] + m["Permanently_Failed_Requests"])

    def test_pause_resume_consistency(self):
        """Test 17: Pausing by stepping or run_until maintains consistent state."""
        reqs = make_test_requests(20)
        self.engine.initialize_workload(reqs)
        
        # Run until t = 3.0s
        self.engine.run_until(3.0)
        t_paused = self.engine.current_time_sec
        self.assertLessEqual(t_paused, 3.5)

        # Resume to completion
        self.engine.run_all()
        m = self.engine.compute_comprehensive_metrics()
        self.assertEqual(m["Completed_Requests"], 20)

    def test_accurate_metric_calculations(self):
        """Test 19: Metric calculation accurately computes averages, percentiles and energy."""
        reqs = make_test_requests(25)
        self.engine.initialize_workload(reqs)
        self.engine.run_all()

        m = self.engine.compute_comprehensive_metrics()
        self.assertGreater(m["Simulation_Makespan_sec"], 0)
        self.assertGreaterEqual(m["Average_Waiting_Time_ms"], 0)
        self.assertGreater(m["Average_Response_Time_ms"], 0)
        self.assertGreaterEqual(m["P99_Response_Time_ms"], m["P95_Response_Time_ms"])
        self.assertGreaterEqual(m["P95_Response_Time_ms"], m["Median_Response_Time_ms"])
        self.assertGreater(m["Estimated_Energy_kWh"], 0.0)
        self.assertGreater(m["Estimated_Cost_USD"], 0.0)

    def test_export_correctness(self):
        """Test 20: Event logger exports valid DataFrame, JSON, and CSV."""
        reqs = make_test_requests(5)
        self.engine.initialize_workload(reqs)
        self.engine.run_all()

        df_logs = self.engine.logger.to_dataframe()
        self.assertFalse(df_logs.empty)
        self.assertIn("Event_Type", df_logs.columns)
        self.assertIn("Sim_Time_sec", df_logs.columns)

        json_str = self.engine.logger.to_json()
        self.assertTrue(json_str.startswith("["))
        csv_str = self.engine.logger.to_csv()
        self.assertTrue("Event_Type" in csv_str)


if __name__ == "__main__":
    unittest.main()
