"""
Data models representing Cloud Requests, Cloud Servers, and Discrete Simulation Events.
Fully backward-compatible with original simulator models while supporting advanced
Chaos Engineering, Failure Recovery, and Adaptive Load Balancing.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


class ServerState(str, Enum):
    """Lifecycle and operational states of a simulated Cloud Server."""
    IDLE = "IDLE"
    HEALTHY = "HEALTHY"
    BUSY = "BUSY"
    OVERLOADED = "OVERLOADED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"


class RecoveryPolicy(str, Enum):
    """Failure recovery handling policy for in-flight requests."""
    RESTART_FROM_BEGINNING = "RESTART_FROM_BEGINNING"
    CHECKPOINT = "CHECKPOINT"


class EventType(str, Enum):
    """Discrete Event types processed by the Chaos Simulation Engine."""
    REQUEST_ARRIVAL = "REQUEST_ARRIVAL"
    REQUEST_START = "REQUEST_START"
    REQUEST_COMPLETION = "REQUEST_COMPLETION"
    SERVER_FAILURE = "SERVER_FAILURE"
    FAILURE_DETECTION = "FAILURE_DETECTION"
    SERVER_RECOVERY = "SERVER_RECOVERY"
    HEALTH_CHECK = "HEALTH_CHECK"
    TRAFFIC_SPIKE = "TRAFFIC_SPIKE"
    CAPACITY_CHANGE = "CAPACITY_CHANGE"
    SCALE_OUT = "SCALE_OUT"
    SCALE_IN = "SCALE_IN"
    RETRY_REQUEST = "RETRY_REQUEST"
    AUTOSCALE_EVALUATE = "AUTOSCALE_EVALUATE"


@dataclass(order=True)
class SimEvent:
    """
    Priority-ordered discrete simulation event.
    Ordered by: timestamp -> priority -> sequence_id
    """
    timestamp: float
    priority: int = 10  # Lower number = higher priority
    sequence_id: int = 0
    event_type: EventType = field(compare=False, default=EventType.REQUEST_ARRIVAL)
    payload: Dict[str, Any] = field(compare=False, default_factory=dict)


@dataclass
class CloudRequest:
    """Represents an incoming computational request in a cloud environment."""
    request_id: str
    arrival_time_str: str
    arrival_time_sec: float
    request_type: str
    processing_time_ms: float
    data_size_mb: float

    # Runtime simulation tracking attributes
    assigned_server: Optional[str] = None
    start_time_sec: Optional[float] = None
    completion_time_sec: Optional[float] = None
    waiting_time_ms: Optional[float] = None
    turnaround_time_ms: Optional[float] = None
    actual_processing_time_ms: Optional[float] = None

    # Chaos & Recovery lifecycle tracking
    retry_count: int = 0
    is_recovered: bool = False
    is_failed: bool = False
    failure_reason: Optional[str] = None
    first_arrival_sec: Optional[float] = None
    reassigned_from: List[str] = field(default_factory=list)
    lost_work_ms: float = 0.0

    def __post_init__(self):
        if self.first_arrival_sec is None:
            self.first_arrival_sec = self.arrival_time_sec

    @classmethod
    def from_row(cls, row: Dict[str, Any], baseline_timestamp: Optional[float] = None) -> "CloudRequest":
        """Instantiate a CloudRequest from a CSV/DataFrame dictionary row."""
        req_id = str(row["Request_ID"]).strip()
        arr_str = str(row["Arrival_Time"]).strip()
        req_type = str(row["Request_Type"]).strip()
        proc_time = float(row["Processing_Time_ms"])
        data_size = float(row["Data_Size_MB"])

        # Parse arrival time into seconds
        try:
            dt = datetime.strptime(arr_str, "%Y-%m-%d %H:%M:%S")
            arr_sec = dt.timestamp()
        except Exception:
            arr_sec = 0.0

        if baseline_timestamp is not None:
            arr_sec -= baseline_timestamp

        return cls(
            request_id=req_id,
            arrival_time_str=arr_str,
            arrival_time_sec=arr_sec,
            request_type=req_type,
            processing_time_ms=proc_time,
            data_size_mb=data_size,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert request record to dictionary for CSV/DataFrame export."""
        return {
            "Request_ID": self.request_id,
            "Arrival_Time": self.arrival_time_str,
            "Arrival_Time_sec": round(self.arrival_time_sec, 3),
            "Request_Type": self.request_type,
            "Server": self.assigned_server or "Unassigned",
            "Processing_Time_ms": self.processing_time_ms,
            "Actual_Processing_Time_ms": round(
                self.actual_processing_time_ms if self.actual_processing_time_ms is not None else self.processing_time_ms,
                2
            ),
            "Waiting_Time_ms": round(self.waiting_time_ms if self.waiting_time_ms is not None else 0.0, 2),
            "Turnaround_Time_ms": round(
                self.turnaround_time_ms if self.turnaround_time_ms is not None else self.processing_time_ms,
                2
            ),
            "Data_Size_MB": self.data_size_mb,
            "Retry_Count": self.retry_count,
            "Is_Recovered": self.is_recovered,
            "Is_Failed": self.is_failed,
            "Failure_Reason": self.failure_reason or "None",
            "Lost_Work_ms": round(self.lost_work_ms, 2),
        }


