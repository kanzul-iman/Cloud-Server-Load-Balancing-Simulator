"""
Performance Metrics and Verification Module for Cloud Server Load Balancing Simulator.
Computes workload metrics, comparative benchmarks, correctness checks, and CSV exports.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd


def calculate_algorithm_metrics(
    algorithm_name: str,
    assignments_df: pd.DataFrame,
    server_loads: Dict[str, int]
) -> Dict[str, Any]:
    """
    Compute core performance metrics for a load-balancing simulation run.
    
    Args:
        algorithm_name: Name of the scheduling algorithm (e.g. "Round Robin").
        assignments_df: Assignments DataFrame with 'Server' and 'Processing_Time_ms'.
        server_loads: Dictionary mapping server names to total accumulated workload (ms).
        
    Returns:
        Dict[str, Any]: Dictionary containing all performance metrics.
    """
    loads = list(server_loads.values())
    total_workload = sum(loads)
    max_workload = max(loads) if loads else 0
    min_workload = min(loads) if loads else 0
    load_imbalance = max_workload - min_workload
    estimated_makespan = max_workload  # Static upper bound under concurrent batch execution

    # Request counts per server
    if "Server" in assignments_df.columns and not assignments_df.empty:
        request_counts = assignments_df["Server"].value_counts().to_dict()
    else:
        request_counts = {}
    for server in server_loads:
        request_counts.setdefault(server, 0)

    # Request duration statistics
    if "Processing_Time_ms" in assignments_df.columns and not assignments_df.empty:
        proc_times = assignments_df["Processing_Time_ms"]
        mean_proc = round(float(proc_times.mean()), 2)
        median_proc = round(float(proc_times.median()), 2)
        max_proc = int(proc_times.max())
        min_proc = int(proc_times.min())
    else:
        mean_proc = 0.0
        median_proc = 0.0
        max_proc = 0
        min_proc = 0

    return {
        "Algorithm": algorithm_name,
        "Total_Workload_ms": total_workload,
        "Maximum_Server_Load_ms": max_workload,
        "Minimum_Server_Load_ms": min_workload,
        "Load_Imbalance_ms": load_imbalance,
        "Estimated_Makespan_ms": estimated_makespan,
        "Server_Request_Counts": request_counts,
        "Server_Loads": dict(server_loads),
        "Mean_Processing_Time_ms": mean_proc,
        "Median_Processing_Time_ms": median_proc,
        "Max_Processing_Time_ms": max_proc,
        "Min_Processing_Time_ms": min_proc,
    }


def calculate_load_imbalance_reduction(
    baseline_imbalance: float,
    target_imbalance: float
) -> Optional[float]:
    """
    Calculate the percentage reduction in load imbalance relative to baseline.
    Only computes percentage when baseline imbalance is strictly greater than zero.
    
    Args:
        baseline_imbalance: Imbalance of baseline algorithm (e.g. Round Robin).
        target_imbalance: Imbalance of optimized algorithm (e.g. Least Loaded).
        
    Returns:
        Optional[float]: Percentage reduction (e.g. 90.24), or None if baseline <= 0.
    """
    if baseline_imbalance <= 0:
        return None
    reduction = ((baseline_imbalance - target_imbalance) / baseline_imbalance) * 100.0
    return round(reduction, 2)


def verify_simulation_correctness(
    original_df: pd.DataFrame,
    assignments_df: pd.DataFrame,
    server_loads: Dict[str, int]
) -> Dict[str, Any]:
    """
    Formally verify simulation correctness constraints:
      1. Every input request is assigned exactly once.
      2. No request is lost or duplicated.
      3. Total assigned processing time equals dataset's total processing time.
      4. Server workloads match their assigned request durations.
      
    Args:
        original_df: The source input dataset.
        assignments_df: The resulting assignment table.
        server_loads: The recorded accumulated workload dictionary.
        
    Returns:
        Dict[str, Any]: Verification status and diagnostic details.
    """
    orig_count = len(original_df)
    assigned_count = len(assignments_df)
    unique_assigned_count = assignments_df["Request_ID"].nunique()

    # Constraint 1 & 2: No loss, no duplication
    count_matches = (orig_count == assigned_count == unique_assigned_count)
    ids_match = (set(original_df["Request_ID"]) == set(assignments_df["Request_ID"]))

    # Constraint 3: Conservation of total processing time
    orig_total_ms = int(original_df["Processing_Time_ms"].sum())
    assigned_total_ms = int(assignments_df["Processing_Time_ms"].sum())
    server_loads_total_ms = sum(server_loads.values())
    workload_conserved = (orig_total_ms == assigned_total_ms == server_loads_total_ms)

    # Constraint 4: Server workloads match their respective assigned requests
    computed_server_totals = assignments_df.groupby("Server")["Processing_Time_ms"].sum().to_dict()
    server_workloads_match = True
    workload_mismatches = {}
    for server, load in server_loads.items():
        computed_load = computed_server_totals.get(server, 0)
        if load != computed_load:
            server_workloads_match = False
            workload_mismatches[server] = {"recorded": load, "computed": computed_load}

    all_passed = (
        count_matches and ids_match and workload_conserved and server_workloads_match
    )

    return {
        "all_passed": all_passed,
        "count_matches": count_matches,
        "ids_match": ids_match,
        "workload_conserved": workload_conserved,
        "server_workloads_match": server_workloads_match,
        "total_requests": orig_count,
        "total_workload_ms": orig_total_ms,
        "mismatches": workload_mismatches,
    }


def build_performance_comparison_dataframe(
    rr_metrics: Dict[str, Any],
    ll_metrics: Dict[str, Any]
) -> pd.DataFrame:
    """
    Assemble standard performance comparison summary DataFrame.
    """
    rows = [
        {
            "Algorithm": rr_metrics["Algorithm"],
            "Total_Workload_ms": rr_metrics["Total_Workload_ms"],
            "Maximum_Server_Load_ms": rr_metrics["Maximum_Server_Load_ms"],
            "Minimum_Server_Load_ms": rr_metrics["Minimum_Server_Load_ms"],
            "Load_Imbalance_ms": rr_metrics["Load_Imbalance_ms"],
            "Estimated_Makespan_ms": rr_metrics["Estimated_Makespan_ms"],
        },
        {
            "Algorithm": ll_metrics["Algorithm"],
            "Total_Workload_ms": ll_metrics["Total_Workload_ms"],
            "Maximum_Server_Load_ms": ll_metrics["Maximum_Server_Load_ms"],
            "Minimum_Server_Load_ms": ll_metrics["Minimum_Server_Load_ms"],
            "Load_Imbalance_ms": ll_metrics["Load_Imbalance_ms"],
            "Estimated_Makespan_ms": ll_metrics["Estimated_Makespan_ms"],
        },
    ]
    return pd.DataFrame(rows)


def build_server_workload_dataframe(
    rr_metrics: Dict[str, Any],
    ll_metrics: Dict[str, Any]
) -> pd.DataFrame:
    """
    Assemble side-by-side server breakdown DataFrame.
    """
    servers = sorted(list(rr_metrics["Server_Loads"].keys()))
    rows = []
    for s in servers:
        rows.append({
            "Server": s,
            "Round_Robin_Requests": rr_metrics["Server_Request_Counts"].get(s, 0),
            "Round_Robin_Load_ms": rr_metrics["Server_Loads"].get(s, 0),
            "Least_Loaded_Requests": ll_metrics["Server_Request_Counts"].get(s, 0),
            "Least_Loaded_Load_ms": ll_metrics["Server_Loads"].get(s, 0),
        })
    return pd.DataFrame(rows)


def export_simulation_reports(
    outputs_dir: Path,
    rr_assignments: pd.DataFrame,
    ll_assignments: pd.DataFrame,
    comparison_df: pd.DataFrame,
    server_workload_df: pd.DataFrame
) -> Dict[str, Path]:
    """
    Export all simulation reports and assignment mapping CSVs to outputs directory.
    Does not overwrite or modify the original dataset.
    
    Args:
        outputs_dir: Destination directory for CSV outputs.
        rr_assignments: Round Robin request assignments.
        ll_assignments: Least Loaded request assignments.
        comparison_df: Performance comparison summary DataFrame.
        server_workload_df: Server workload comparison DataFrame.
        
    Returns:
        Dict[str, Path]: Dictionary mapping report name to saved file path.
    """
    outputs_dir = Path(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "round_robin_assignments": outputs_dir / "round_robin_assignments.csv",
        "least_loaded_assignments": outputs_dir / "least_loaded_assignments.csv",
        "performance_comparison": outputs_dir / "performance_comparison.csv",
        "server_workload_comparison": outputs_dir / "server_workload_comparison.csv",
    }

    rr_assignments.to_csv(paths["round_robin_assignments"], index=False)
    ll_assignments.to_csv(paths["least_loaded_assignments"], index=False)
    comparison_df.to_csv(paths["performance_comparison"], index=False)
    server_workload_df.to_csv(paths["server_workload_comparison"], index=False)

    return paths
