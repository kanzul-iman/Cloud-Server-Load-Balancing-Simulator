"""
Horizontal Auto-Scaling Controller for Cloud Chaos Lab.
Monitors cluster load, executes threshold-based scale-out/scale-in policies,
enforces cooldown periods, and provides explainable audit trails.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from .models import CloudServer, ServerState
from .event_logger import EventLogger, EventSeverity


@dataclass
class ScalingDecision:
    """Audit record explaining an auto-scaling evaluation."""
    timestamp_sec: float
    action: str  # "SCALE_OUT", "SCALE_IN", "NOOP"
    avg_utilization_pct: float
    active_server_count: int
    trigger_reason: str
    target_server_name: Optional[str] = None
    target_server_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Sim_Time_sec": round(self.timestamp_sec, 2),
            "Action": self.action,
            "Avg_Utilization_Pct": round(self.avg_utilization_pct, 1),
            "Active_Servers": self.active_server_count,
            "Reason": self.trigger_reason,
            "Target_Server": self.target_server_name or "N/A"
        }


class AutoScaler:
    """
    Elastic horizontal cluster auto-scaling controller.
    Dynamically adjusts pool capacity based on cluster resource pressure.
    """

    def __init__(
        self,
        enabled: bool = False,
        scale_out_threshold_pct: float = 80.0,
        scale_in_threshold_pct: float = 25.0,
        min_servers: int = 2,
        max_servers: int = 8,
        evaluation_window_sec: float = 5.0,
        cooldown_sec: float = 12.0,
        provisioning_delay_sec: float = 3.0
    ):
        self.enabled = enabled
        self.scale_out_threshold_pct = scale_out_threshold_pct
        self.scale_in_threshold_pct = scale_in_threshold_pct
        self.min_servers = min_servers
        self.max_servers = max_servers
        self.evaluation_window_sec = evaluation_window_sec
        self.cooldown_sec = cooldown_sec
        self.provisioning_delay_sec = provisioning_delay_sec

        # Internal state
        self.last_scaling_timestamp_sec: float = -999.0
        self.decision_history: List[ScalingDecision] = []
        self._next_server_seq_id: int = 100

    def reset(self) -> None:
        """Reset auto-scaler state."""
        self.last_scaling_timestamp_sec = -999.0
        self.decision_history.clear()

    def evaluate(
        self,
        current_time_sec: float,
        servers: List[CloudServer],
        logger: Optional[EventLogger] = None
    ) -> Optional[ScalingDecision]:
        """
        Evaluate current cluster utilization and decide whether to scale out,
        scale in, or hold current capacity.
        """
        if not self.enabled:
            return None

        # Filter to active healthy servers
        healthy_servers = [
            s for s in servers
            if s.state not in (ServerState.FAILED, ServerState.RECOVERING)
            and not getattr(s, "is_draining", False)
        ]
        active_count = len(healthy_servers)

        if active_count == 0:
            return None

        # Compute average CPU utilization across healthy nodes
        total_util = sum(s.cpu_utilization_pct for s in healthy_servers)
        avg_util = total_util / active_count

        time_since_last = current_time_sec - self.last_scaling_timestamp_sec
        in_cooldown = time_since_last < self.cooldown_sec

        # Rule 1: Scale Out condition
        if avg_util >= self.scale_out_threshold_pct:
            if active_count >= self.max_servers:
                reason = f"Avg CPU {avg_util:.1f}% >= {self.scale_out_threshold_pct}% but reached maximum cluster limit ({self.max_servers} servers)."
                decision = ScalingDecision(current_time_sec, "NOOP", avg_util, active_count, reason)
                self.decision_history.append(decision)
                return decision

            if in_cooldown:
                reason = f"Avg CPU {avg_util:.1f}% >= {self.scale_out_threshold_pct}% but in cooldown ({time_since_last:.1f}s / {self.cooldown_sec}s)."
                decision = ScalingDecision(current_time_sec, "NOOP", avg_util, active_count, reason)
                self.decision_history.append(decision)
                return decision

            # Trigger Scale Out
            self.last_scaling_timestamp_sec = current_time_sec
            reason = (
                f"Sustained cluster overload (Avg CPU {avg_util:.1f}% >= {self.scale_out_threshold_pct}%). "
                f"Provisioning new server node."
            )
            decision = ScalingDecision(
                current_time_sec,
                "SCALE_OUT",
                avg_util,
                active_count + 1,
                reason,
                target_server_name=f"Server {len(servers) + 1} (Auto-Scaled)"
            )
            self.decision_history.append(decision)
            if logger:
                logger.warning(
                    current_time_sec,
                    "AutoScaler",
                    f"SCALE-OUT Triggered: {reason} (+1 node)"
                )
            return decision

        # Rule 2: Scale In condition
        if avg_util <= self.scale_in_threshold_pct:
            if active_count <= self.min_servers:
                reason = f"Avg CPU {avg_util:.1f}% <= {self.scale_in_threshold_pct}% but at minimum cluster limit ({self.min_servers} servers)."
                decision = ScalingDecision(current_time_sec, "NOOP", avg_util, active_count, reason)
                self.decision_history.append(decision)
                return decision

            if in_cooldown:
                reason = f"Avg CPU {avg_util:.1f}% <= {self.scale_in_threshold_pct}% but in cooldown ({time_since_last:.1f}s / {self.cooldown_sec}s)."
                decision = ScalingDecision(current_time_sec, "NOOP", avg_util, active_count, reason)
                self.decision_history.append(decision)
                return decision

            # Find best candidate to scale in (lowest queue and idle if possible)
            idle_candidates = [s for s in healthy_servers if s.queue_length == 0 and s.active_request is None]
            target = idle_candidates[-1] if idle_candidates else min(healthy_servers, key=lambda s: s.queue_length)

            self.last_scaling_timestamp_sec = current_time_sec
            reason = (
                f"Cluster underutilized (Avg CPU {avg_util:.1f}% <= {self.scale_in_threshold_pct}%). "
                f"Initiating graceful drain of {target.name}."
            )
            decision = ScalingDecision(
                current_time_sec,
                "SCALE_IN",
                avg_util,
                active_count - 1,
                reason,
                target_server_name=target.name,
                target_server_id=target.server_id
            )
            self.decision_history.append(decision)
            if logger:
                logger.info(
                    current_time_sec,
                    "AutoScaler",
                    f"SCALE-IN Triggered: {reason} (-1 node: {target.name})"
                )
            return decision

        return None

    def provision_new_server(
        self,
        current_servers: List[CloudServer],
        current_time_sec: float
    ) -> CloudServer:
        """Create and configure a newly scaled-out server node."""
        new_id = max(s.server_id for s in current_servers) + 1 if current_servers else 1
        new_server = CloudServer(
            server_id=new_id,
            name=f"Server {new_id} (Auto)",
            capacity_weight=1.0,
            state=ServerState.RECOVERING  # Undergoing provisioning
        )
        new_server.provisioned_at = current_time_sec
        return new_server