@dataclass
class CloudServer:
    """Represents a physical or virtual compute node in a cloud datacenter."""
    server_id: int
    name: str
    capacity_weight: float = 1.0  # Processing speed multiplier (e.g. 1.0 = baseline, 2.0 = 2x faster)
    
    # State tracking
    cumulative_workload_ms: float = 0.0
    assigned_count: int = 0
    busy_until_sec: float = 0.0
    total_busy_time_sec: float = 0.0

    # Chaos Lab operational attributes
    state: ServerState = ServerState.IDLE
    degradation_factor: float = 1.0  # 1.0 = normal, 0.5 = 50% capacity, etc.
    ram_mb: float = 16384.0  # 16 GB modeled RAM
    ram_used_mb: float = 0.0
    
    # Task queues & active processing
    pending_queue: List[CloudRequest] = field(default_factory=list)
    active_request: Optional[CloudRequest] = None
    active_task_start_sec: Optional[float] = None
    active_task_finish_sec: Optional[float] = None
    
    # Historical counts & metrics
    completed_requests: List[CloudRequest] = field(default_factory=list)
    failed_requests_count: int = 0
    retried_requests_count: int = 0
    total_lost_work_ms: float = 0.0
    
    # Energy model parameters (Watts)
    idle_power_watts: float = 120.0
    busy_power_watts: float = 300.0
    
    # Fault and recovery bookkeeping
    last_heartbeat_time: float = 0.0
    failure_timestamp: Optional[float] = None
    detection_timestamp: Optional[float] = None
    recovery_timestamp: Optional[float] = None
    is_draining: bool = False  # For safe auto-scale scale-in

    @property
    def effective_capacity(self) -> float:
        """Effective processing speed multiplier accounting for degradation."""
        if self.state in (ServerState.FAILED, ServerState.RECOVERING):
            return 0.0001  # Near zero to avoid division by zero
        return max(0.05, self.capacity_weight * self.degradation_factor)

    @property
    def queue_length(self) -> int:
        """Number of requests pending in the server's local queue."""
        return len(self.pending_queue)

    @property
    def cpu_utilization_pct(self) -> float:
        """Current instantaneous CPU utilization."""
        if self.state == ServerState.FAILED:
            return 0.0
        if self.active_request is not None:
            # Under degradation or high queue, compute utilization
            base_util = 75.0 if self.queue_length == 0 else 95.0
            return min(100.0, base_util / self.degradation_factor)
        return 0.0

    @property
    def ram_utilization_pct(self) -> float:
        """Modeled RAM utilization based on active and queued tasks."""
        if self.state == ServerState.FAILED:
            return 0.0
        task_ram = (1 if self.active_request else 0) * 512.0
        queue_ram = self.queue_length * 256.0
        total_used = min(self.ram_mb, 1024.0 + task_ram + queue_ram)
        return (total_used / self.ram_mb) * 100.0

    def reset(self) -> None:
        """Reset the server state to idle before starting a simulation run."""
        self.cumulative_workload_ms = 0.0
        self.assigned_count = 0
        self.busy_until_sec = 0.0
        self.total_busy_time_sec = 0.0
        self.state = ServerState.IDLE
        self.degradation_factor = 1.0
        self.ram_used_mb = 0.0
        self.pending_queue.clear()
        self.active_request = None
        self.active_task_start_sec = None
        self.active_task_finish_sec = None
        self.completed_requests.clear()
        self.failed_requests_count = 0
        self.retried_requests_count = 0
        self.total_lost_work_ms = 0.0
        self.last_heartbeat_time = 0.0
        self.failure_timestamp = None
        self.detection_timestamp = None
        self.recovery_timestamp = None
        self.is_draining = False

    def update_operational_state(self) -> None:
        """
        Transition between HEALTHY, BUSY, OVERLOADED, DEGRADED, IDLE
        based on active tasks, queue length, and degradation settings.
        Preserves FAILED and RECOVERING states until explicitly transitioned.
        """
        if self.state in (ServerState.FAILED, ServerState.RECOVERING):
            return

        if self.degradation_factor < 0.99:
            self.state = ServerState.DEGRADED
        elif self.active_request is None and self.queue_length == 0:
            self.state = ServerState.IDLE
        elif self.queue_length > 8 or self.cpu_utilization_pct >= 90.0:
            self.state = ServerState.OVERLOADED
        elif self.active_request is not None or self.queue_length > 0:
            self.state = ServerState.BUSY
        else:
            self.state = ServerState.HEALTHY

    def get_remaining_workload_ms_at(self, current_time_sec: float) -> float:
        """
        Calculate remaining active work (ms) at a specific point in time.
        Models instantaneous queue backlog in dynamic scheduling.
        """
        remaining_sec = max(0.0, self.busy_until_sec - current_time_sec)
        return remaining_sec * 1000.0

    def calculate_energy_kwh(self, total_sim_time_sec: float) -> float:
        """
        Calculate total energy consumption (kWh) over the simulation run.
        Uses standard cloud datacenter power model:
        Energy = [P_idle * T_idle + P_busy * T_busy] / (3600 * 1000)
        """
        if total_sim_time_sec <= 0:
            return 0.0
        busy_sec = min(total_sim_time_sec, self.total_busy_time_sec)
        idle_sec = max(0.0, total_sim_time_sec - busy_sec)
        joules = (self.idle_power_watts * idle_sec) + (self.busy_power_watts * busy_sec)
        return joules / (3600.0 * 1000.0)

    def execute_request_dynamic(self, request: CloudRequest) -> None:
        """
        Execute request in time-aware simulation mode.
        Computes queuing delay, actual execution duration (factoring capacity weight),
        and completion timestamp.
        """
        arr_sec = request.arrival_time_sec
        start_sec = max(arr_sec, self.busy_until_sec)
        waiting_sec = max(0.0, start_sec - arr_sec)
        
        # Duration adjusted by effective capacity
        eff_cap = self.effective_capacity
        duration_sec = (request.processing_time_ms / (1000.0 * eff_cap))
        finish_sec = start_sec + duration_sec
        turnaround_sec = finish_sec - arr_sec

        # Update server state
        self.busy_until_sec = finish_sec
        self.total_busy_time_sec += duration_sec
        self.cumulative_workload_ms += request.processing_time_ms
        self.assigned_count += 1

        # Annotate request
        request.assigned_server = self.name
        request.start_time_sec = start_sec
        request.completion_time_sec = finish_sec
        request.waiting_time_ms = waiting_sec * 1000.0
        request.actual_processing_time_ms = duration_sec * 1000.0
        request.turnaround_time_ms = turnaround_sec * 1000.0
        self.update_operational_state()

    def execute_request_static(self, request: CloudRequest) -> None:
        """
        Execute request in static cumulative workload mode (matching baseline logic).
        """
        self.cumulative_workload_ms += request.processing_time_ms
        self.assigned_count += 1
        request.assigned_server = self.name
