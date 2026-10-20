"""
Metrics evaluation for Cloud Server Load Balancing.
Provides comprehensive calculations for both static heuristics and dynamic simulations.
"""

import math
from typing import List, Dict, Any
from .models import CloudRequest, CloudServer


def calculate_static_metrics(scheduler_name: str, servers: List[CloudServer]) -> Dict[str, Any]:
    """
    Computes static workload distribution metrics matching the project's original baseline.
    """
    loads = [s.cumulative_workload_ms for s in servers]
    total_load = sum(loads)
    max_load = max(loads) if loads else 0.0
    min_load = min(loads) if loads else 0.0
    imbalance = max_load - min_load

    # Calculate standard deviation of load across servers
    mean_load = total_load / len(servers) if servers else 0.0
    variance = sum((l - mean_load) ** 2 for l in loads) / len(servers) if servers else 0.0
    std_dev = math.sqrt(variance)

    server_loads_dict = {s.name: s.cumulative_workload_ms for s in servers}
    server_counts_dict = {s.name: s.assigned_count for s in servers}

    return {
        "Algorithm": scheduler_name,
        "Mode": "Static Cumulative",
        "Total_Workload_ms": round(total_load, 2),
        "Maximum_Server_Load_ms": round(max_load, 2),
        "Minimum_Server_Load_ms": round(min_load, 2),
        "Load_Imbalance_ms": round(imbalance, 2),
        "Load_Std_Dev_ms": round(std_dev, 2),
        "Estimated_Makespan_ms": round(max_load, 2),
        "Server_Loads": server_loads_dict,
        "Server_Counts": server_counts_dict,
    }


def calculate_dynamic_metrics(
    scheduler_name: str,
    servers: List[CloudServer],
    requests: List[CloudRequest]
) -> Dict[str, Any]:
    """
    Computes realistic distributed system metrics from a time-aware discrete-event run.
    """
    if not requests:
        return {}

    waiting_times = [r.waiting_time_ms for r in requests if r.waiting_time_ms is not None]
    turnarounds = [r.turnaround_time_ms for r in requests if r.turnaround_time_ms is not None]
    
    first_arrival = min(r.arrival_time_sec for r in requests)
    last_completion = max(r.completion_time_sec for r in requests if r.completion_time_sec is not None)
    
    total_sim_time_sec = max(0.001, last_completion - first_arrival)
    makespan_ms = total_sim_time_sec * 1000.0

    # Percentiles
    sorted_turnaround = sorted(turnarounds)
    n = len(sorted_turnaround)
    p50 = sorted_turnaround[int(n * 0.50)] if n else 0.0
    p95 = sorted_turnaround[min(n - 1, int(n * 0.95))] if n else 0.0
    p99 = sorted_turnaround[min(n - 1, int(n * 0.99))] if n else 0.0

    avg_wait = sum(waiting_times) / len(waiting_times) if waiting_times else 0.0
    avg_turnaround = sum(turnarounds) / len(turnarounds) if turnarounds else 0.0

    # Server Busy Times and Utilization
    total_busy_sec = sum(s.total_busy_time_sec for s in servers)
    total_available_capacity_sec = total_sim_time_sec * len(servers)
    avg_utilization_pct = (total_busy_sec / total_available_capacity_sec * 100.0) if total_available_capacity_sec > 0 else 0.0

    server_busy_pct = {
        s.name: round((s.total_busy_time_sec / total_sim_time_sec * 100.0), 2)
        for s in servers
    }

    throughput_rps = len(requests) / total_sim_time_sec if total_sim_time_sec > 0 else 0.0

    loads = [s.cumulative_workload_ms for s in servers]
    max_load = max(loads) if loads else 0.0
    min_load = min(loads) if loads else 0.0

    return {
        "Algorithm": scheduler_name,
        "Mode": "Dynamic Discrete-Event",
        "Total_Requests": len(requests),
        "Simulation_Makespan_sec": round(total_sim_time_sec, 2),
        "Avg_Waiting_Time_ms": round(avg_wait, 2),
        "Avg_Response_Time_ms": round(avg_turnaround, 2),
        "Median_Response_Time_ms": round(p50, 2),
        "P95_Response_Time_ms": round(p95, 2),
        "P99_Response_Time_ms": round(p99, 2),
        "Overall_Utilization_Pct": round(avg_utilization_pct, 2),
        "Throughput_RPS": round(throughput_rps, 2),
        "Load_Imbalance_ms": round(max_load - min_load, 2),
        "Server_Utilization_Pct": server_busy_pct,
        "Server_Counts": {s.name: s.assigned_count for s in servers},
    }
