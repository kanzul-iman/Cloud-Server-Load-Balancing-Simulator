"""
Unit and integration tests for RecoveryManager.
Covers recovery of queued requests, retry limits, duplicate-completion prevention,
and complete cluster outages.
"""

import unittest
from simulator.models import CloudRequest, CloudServer, ServerState, RecoveryPolicy
from simulator.algorithms import RoundRobinScheduler
from simulator.recovery_manager import RecoveryManager
from simulator.chaos_engine import ChaosSimulationEngine


class TestRecovery(unittest.TestCase):
    def setUp(self):
        self.recovery = RecoveryManager(
            default_policy=RecoveryPolicy.RESTART_FROM_BEGINNING,
            max_retries=2
        )

    def test_recovery_of_queued_requests(self):
        """Test 3: Verify queued requests on failed server are harvested and reassigned."""
        s1 = CloudServer(1, "Server 1")
        s2 = CloudServer(2, "Server 2")
        
        req1 = CloudRequest("R1", "00:00.000", 0.0, "API", 200.0, 1.0)
        req2 = CloudRequest("R2", "00:00.000", 0.0, "API", 300.0, 1.0)
        s1.pending_queue = [req1, req2]

        scheduler = RoundRobinScheduler()
        reassigned, perm_failed = self.recovery.process_server_crash(
            failed_server=s1,
            failure_time_sec=1.0,
            detection_time_sec=2.0,
            eligible_servers=[s2],
            scheduler=scheduler
        )

        self.assertEqual(len(reassigned), 2)
        self.assertEqual(len(perm_failed), 0)
        self.assertEqual(req1.assigned_server, "Server 2")
        self.assertEqual(req2.assigned_server, "Server 2")
        self.assertTrue(req1.is_recovered)
        self.assertEqual(req1.retry_count, 1)

    def test_retry_limits(self):
        """Test 4: Request exceeding max_retries is marked permanently failed."""
        s1 = CloudServer(1, "Server 1")
        s2 = CloudServer(2, "Server 2")
        req = CloudRequest("RETRY-MAX", "00:00.000", 0.0, "Batch", 500.0, 2.0)
        req.retry_count = 2  # Already retried twice, max is 2

        s1.active_request = req
        scheduler = RoundRobinScheduler()
        reassigned, perm_failed = self.recovery.process_server_crash(
            failed_server=s1,
            failure_time_sec=1.0,
            detection_time_sec=2.0,
            eligible_servers=[s2],
            scheduler=scheduler
        )

        self.assertEqual(len(perm_failed), 1)
        self.assertTrue(req.is_failed)
        self.assertIn("Exceeded", req.failure_reason)

    def test_duplicate_completion_prevention(self):
        """Test 5: Completed request ID is finalized and cannot be re-processed."""
        s1 = CloudServer(1, "Server 1")
        req = CloudRequest("DUP-1", "00:00.000", 0.0, "API", 200.0, 1.0)
        self.recovery.finalized_request_ids.add(req.request_id)

        s1.pending_queue = [req]
        scheduler = RoundRobinScheduler()
        reassigned, perm_failed = self.recovery.process_server_crash(
            failed_server=s1,
            failure_time_sec=1.0,
            detection_time_sec=2.0,
            eligible_servers=[],
            scheduler=scheduler
        )

        # Since it was already finalized, it is ignored and not re-queued
        self.assertEqual(len(reassigned), 0)
        self.assertEqual(len(perm_failed), 0)

    def test_all_servers_failed_cluster_outage(self):
        """Test 6: When all servers fail, requests are buffered in cluster outage queue without loss."""
        s1 = CloudServer(1, "Server 1")
        req1 = CloudRequest("OUTAGE-1", "00:00.000", 0.0, "API", 200.0, 1.0)
        req2 = CloudRequest("OUTAGE-2", "00:00.000", 0.0, "API", 300.0, 1.0)
        s1.pending_queue = [req1, req2]

        scheduler = RoundRobinScheduler()
        reassigned, perm_failed = self.recovery.process_server_crash(
            failed_server=s1,
            failure_time_sec=1.0,
            detection_time_sec=2.0,
            eligible_servers=[],  # NO healthy servers left!
            scheduler=scheduler
        )

        self.assertEqual(len(self.recovery.cluster_outage_buffer), 2)
        self.assertIn(req1, self.recovery.cluster_outage_buffer)
        self.assertIn(req2, self.recovery.cluster_outage_buffer)

        # Now simulate server recovery: buffer should be drained
        restored = self.recovery.complete_server_recovery(s1, restoration_time_sec=5.0)
        self.assertEqual(len(restored), 2)
        self.assertEqual(len(self.recovery.cluster_outage_buffer), 0)


if __name__ == "__main__":
    unittest.main()
