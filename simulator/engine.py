"""
Discrete-Event and Static Simulation Engine for Cloud Server Load Balancing.
"""

import copy
import csv
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from .models import CloudRequest, CloudServer
from .algorithms import BaseScheduler
from .metrics import calculate_static_metrics, calculate_dynamic_metrics


@dataclass
class SimulationResult:
    """Encapsulates the output of a single simulation experiment."""
    scheduler_name: str
    mode: str
    servers: List[CloudServer]
    requests: List[CloudRequest]
    metrics: Dict[str, Any]

    def get_assignments_data(self) -> List[Dict[str, Any]]:
        """Return list of assignment dictionaries."""
        return [r.to_dict() for r in self.requests]

    def save_assignments_csv(self, file_path: str) -> None:
        """Save request-to-server assignments to CSV."""
        data = self.get_assignments_data()
        if not data:
            return
        fieldnames = list(data[0].keys())
        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)


class SimulationEngine:
    """
    Simulation Engine orchestrating servers, requests, and scheduling algorithms.
    Supports both Static Workload Allocation and Dynamic Time-Aware Discrete-Event Simulation.
    """

    def __init__(self, servers: Optional[List[CloudServer]] = None):
        self.servers: List[CloudServer] = servers or [
            CloudServer(server_id=1, name="Server 1", capacity_weight=1.0),
            CloudServer(server_id=2, name="Server 2", capacity_weight=1.0),
            CloudServer(server_id=3, name="Server 3", capacity_weight=1.0),
        ]
        self._requests_template: List[CloudRequest] = []

    def set_servers(self, servers: List[CloudServer]) -> None:
        """Update or replace configured servers."""
        self.servers = servers

    def load_dataset_from_csv(self, csv_path: str) -> int:
        """Load and parse requests from a CSV file."""
        requests: List[CloudRequest] = []
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            first_row = True
            baseline_ts = 0.0

            for row in reader:
                req = CloudRequest.from_row(row, baseline_timestamp=None)
                if first_row:
                    baseline_ts = req.arrival_time_sec
                    first_row = False
                req.arrival_time_sec -= baseline_ts
                requests.append(req)

        self._requests_template = requests
        return len(self._requests_template)

    def load_dataset_from_requests(self, requests: List[CloudRequest]) -> None:
        """Load pre-parsed CloudRequest objects."""
        self._requests_template = requests

    def run(
        self,
        scheduler: BaseScheduler,
        mode: str = "dynamic"
    ) -> SimulationResult:
        """
        Execute a simulation run with the given scheduler.
        
        Args:
            scheduler: Schedular algorithm instance.
            mode: "static" (cumulative workload heuristic) or "dynamic" (discrete-event queue simulation).
        """
        if not self._requests_template:
            raise ValueError("No requests loaded. Call load_dataset_from_csv() first.")
        if not self.servers:
            raise ValueError("No servers configured.")

        # Deep copy to ensure fresh isolated state per run
        run_servers = [copy.deepcopy(s) for s in self.servers]
        for s in run_servers:
            s.reset()
        run_requests = [copy.deepcopy(r) for r in self._requests_template]
        scheduler.reset()

        if mode == "static":
            for req in run_requests:
                selected_server = scheduler.select_server(req, run_servers, current_time_sec=0.0)
                selected_server.execute_request_static(req)
            metrics = calculate_static_metrics(scheduler.name, run_servers)

        elif mode == "dynamic":
            # Ensure chronological order by arrival time
            run_requests.sort(key=lambda r: r.arrival_time_sec)
            for req in run_requests:
                selected_server = scheduler.select_server(
                    req,
                    run_servers,
                    current_time_sec=req.arrival_time_sec
                )
                selected_server.execute_request_dynamic(req)
            metrics = calculate_dynamic_metrics(scheduler.name, run_servers, run_requests)

        else:
            raise ValueError(f"Unknown simulation mode '{mode}'. Choose 'static' or 'dynamic'.")

        return SimulationResult(
            scheduler_name=scheduler.name,
            mode=mode,
            servers=run_servers,
            requests=run_requests,
            metrics=metrics
        )
