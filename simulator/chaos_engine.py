"""
Time-Aware Discrete-Event Simulation Engine for Cloud Chaos Lab.
Provides priority-queue event execution, interactive fault injection,
dynamic autoscaling, and comprehensive distributed systems telemetry.
"""

import copy
import heapq
import random
from typing import List, Dict, Any, Optional, Tuple, Set
import pandas as pd

from .models import (
    CloudRequest,
    CloudServer,
    ServerState,
    RecoveryPolicy,
    EventType,
    SimEvent,
)
from .algorithms import (
    BaseScheduler,
    RoundRobinScheduler,
    AdaptiveCapacityAwareScheduler,
    get_eligible_servers,
)
from .event_logger import EventLogger, EventSeverity
from .health_monitor import HealthMonitor
from .recovery_manager import RecoveryManager
from .autoscaler import AutoScaler


class ChaosSimulationEngine:
    """
    Stateful Discrete-Event Chaos Simulation Engine.
    Executes time-aware requests, failures, recoveries, and autoscaling.
    """

    def __init__(
        self,
        servers: Optional[List[CloudServer]] = None,
        scheduler: Optional[BaseScheduler] = None,
        recovery_policy: RecoveryPolicy = RecoveryPolicy.RESTART_FROM_BEGINNING,
        max_retries: int = 3,
        heartbeat_interval_sec: float = 2.0,
        failure_detection_delay_sec: float = 1.5,
        autoscale_enabled: bool = False,
        autoscale_cooldown_sec: float = 12.0
    ):
        # Cluster Nodes
        self.servers: List[CloudServer] = servers or [
            CloudServer(server_id=1, name="Server 1", capacity_weight=1.0),
            CloudServer(server_id=2, name="Server 2", capacity_weight=1.0),
            CloudServer(server_id=3, name="Server 3", capacity_weight=1.0),
        ]
        self.scheduler: BaseScheduler = scheduler or AdaptiveCapacityAwareScheduler()
        
        # Subsystems
        self.logger = EventLogger()
        self.health_monitor = HealthMonitor(
            heartbeat_interval_sec=heartbeat_interval_sec,
            detection_delay_sec=failure_detection_delay_sec
        )
        self.recovery_manager = RecoveryManager(
            default_policy=recovery_policy,
            max_retries=max_retries
        )
        self.autoscaler = AutoScaler(
            enabled=autoscale_enabled,
            cooldown_sec=autoscale_cooldown_sec
        )

        # Simulation Clock & Event Priority Queue
        self.current_time_sec: float = 0.0
        self._event_queue: List[SimEvent] = []
        self._event_counter: int = 0  # Deterministic sequence counter
        self._baseline_timestamp: float = 0.0

        # Request Tracking
        self.submitted_requests: List[CloudRequest] = []
        self.completed_requests: List[CloudRequest] = []
        self.failed_requests: List[CloudRequest] = []

        # Server active event mappings: server_id -> completion_event_seq_id
        self._active_completion_events: Dict[int, int] = {}

        # Telemetry samples over time for live plotting
        self.telemetry_history: List[Dict[str, Any]] = []

    def set_servers(self, servers: List[CloudServer]) -> None:
        """Update cluster servers."""
        self.servers = [copy.deepcopy(s) for s in servers]

    def set_scheduler(self, scheduler: BaseScheduler) -> None:
        """Update active load balancing algorithm."""
        self.scheduler = scheduler

    def load_requests(self, requests: List[CloudRequest]) -> None:
        """Load pre-parsed requests into the simulation template."""
        self.submitted_requests = [copy.deepcopy(r) for r in requests]

    def reset(self) -> None:
        """Reset simulation clock, queues, and all server states."""
        self.current_time_sec = 0.0
        self._event_queue.clear()
        self._event_counter = 0
        self._active_completion_events.clear()
        self.completed_requests.clear()
        self.failed_requests.clear()
        self.telemetry_history.clear()

        self.logger.clear()
        self.health_monitor.reset()
        self.recovery_manager.reset()
        self.autoscaler.reset()
        self.scheduler.reset()

        for s in self.servers:
            s.reset()

        # Enqueue initial periodic events (heartbeat & autoscaler)
        self._schedule_event(0.5, EventType.HEALTH_CHECK, priority=20)
        self._schedule_event(1.0, EventType.AUTOSCALE_EVALUATE, priority=25)

    def _schedule_event(
        self,
        timestamp: float,
        event_type: EventType,
        priority: int = 10,
        payload: Optional[Dict[str, Any]] = None
    ) -> int:
        """Enqueue a discrete event with deterministic tie-breaking."""
        self._event_counter += 1
        event = SimEvent(
            timestamp=timestamp,
            priority=priority,
            sequence_id=self._event_counter,
            event_type=event_type,
            payload=payload or {}
        )
        heapq.heappush(self._event_queue, event)
        return self._event_counter

    def initialize_workload(self, requests: List[CloudRequest]) -> None:
        """Initialize simulation with an incoming stream of requests."""
        self.reset()
        self.submitted_requests = [copy.deepcopy(r) for r in requests]
        
        # Sort by arrival time
        self.submitted_requests.sort(key=lambda r: r.arrival_time_sec)
        
        # Normalize arrival times so first request starts at t=0.0
        if self.submitted_requests:
            first_arr = self.submitted_requests[0].arrival_time_sec
            for req in self.submitted_requests:
                req.arrival_time_sec = max(0.0, req.arrival_time_sec - first_arr)
                req.first_arrival_sec = req.arrival_time_sec
                # Schedule arrival event
                self._schedule_event(
                    req.arrival_time_sec,
                    EventType.REQUEST_ARRIVAL,
                    priority=5,
                    payload={"request": req}
                )

        self.logger.info(
            0.0,
            "Engine",
            f"Initialized simulation with {len(self.submitted_requests)} requests across {len(self.servers)} servers."
        )
        self._record_telemetry_snapshot()

    # -------------------------------------------------------------------------
    # DISASTER & CHAOS INJECTION CONTROLS
    # -------------------------------------------------------------------------
    def inject_server_crash(self, server_id: int, timestamp_sec: Optional[float] = None) -> bool:
        """Instantly crash a server at the specified or current timestamp."""
        t = self.current_time_sec if timestamp_sec is None else timestamp_sec
        server = self.get_server_by_id(server_id)
        if not server:
            return False

        self._schedule_event(
            t,
            EventType.SERVER_FAILURE,
            priority=1,
            payload={"server_id": server_id}
        )
        return True

    def inject_server_recovery(self, server_id: int, timestamp_sec: Optional[float] = None) -> bool:
        """Initiate recovery for a crashed server."""
        t = self.current_time_sec if timestamp_sec is None else timestamp_sec
        server = self.get_server_by_id(server_id)
        if not server:
            return False

        if t > self.current_time_sec:
            # Future recovery initiation event
            self._schedule_event(
                t,
                EventType.SERVER_RECOVERY,
                priority=2,
                payload={"server_id": server_id}
            )
            return True

        if server.state != ServerState.FAILED:
            return False

        restoration_time = self.recovery_manager.initiate_server_recovery(server, t, self.logger)
        self._schedule_event(
            restoration_time,
            EventType.SERVER_RECOVERY,
            priority=2,
            payload={"server_id": server_id}
        )
        return True

    def inject_server_degradation(
        self,
        server_id: int,
        degradation_factor: float,
        timestamp_sec: Optional[float] = None
    ) -> bool:
        """Throttle a server's processing speed."""
        t = self.current_time_sec if timestamp_sec is None else timestamp_sec
        server = self.get_server_by_id(server_id)
        if not server:
            return False

        self._schedule_event(
            t,
            EventType.CAPACITY_CHANGE,
            priority=3,
            payload={"server_id": server_id, "factor": degradation_factor}
        )
        return True

    def inject_traffic_spike(
        self,
        count: int = 50,
        arrival_rate_rps: float = 20.0,
        duration_sec: float = 3.0,
        profile: str = "medium",
        seed: int = 42,
        timestamp_sec: Optional[float] = None
    ) -> List[CloudRequest]:
        """Inject an intentional synthetic traffic spike."""
        t_start = self.current_time_sec if timestamp_sec is None else timestamp_sec
        rng = random.Random(seed)
        
        # Profile processing times (ms)
        proc_ranges = {
            "light": (30.0, 150.0),
            "medium": (100.0, 400.0),
            "heavy": (350.0, 800.0),
        }
        low, high = proc_ranges.get(profile, (100.0, 400.0))

        spike_requests: List[CloudRequest] = []
        interval = duration_sec / max(1, count)

        for i in range(count):
            arr_t = t_start + (i * interval) + rng.uniform(0.0, interval * 0.5)
            p_time = rng.uniform(low, high)
            d_size = rng.uniform(1.0, 25.0)
            req = CloudRequest(
                request_id=f"SPIKE-{i + 1:04d}",
                arrival_time_str=EventLogger.format_sim_time(arr_t),
                arrival_time_sec=arr_t,
                request_type=f"Spike-{profile.capitalize()}",
                processing_time_ms=round(p_time, 1),
                data_size_mb=round(d_size, 1)
            )
            spike_requests.append(req)
            self.submitted_requests.append(req)
            self._schedule_event(
                arr_t,
                EventType.REQUEST_ARRIVAL,
                priority=5,
                payload={"request": req}
            )

        self.logger.warning(
            t_start,
            "TrafficGenerator",
            f"Injected TRAFFIC SPIKE: {count} {profile} requests over {duration_sec}s (Rate: {arrival_rate_rps} rps)."
        )
        return spike_requests

    def run_combined_disaster(self, timestamp_sec: Optional[float] = None) -> None:
        """
        Execute pre-packaged multi-event cascade:
        Traffic spike starts, Server 2 crashes, Server 3 degrades to 50%, Auto-scaling responds.
        """
        t = self.current_time_sec if timestamp_sec is None else timestamp_sec
        
        # 1. Traffic spike
        self.inject_traffic_spike(count=60, arrival_rate_rps=25.0, duration_sec=4.0, profile="heavy", seed=101, timestamp_sec=t)
        
        # 2. Crash Server 2 at t + 1.0s
        if len(self.servers) >= 2:
            self.inject_server_crash(self.servers[1].server_id, timestamp_sec=t + 1.0)
        
        # 3. Degrade Server 3 to 50% at t + 1.5s
        if len(self.servers) >= 3:
            self.inject_server_degradation(self.servers[2].server_id, 0.50, timestamp_sec=t + 1.5)

        self.logger.critical(
            t,
            "ChaosLab",
            "COMBINED DISASTER Initiated: Heavy Spike + Server 2 Crash + Server 3 CPU Degradation (50%)."
        )

    # -------------------------------------------------------------------------
    # DISCRETE-EVENT PROCESSING LOOP
    # -------------------------------------------------------------------------
    def has_active_work(self) -> bool:
        """Check if any requests, queues, or non-periodic events remain."""
        if len(self.completed_requests) + len(self.failed_requests) < len(self.submitted_requests):
            return True
        if any(s.active_request is not None or s.queue_length > 0 for s in self.servers):
            return True
        if self.recovery_manager.cluster_outage_buffer:
            return True
        for ev in self._event_queue:
            if ev.event_type not in (EventType.HEALTH_CHECK, EventType.AUTOSCALE_EVALUATE):
                return True
        return False

    def step(self) -> Optional[SimEvent]:
        """Execute exactly one discrete simulation event from the priority queue."""
        if not self._event_queue:
            return None

        # If only periodic events remain and all requests are finished, stop simulation cleanly
        if not self.has_active_work():
            self._event_queue.clear()
            return None

        event = heapq.heappop(self._event_queue)
        self.current_time_sec = event.timestamp

        # Dispatch event to its specialized handler
        if event.event_type == EventType.REQUEST_ARRIVAL:
            self._handle_request_arrival(event)
        elif event.event_type == EventType.REQUEST_START:
            self._handle_request_start(event)
        elif event.event_type == EventType.REQUEST_COMPLETION:
            self._handle_request_completion(event)
        elif event.event_type == EventType.SERVER_FAILURE:
            self._handle_server_failure(event)
        elif event.event_type == EventType.FAILURE_DETECTION:
            self._handle_failure_detection(event)
        elif event.event_type == EventType.SERVER_RECOVERY:
            self._handle_server_recovery(event)
        elif event.event_type == EventType.CAPACITY_CHANGE:
            self._handle_capacity_change(event)
        elif event.event_type == EventType.HEALTH_CHECK:
            self._handle_health_check(event)
        elif event.event_type == EventType.AUTOSCALE_EVALUATE:
            self._handle_autoscale_evaluate(event)

        self._record_telemetry_snapshot()
        return event

    def run_until(self, target_time_sec: float) -> int:
        """Process all events up to the target timestamp."""
        count = 0
        while self._event_queue and self._event_queue[0].timestamp <= target_time_sec:
            self.step()
            count += 1
        return count

    def run_all(self, max_events: int = 50000) -> int:
        """Run simulation to completion or until queue empty."""
        count = 0
        while self._event_queue and count < max_events:
            self.step()
            count += 1
        return count

    # -------------------------------------------------------------------------
    # INDIVIDUAL EVENT HANDLERS
    # -------------------------------------------------------------------------
    def _handle_request_arrival(self, event: SimEvent) -> None:
        req: CloudRequest = event.payload["request"]
        eligible = get_eligible_servers(self.servers)

        if not eligible:
            # Cluster outage: place in recovery buffer
            self.recovery_manager.cluster_outage_buffer.append(req)
            self.logger.critical(
                self.current_time_sec,
                "Router",
                f"Cluster Outage! No healthy servers available for {req.request_id}. Queued in recovery buffer."
            )
            return

        # Assign via active scheduler
        target_server = self.scheduler.select_server(req, self.servers, current_time_sec=self.current_time_sec)
        req.assigned_server = target_server.name
        
        # If server is idle, start immediately; otherwise append to queue
        if target_server.active_request is None and target_server.state != ServerState.FAILED:
            self._start_request_on_server(target_server, req)
        else:
            target_server.pending_queue.append(req)
            target_server.update_operational_state()

    def _start_request_on_server(self, server: CloudServer, req: CloudRequest) -> None:
        server.active_request = req
        req.start_time_sec = self.current_time_sec
        req.waiting_time_ms = max(0.0, (self.current_time_sec - req.first_arrival_sec) * 1000.0)

        # Processing duration based on effective capacity
        eff_cap = server.effective_capacity
        dur_sec = req.processing_time_ms / (1000.0 * eff_cap)
        finish_sec = self.current_time_sec + dur_sec

        server.active_task_start_sec = self.current_time_sec
        server.active_task_finish_sec = finish_sec
        server.busy_until_sec = max(server.busy_until_sec, finish_sec)
        req.actual_processing_time_ms = dur_sec * 1000.0
        server.update_operational_state()

        # Enqueue completion
        seq_id = self._schedule_event(
            finish_sec,
            EventType.REQUEST_COMPLETION,
            priority=8,
            payload={"server_id": server.server_id, "request_id": req.request_id}
        )
        self._active_completion_events[server.server_id] = seq_id

    def _handle_request_start(self, event: SimEvent) -> None:
        server_id = event.payload["server_id"]
        server = self.get_server_by_id(server_id)
        if not server or server.state == ServerState.FAILED or server.active_request is not None:
            return
        if server.pending_queue:
            next_req = server.pending_queue.pop(0)
            self._start_request_on_server(server, next_req)

    def _handle_request_completion(self, event: SimEvent) -> None:
        server_id = event.payload["server_id"]
        req_id = event.payload["request_id"]
        server = self.get_server_by_id(server_id)

        # Validity check: if server crashed or active request changed, cancel this event
        if not server or server.state == ServerState.FAILED:
            return
        if not server.active_request or server.active_request.request_id != req_id:
            return

        req = server.active_request
        req.completion_time_sec = self.current_time_sec
        req.turnaround_time_ms = max(0.0, (self.current_time_sec - req.first_arrival_sec) * 1000.0)

        # Update metrics & bookkeeping
        server.active_request = None
        server.active_task_start_sec = None
        server.active_task_finish_sec = None
        server.completed_requests.append(req)
        server.cumulative_workload_ms += req.processing_time_ms
        server.total_busy_time_sec += (req.actual_processing_time_ms / 1000.0)
        server.assigned_count += 1
        
        self.completed_requests.append(req)
        self.recovery_manager.finalized_request_ids.add(req.request_id)
        self._active_completion_events.pop(server.server_id, None)

        # Check if server was draining for auto-scale scale-in
        if getattr(server, "is_draining", False) and not server.pending_queue:
            self.servers = [s for s in self.servers if s.server_id != server.server_id]
            self.logger.info(
                self.current_time_sec,
                "AutoScaler",
                f"Scale-in complete: {server.name} safely drained and decommissioned."
            )
            return

        # Start next queued task if present
        if server.pending_queue:
            next_req = server.pending_queue.pop(0)
            self._start_request_on_server(server, next_req)
        else:
            server.update_operational_state()

    def _handle_server_failure(self, event: SimEvent) -> None:
        server_id = event.payload["server_id"]
        server = self.get_server_by_id(server_id)
        if not server or server.state == ServerState.FAILED:
            return

        server.state = ServerState.FAILED
        self._active_completion_events.pop(server_id, None)
        
        # Schedule failure detection with realistic delay
        detection_time = self.health_monitor.schedule_failure_detection(server, self.current_time_sec)
        self._schedule_event(
            detection_time,
            EventType.FAILURE_DETECTION,
            priority=1,
            payload={"server_id": server_id}
        )

        self.logger.critical(
            self.current_time_sec,
            server.name,
            f"DISASTER: {server.name} crashed! Heartbeat lost (Detection scheduled at t={detection_time:.2f}s)."
        )

    def _handle_failure_detection(self, event: SimEvent) -> None:
        server_id = event.payload["server_id"]
        server = self.get_server_by_id(server_id)
        if not server:
            return

        latency = self.health_monitor.confirm_detection(server, self.current_time_sec)
        self.logger.warning(
            self.current_time_sec,
            "HealthMonitor",
            f"Failure DETECTED for {server.name} (Detection Latency: {latency:.2f}s). Initiating task recovery..."
        )

        # Reassign tasks
        eligible = get_eligible_servers(self.servers)
        reassigned, perm_failed = self.recovery_manager.process_server_crash(
            failed_server=server,
            failure_time_sec=server.failure_timestamp or self.current_time_sec,
            detection_time_sec=self.current_time_sec,
            eligible_servers=eligible,
            scheduler=self.scheduler,
            logger=self.logger
        )

        for req in perm_failed:
            self.failed_requests.append(req)

        # Dispatch reassigned tasks to their newly assigned servers
        for req, target in reassigned:
            if target is not None:
                if target.active_request is None and target.state != ServerState.FAILED:
                    self._start_request_on_server(target, req)
                else:
                    target.pending_queue.append(req)
                    target.update_operational_state()

    def _handle_server_recovery(self, event: SimEvent) -> None:
        server_id = event.payload["server_id"]
        server = self.get_server_by_id(server_id)
        if not server:
            return

        if server.state == ServerState.FAILED:
            # Step 1: Initiate recovery phase with startup delay
            restoration_time = self.recovery_manager.initiate_server_recovery(
                server, self.current_time_sec, self.logger
            )
            self._schedule_event(
                restoration_time,
                EventType.SERVER_RECOVERY,
                priority=2,
                payload={"server_id": server_id}
            )
            return

        # Step 2: Server was RECOVERING; complete health checks and rejoin
        backlog_tasks = self.recovery_manager.complete_server_recovery(
            server,
            self.current_time_sec,
            self.logger
        )

        # If any tasks were in the outage buffer, route them
        for req in backlog_tasks:
            req.assigned_server = server.name
            if server.active_request is None:
                self._start_request_on_server(server, req)
            else:
                server.pending_queue.append(req)
        server.update_operational_state()

    def _handle_capacity_change(self, event: SimEvent) -> None:
        server_id = event.payload["server_id"]
        factor = event.payload["factor"]
        server = self.get_server_by_id(server_id)
        if not server:
            return

        old_factor = server.degradation_factor
        server.degradation_factor = factor
        server.update_operational_state()

        pct = int(factor * 100)
        self.logger.warning(
            self.current_time_sec,
            server.name,
            f"CPU Degradation applied to {server.name}: throttled to {pct}% capacity (Effective speed: {server.effective_capacity:.2f}x)."
        )

        # If request is actively executing, adjust its completion time
        if server.active_request and server.active_task_finish_sec is not None:
            remaining_old_sec = max(0.001, server.active_task_finish_sec - self.current_time_sec)
            scale = old_factor / max(0.05, factor)
            new_remaining_sec = remaining_old_sec * scale
            new_finish_sec = self.current_time_sec + new_remaining_sec
            server.active_task_finish_sec = new_finish_sec
            server.busy_until_sec = max(server.busy_until_sec, new_finish_sec)

            # Re-schedule completion
            self._schedule_event(
                new_finish_sec,
                EventType.REQUEST_COMPLETION,
                priority=8,
                payload={"server_id": server.server_id, "request_id": server.active_request.request_id}
            )

    def _handle_health_check(self, event: SimEvent) -> None:
        # Periodic heartbeat
        for s in self.servers:
            self.health_monitor.record_heartbeat(s, self.current_time_sec)
        
        # Schedule next heartbeat only if workload is still active
        if self.has_active_work():
            self._schedule_event(
                self.current_time_sec + self.health_monitor.heartbeat_interval_sec,
                EventType.HEALTH_CHECK,
                priority=20
            )

    def _handle_autoscale_evaluate(self, event: SimEvent) -> None:
        decision = self.autoscaler.evaluate(self.current_time_sec, self.servers, self.logger)
        if decision and decision.action == "SCALE_OUT":
            # Provision new server
            new_node = self.autoscaler.provision_new_server(self.servers, self.current_time_sec)
            self.servers.append(new_node)
            # Schedule startup completion
            ready_time = self.current_time_sec + self.autoscaler.provisioning_delay_sec
            self._schedule_event(
                ready_time,
                EventType.SERVER_RECOVERY,
                priority=4,
                payload={"server_id": new_node.server_id}
            )
            self.logger.info(
                self.current_time_sec,
                "AutoScaler",
                f"Provisioning {new_node.name} (Ready in {self.autoscaler.provisioning_delay_sec}s)."
            )

        # Schedule next evaluation only if workload is still active
        if self.has_active_work():
            self._schedule_event(
                self.current_time_sec + self.autoscaler.evaluation_window_sec,
                EventType.AUTOSCALE_EVALUATE,
                priority=25
            )

    # -------------------------------------------------------------------------
    # HELPERS & TELEMETRY
    # -------------------------------------------------------------------------
    def get_server_by_id(self, server_id: int) -> Optional[CloudServer]:
        """Lookup server by unique ID."""
        for s in self.servers:
            if s.server_id == server_id:
                return s
        return None

    def _record_telemetry_snapshot(self) -> None:
        """Sample operational telemetry for time-series charts."""
        healthy_servers = [s for s in self.servers if s.state != ServerState.FAILED]
        total_q = sum(s.queue_length for s in self.servers)
        active_tasks = sum(1 for s in self.servers if s.active_request is not None)
        avg_cpu = sum(s.cpu_utilization_pct for s in healthy_servers) / len(healthy_servers) if healthy_servers else 0.0

        snapshot = {
            "Sim_Time_sec": round(self.current_time_sec, 2),
            "Active_Servers": len(healthy_servers),
            "Total_Servers": len(self.servers),
            "Cluster_Avg_CPU_Pct": round(avg_cpu, 1),
            "Total_Queue_Length": total_q,
            "Active_Tasks_Running": active_tasks,
            "Completed_Count": len(self.completed_requests),
            "Failed_Count": len(self.failed_requests),
            "Retried_Count": self.recovery_manager.total_retry_events,
            "Outage_Buffer_Count": len(self.recovery_manager.cluster_outage_buffer),
        }
        # Add per-server CPU & Queue
        for s in self.servers:
            snapshot[f"{s.name}_CPU"] = round(s.cpu_utilization_pct, 1)
            snapshot[f"{s.name}_Queue"] = s.queue_length

        self.telemetry_history.append(snapshot)

    def get_telemetry_dataframe(self) -> pd.DataFrame:
        """Return historical telemetry as pandas DataFrame."""
        if not self.telemetry_history:
            return pd.DataFrame()
        return pd.DataFrame(self.telemetry_history)

    def compute_comprehensive_metrics(self) -> Dict[str, Any]:
        """Calculate complete scientific metrics across all subsystems."""
        completed = self.completed_requests
        failed = self.failed_requests
        total_sub = len(self.submitted_requests)

        waits = [r.waiting_time_ms for r in completed if r.waiting_time_ms is not None]
        turnarounds = [r.turnaround_time_ms for r in completed if r.turnaround_time_ms is not None]

        waits_sorted = sorted(waits)
        turns_sorted = sorted(turnarounds)
        n = len(turns_sorted)

        p50 = turns_sorted[int(n * 0.50)] if n else 0.0
        p95 = turns_sorted[min(n - 1, int(n * 0.95))] if n else 0.0
        p99 = turns_sorted[min(n - 1, int(n * 0.99))] if n else 0.0

        avg_wait = sum(waits) / len(waits) if waits else 0.0
        avg_turnaround = sum(turnarounds) / len(turnarounds) if turnarounds else 0.0

        sim_makespan = max(0.001, self.current_time_sec)
        throughput = len(completed) / sim_makespan if sim_makespan > 0 else 0.0

        # Energy & Cost Models
        total_energy_kwh = sum(s.calculate_energy_kwh(sim_makespan) for s in self.servers)
        # Cloud billing estimate: $0.05 per active server-hour modeled
        hourly_rate_per_server = 0.05
        active_hours = (sim_makespan / 3600.0) * len(self.servers)
        estimated_cost_usd = active_hours * hourly_rate_per_server

        # Workload balance
        loads = [s.cumulative_workload_ms for s in self.servers]
        max_load = max(loads) if loads else 0.0
        min_load = min(loads) if loads else 0.0
        imbalance = max_load - min_load

        # Verification of request conservation
        in_flight = sum(1 for s in self.servers if s.active_request is not None)
        queued = sum(s.queue_length for s in self.servers) + len(self.recovery_manager.cluster_outage_buffer)
        accounted = len(completed) + len(failed) + in_flight + queued
        conservation_passed = (total_sub == accounted) or (total_sub == 0)

        return {
            "Algorithm": self.scheduler.name,
            "Simulation_Makespan_sec": round(sim_makespan, 2),
            "Total_Submitted_Requests": total_sub,
            "Completed_Requests": len(completed),
            "Permanently_Failed_Requests": len(failed),
            "Retried_Request_Events": self.recovery_manager.total_retry_events,
            "Recovered_Requests_Count": self.recovery_manager.total_recovered_count,
            "Total_Lost_Work_ms": round(self.recovery_manager.total_lost_work_ms, 2),
            "Average_Waiting_Time_ms": round(avg_wait, 2),
            "Average_Response_Time_ms": round(avg_turnaround, 2),
            "Median_Response_Time_ms": round(p50, 2),
            "P95_Response_Time_ms": round(p95, 2),
            "P99_Response_Time_ms": round(p99, 2),
            "Throughput_RPS": round(throughput, 2),
            "Load_Imbalance_ms": round(imbalance, 2),
            "Failure_Detection_Latency_sec": round(self.health_monitor.average_detection_latency_sec, 2),
            "Estimated_Energy_kWh": round(total_energy_kwh, 6),
            "Estimated_Cost_USD": round(estimated_cost_usd, 6),
            "Request_Conservation_Passed": conservation_passed,
            "Server_Metrics": {
                s.name: {
                    "State": s.state.value,
                    "Capacity_Multiplier": round(s.effective_capacity, 2),
                    "CPU_Util_Pct": round(s.cpu_utilization_pct, 1),
                    "Queue_Length": s.queue_length,
                    "Assigned_Count": s.assigned_count,
                    "Completed_Count": len(s.completed_requests),
                    "Retried_Count": s.retried_requests_count,
                    "Failed_Count": s.failed_requests_count,
                    "Lost_Work_ms": round(s.total_lost_work_ms, 2),
                    "Total_Busy_sec": round(s.total_busy_time_sec, 2),
                    "Cumulative_Load_ms": round(s.cumulative_workload_ms, 2),
                }
                for s in self.servers
            }
        }
