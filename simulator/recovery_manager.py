"""
Failure Recovery and Task Reassignment Manager for Cloud Chaos Lab.
Implements retry policies, prevents duplicate completions, tracks lost computational
work, and manages cluster outage buffers.
"""

from typing import List, Dict, Optional, Tuple, Set
from .models import CloudRequest, CloudServer, ServerState, RecoveryPolicy
from .algorithms import BaseScheduler, get_eligible_servers
from .event_logger import EventLogger, EventSeverity


class RecoveryManager:
    """
    Coordinates fault recovery, task reassignment, and service restoration
    across a distributed cloud cluster.
    """

    def __init__(
        self,
        default_policy: RecoveryPolicy = RecoveryPolicy.RESTART_FROM_BEGINNING,
        max_retries: int = 3,
        startup_delay_sec: float = 3.5
    ):
        self.recovery_policy = default_policy
        self.max_retries = max_retries
        self.startup_delay_sec = startup_delay_sec

        # Cluster outage buffer for requests waiting for at least one healthy server
        self.cluster_outage_buffer: List[CloudRequest] = []

        # Deduplication & safety tracking
        self.finalized_request_ids: Set[str] = set()

        # Cumulative metrics
        self.total_recovered_count: int = 0
        self.total_permanently_failed_count: int = 0
        self.total_retry_events: int = 0
        self.total_lost_work_ms: float = 0.0
        self.recovery_durations_sec: List[float] = []

    def reset(self) -> None:
        """Reset manager state."""
        self.cluster_outage_buffer.clear()
        self.finalized_request_ids.clear()
        self.total_recovered_count = 0
        self.total_permanently_failed_count = 0
        self.total_retry_events = 0
        self.total_lost_work_ms = 0.0
        self.recovery_durations_sec.clear()

    def process_server_crash(
        self,
        failed_server: CloudServer,
        failure_time_sec: float,
        detection_time_sec: float,
        eligible_servers: List[CloudServer],
        scheduler: BaseScheduler,
        logger: Optional[EventLogger] = None
    ) -> Tuple[List[Tuple[CloudRequest, Optional[CloudServer]]], List[CloudRequest]]:
        """
        Execute fault containment and task reassignment for a crashed server.
        
        Returns:
            Tuple of:
              - reassigned_requests: List of (request, target_server_or_None)
              - permanently_failed_requests: List of requests that exceeded max retries
        """
        reassigned: List[Tuple[CloudRequest, Optional[CloudServer]]] = []
        permanently_failed: List[CloudRequest] = []

        # 1. Harvest active in-flight request
        active_req = failed_server.active_request
        failed_server.active_request = None
        failed_server.active_task_finish_sec = None

        tasks_to_recover: List[Tuple[CloudRequest, bool]] = []  # (request, is_in_flight)

        if active_req and active_req.request_id not in self.finalized_request_ids:
            tasks_to_recover.append((active_req, True))

        # 2. Harvest all pending queued requests
        while failed_server.pending_queue:
            q_req = failed_server.pending_queue.pop(0)
            if q_req.request_id not in self.finalized_request_ids:
                tasks_to_recover.append((q_req, False))

        # 3. Process each task through retry and recovery policy
        for req, was_in_flight in tasks_to_recover:
            req.retry_count += 1
            self.total_retry_events += 1
            failed_server.retried_requests_count += 1

            if was_in_flight:
                # Calculate lost computational work
                if self.recovery_policy == RecoveryPolicy.RESTART_FROM_BEGINNING:
                    start_t = req.start_time_sec if req.start_time_sec is not None else failure_time_sec
                    elapsed_sec = max(0.0, failure_time_sec - start_t)
                    eff_cap = failed_server.effective_capacity
                    lost_ms = elapsed_sec * 1000.0 * eff_cap
                    lost_ms = min(lost_ms, req.processing_time_ms)
                    req.lost_work_ms += lost_ms
                    self.total_lost_work_ms += lost_ms
                    failed_server.total_lost_work_ms += lost_ms
                else:
                    # Checkpoint recovery: keep partial progress
                    start_t = req.start_time_sec if req.start_time_sec is not None else failure_time_sec
                    elapsed_sec = max(0.0, failure_time_sec - start_t)
                    eff_cap = failed_server.effective_capacity
                    done_ms = elapsed_sec * 1000.0 * eff_cap
                    req.processing_time_ms = max(5.0, req.processing_time_ms - done_ms)

            # Check retry exhaustion
            if req.retry_count > self.max_retries:
                req.is_failed = True
                req.failure_reason = f"Exceeded maximum retry limit of {self.max_retries}"
                permanently_failed.append(req)
                self.total_permanently_failed_count += 1
                failed_server.failed_requests_count += 1
                self.finalized_request_ids.add(req.request_id)
                if logger:
                    logger.critical(
                        detection_time_sec,
                        failed_server.name,
                        f"Request {req.request_id} permanently failed (exceeded {self.max_retries} retries)."
                    )
                continue

            # Task is eligible for recovery & reassignment
            req.is_recovered = True
            req.reassigned_from.append(failed_server.name)
            self.total_recovered_count += 1

            # Check if any healthy servers exist
            active_eligible = [s for s in eligible_servers if s.server_id != failed_server.server_id]
            if active_eligible:
                target_server = scheduler.select_server(req, active_eligible, current_time_sec=detection_time_sec)
                req.assigned_server = target_server.name
                reassigned.append((req, target_server))
                if logger:
                    logger.warning(
                        detection_time_sec,
                        "RecoveryManager",
                        f"Recovered request {req.request_id} reassigned to {target_server.name} (Retry #{req.retry_count})."
                    )
            else:
                # Total cluster outage: preserve request in outage buffer
                self.cluster_outage_buffer.append(req)
                reassigned.append((req, None))
                if logger:
                    logger.critical(
                        detection_time_sec,
                        "ClusterManager",
                        f"All servers failed! Request {req.request_id} placed in cluster outage buffer."
                    )

        return reassigned, permanently_failed

    def initiate_server_recovery(
        self,
        server: CloudServer,
        trigger_time_sec: float,
        logger: Optional[EventLogger] = None
    ) -> float:
        """
        Transition a failed server into RECOVERING state with a startup delay.
        Returns the expected completion timestamp for service restoration.
        """
        server.state = ServerState.RECOVERING
        restoration_time_sec = trigger_time_sec + self.startup_delay_sec
        server.recovery_timestamp = restoration_time_sec
        if logger:
            logger.info(
                trigger_time_sec,
                server.name,
                f"{server.name} initiating recovery protocol (Startup delay: {self.startup_delay_sec}s)."
            )
        return restoration_time_sec

    def complete_server_recovery(
        self,
        server: CloudServer,
        restoration_time_sec: float,
        logger: Optional[EventLogger] = None
    ) -> List[CloudRequest]:
        """
        Complete health checks, restore server to healthy state,
        and assign any queued cluster-outage backlog requests to it.
        """
        server.state = ServerState.HEALTHY
        server.update_operational_state()
        server.failure_timestamp = None
        server.detection_timestamp = None

        if server.failure_timestamp is not None:
            dur = max(0.0, restoration_time_sec - server.failure_timestamp)
            self.recovery_durations_sec.append(dur)

        if logger:
            logger.success(
                restoration_time_sec,
                server.name,
                f"{server.name} passed health checks and rejoined the active scheduling cluster."
            )

        # Drain cluster outage buffer if any tasks were waiting
        restored_tasks: List[CloudRequest] = []
        if self.cluster_outage_buffer:
            restored_tasks = list(self.cluster_outage_buffer)
            self.cluster_outage_buffer.clear()
            if logger:
                logger.info(
                    restoration_time_sec,
                    "ClusterManager",
                    f"Dispatched {len(restored_tasks)} backlog requests from outage buffer to restored {server.name}."
                )

        return restored_tasks

    @property
    def average_recovery_duration_sec(self) -> float:
        """Calculate average time from failure to full restoration."""
        if not self.recovery_durations_sec:
            return self.startup_delay_sec
        return sum(self.recovery_durations_sec) / len(self.recovery_durations_sec)
