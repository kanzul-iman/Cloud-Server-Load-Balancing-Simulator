"""
Health Monitor and Heartbeat Failure Detector for Cloud Chaos Lab.
Accurately models distributed heartbeat pings, detection delays,
and cluster node health state transitions.
"""

from typing import List, Dict, Optional, Tuple
from .models import CloudServer, ServerState
from .event_logger import EventLogger


class HealthMonitor:
    """
    Simulates a distributed cluster health monitoring agent.
    Performs periodic heartbeat probes and detects unannounced node crashes.
    """

    def __init__(
        self,
        heartbeat_interval_sec: float = 2.0,
        detection_delay_sec: float = 1.5,
        heartbeat_timeout_sec: float = 4.0
    ):
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.detection_delay_sec = detection_delay_sec
        self.heartbeat_timeout_sec = heartbeat_timeout_sec

        # State tracking per server ID
        self.last_heartbeats: Dict[int, float] = {}
        self.pending_failure_detections: Dict[int, float] = {}  # server_id -> expected_detection_time
        self.detection_latencies: List[float] = []

    def reset(self) -> None:
        """Reset monitor state."""
        self.last_heartbeats.clear()
        self.pending_failure_detections.clear()
        self.detection_latencies.clear()

    def record_heartbeat(self, server: CloudServer, timestamp_sec: float) -> bool:
        """
        Record a successful heartbeat ping from a server.
        Returns True if heartbeat was accepted, False if server is failed or uncontactable.
        """
        if server.state == ServerState.FAILED:
            return False
        self.last_heartbeats[server.server_id] = timestamp_sec
        server.last_heartbeat_time = timestamp_sec
        return True

    def schedule_failure_detection(
        self,
        server: CloudServer,
        failure_time_sec: float
    ) -> float:
        """
        Register a server failure and compute the exact detection timestamp
        based on configured detection latency.
        """
        detection_time_sec = failure_time_sec + self.detection_delay_sec
        server.failure_timestamp = failure_time_sec
        server.detection_timestamp = detection_time_sec
        self.pending_failure_detections[server.server_id] = detection_time_sec
        return detection_time_sec

    def check_unannounced_failures(
        self,
        servers: List[CloudServer],
        current_time_sec: float
    ) -> List[Tuple[CloudServer, float]]:
        """
        Check for any servers whose heartbeats timed out without explicit crash announcement.
        Returns list of (server, detected_time).
        """
        detected: List[Tuple[CloudServer, float]] = []
        for server in servers:
            if server.state == ServerState.FAILED:
                continue
            last = self.last_heartbeats.get(server.server_id, 0.0)
            if current_time_sec - last > self.heartbeat_timeout_sec:
                detected.append((server, current_time_sec))
        return detected

    def confirm_detection(self, server: CloudServer, current_time_sec: float) -> float:
        """
        Mark failure as officially detected by the cluster monitor.
        Returns the recorded detection latency in seconds.
        """
        failure_time = server.failure_timestamp or current_time_sec
        latency = max(0.0, current_time_sec - failure_time)
        server.detection_timestamp = current_time_sec
        self.detection_latencies.append(latency)
        self.pending_failure_detections.pop(server.server_id, None)
        return latency

    @property
    def average_detection_latency_sec(self) -> float:
        """Calculate average latency between failure occurrence and detection."""
        if not self.detection_latencies:
            return self.detection_delay_sec
        return sum(self.detection_latencies) / len(self.detection_latencies)
