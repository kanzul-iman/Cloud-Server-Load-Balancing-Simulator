"""
Load Balancer Module for Cloud Server Load Balancing Simulator.
Implements Round Robin and Least Loaded scheduling algorithms with deterministic tie-breaking.
"""

from typing import List, Dict, Tuple, Optional
import pandas as pd

DEFAULT_SERVERS: List[str] = ["Server 1", "Server 2", "Server 3"]


def generate_server_names(num_servers: int = 3) -> List[str]:
    """
    Generate standard logical server identifiers.
    
    Args:
        num_servers: Number of logical servers to instantiate (must be >= 1).
        
    Returns:
        List[str]: Formatted server names (e.g., ["Server 1", "Server 2", "Server 3"]).
        
    Raises:
        ValueError: If num_servers is less than 1.
    """
    if num_servers < 1:
        raise ValueError(
            f"Invalid number of servers: {num_servers}. At least 1 server is required."
        )
    return [f"Server {i}" for i in range(1, num_servers + 1)]


def round_robin_scheduler(
    data: pd.DataFrame,
    servers: Optional[List[str]] = None
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Assign requests sequentially to servers in cyclic order (modulo N).
    
    This is a static, workload-unaware scheduling algorithm that guarantees
    equal request counts per server, but may cause workload imbalance when
    request processing times vary.
    
    Args:
        data: Validated DataFrame of incoming requests.
        servers: Optional list of server names (defaults to Server 1, 2, 3).
        
    Returns:
        Tuple[pd.DataFrame, Dict[str, int]]:
            - assignments_df: Complete request assignments table.
            - server_loads: Accumulated total processing time (ms) per server.
            
    Raises:
        ValueError: If servers list is empty or data is empty.
    """
    if servers is None:
        servers = list(DEFAULT_SERVERS)
    if not servers:
        raise ValueError("Server pool cannot be empty.")
    if data is None:
        raise ValueError("Input request DataFrame cannot be None.")

    empty_cols = [
        "Request_ID", "Arrival_Time", "Request_Type",
        "Processing_Time_ms", "Data_Size_MB", "Server", "Server_Cumulative_Load_ms"
    ]
    if data.empty:
        return pd.DataFrame(columns=empty_cols), {server: 0 for server in servers}

    server_loads: Dict[str, int] = {server: 0 for server in servers}
    assignments: List[Dict] = []
    num_servers = len(servers)

    for i, (_, request) in enumerate(data.iterrows()):
        server = servers[i % num_servers]
        proc_time = int(request["Processing_Time_ms"])
        server_loads[server] += proc_time

        assignments.append({
            "Request_ID": request["Request_ID"],
            "Arrival_Time": request["Arrival_Time"],
            "Request_Type": request["Request_Type"],
            "Processing_Time_ms": proc_time,
            "Data_Size_MB": float(request["Data_Size_MB"]),
            "Server": server,
            "Server_Cumulative_Load_ms": server_loads[server],
        })

    assignments_df = pd.DataFrame(assignments)
    return assignments_df, server_loads


def least_loaded_scheduler(
    data: pd.DataFrame,
    servers: Optional[List[str]] = None
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Assign each incoming request to the server with the smallest accumulated workload.
    
    Tie-Breaking Rule:
        Ties are broken deterministically using server order (e.g. Server 1 before Server 2).
        Because Python's min() preserves the first encountered element upon ties,
        iterating over the declared server list enforces this deterministic behavior.
        
    Note on Simulation Fidelity:
        This is a simplified, sequential, workload-aware scheduling simulation.
        It models a load balancer maintaining cumulative assigned workloads to
        balance aggregate server processing time.
        
    Args:
        data: Validated DataFrame of incoming requests.
        servers: Optional list of server names (defaults to Server 1, 2, 3).
        
    Returns:
        Tuple[pd.DataFrame, Dict[str, int]]:
            - assignments_df: Complete request assignments table.
            - server_loads: Accumulated total processing time (ms) per server.
            
    Raises:
        ValueError: If servers list is empty or data is None.
    """
    if servers is None:
        servers = list(DEFAULT_SERVERS)
    if not servers:
        raise ValueError("Server pool cannot be empty.")
    if data is None:
        raise ValueError("Input request DataFrame cannot be None.")

    empty_cols = [
        "Request_ID", "Arrival_Time", "Request_Type",
        "Processing_Time_ms", "Data_Size_MB", "Server", "Server_Cumulative_Load_ms"
    ]
    if data.empty:
        return pd.DataFrame(columns=empty_cols), {server: 0 for server in servers}

    server_loads: Dict[str, int] = {server: 0 for server in servers}
    assignments: List[Dict] = []

    for _, request in data.iterrows():
        # Select server with lowest cumulative load; deterministic tie-breaking via server order
        selected_server = min(servers, key=lambda s: server_loads[s])
        proc_time = int(request["Processing_Time_ms"])
        server_loads[selected_server] += proc_time

        assignments.append({
            "Request_ID": request["Request_ID"],
            "Arrival_Time": request["Arrival_Time"],
            "Request_Type": request["Request_Type"],
            "Processing_Time_ms": proc_time,
            "Data_Size_MB": float(request["Data_Size_MB"]),
            "Server": selected_server,
            "Server_Cumulative_Load_ms": server_loads[selected_server],
        })

    assignments_df = pd.DataFrame(assignments)
    return assignments_df, server_loads
