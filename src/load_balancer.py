"""
Load Balancer Module for Cloud Server Load Balancing Simulator.
Implements Round Robin and Least Loaded scheduling algorithms with deterministic tie-breaking.
"""

from typing import List, Dict, Tuple, Optional, Any, Union
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


def validate_request_inputs(
    request_id: str,
    request_type: str,
    processing_time_ms: Any,
    data_size_mb: Any,
    existing_ids: Optional[Union[set, List[str]]] = None,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validate manual request creation parameters for dynamic injection.
    
    Args:
        request_id: Unique string identifier for the request.
        request_type: Category of request (e.g. 'API Read', 'Database Query').
        processing_time_ms: Burst duration in milliseconds (must be positive > 0).
        data_size_mb: Payload size in megabytes (must be non-negative >= 0).
        existing_ids: Optional collection of already assigned Request IDs to prevent duplicates.
        
    Returns:
        Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
            - is_valid: True if all fields pass validation.
            - error_message: Descriptive explanation if invalid, else None.
            - cleaned_data: Normalized dictionary of request fields if valid, else None.
    """
    if not request_id or not str(request_id).strip():
        return False, "Request ID cannot be empty or whitespace.", None

    clean_id = str(request_id).strip()
    if existing_ids is not None and clean_id in existing_ids:
        return False, f"Duplicate Request ID: '{clean_id}' already exists in the simulation.", None

    if not request_type or not str(request_type).strip():
        return False, "Request Type must be selected.", None
    clean_type = str(request_type).strip()

    # Validate processing time (cannot be negative or zero)
    try:
        proc_time = float(processing_time_ms)
        if proc_time <= 0:
            return False, f"Invalid Processing Time ({processing_time_ms} ms): Must be a positive number greater than 0.", None
        proc_time_int = int(proc_time) if proc_time.is_integer() else int(round(proc_time))
    except (ValueError, TypeError):
        return False, f"Invalid Processing Time '{processing_time_ms}': Must be a valid numeric value.", None

    # Validate data size (cannot be negative)
    try:
        data_size = float(data_size_mb)
        if data_size < 0:
            return False, f"Invalid Data Size ({data_size_mb} MB): Cannot be negative.", None
    except (ValueError, TypeError):
        return False, f"Invalid Data Size '{data_size_mb}': Must be a valid numeric value.", None

    cleaned_data = {
        "Request_ID": clean_id,
        "Request_Type": clean_type,
        "Processing_Time_ms": proc_time_int,
        "Data_Size_MB": round(data_size, 2),
    }
    return True, None, cleaned_data


def assign_single_request(
    request: Dict[str, Any],
    servers: Optional[List[str]] = None,
    current_loads: Optional[Dict[str, int]] = None,
    strategy: str = "Least Loaded",
    current_index: int = 0,
    arrival_time: Optional[str] = None,
) -> Tuple[str, Dict[str, Any], Dict[str, int]]:
    """
    Assign a single new request to a server according to the selected scheduling strategy.
    
    When strategy is Least Loaded:
        Selects the server with the lowest current workload (deterministic tie-breaking via server order).
    When strategy is Round Robin:
        Selects the server based on current sequential cyclic index (modulo N).
        
    Args:
        request: Validated request dictionary (contains Request_ID, Request_Type,
                 Processing_Time_ms, Data_Size_MB).
        servers: List of available server names (defaults to DEFAULT_SERVERS).
        current_loads: Current cumulative workload mapping {server_name: load_ms}.
        strategy: "Least Loaded" or "Round Robin".
        current_index: Sequential index for Round Robin dispatching.
        arrival_time: Optional ISO/formatted timestamp string for arrival.
        
    Returns:
        Tuple:
            - selected_server (str): Server chosen by the algorithm.
            - assignment_record (dict): Single-row dict matching assignments DataFrame schema.
            - updated_loads (dict): Workloads dictionary after adding the request's processing time.
            
    Raises:
        ValueError: If servers list is empty or strategy is unknown.
    """
    if servers is None:
        servers = list(DEFAULT_SERVERS)
    if not servers:
        raise ValueError("Server pool cannot be empty.")

    if current_loads is None:
        current_loads = {s: 0 for s in servers}

    updated_loads = dict(current_loads)
    for s in servers:
        if s not in updated_loads:
            updated_loads[s] = 0

    strategy_clean = strategy.strip().lower()
    proc_time = int(request["Processing_Time_ms"])

    if "least" in strategy_clean:
        # Assign to server with the lowest current workload
        selected_server = min(servers, key=lambda s: updated_loads[s])
    elif "round" in strategy_clean:
        # Assign according to cyclic Round Robin sequence
        selected_server = servers[current_index % len(servers)]
    else:
        raise ValueError(
            f"Unsupported scheduling strategy: '{strategy}'. Must be 'Least Loaded' or 'Round Robin'."
        )

    # Add new request's processing time to selected server's workload
    updated_loads[selected_server] += proc_time

    timestamp = arrival_time or pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    assignment_record = {
        "Request_ID": str(request["Request_ID"]),
        "Arrival_Time": timestamp,
        "Request_Type": str(request["Request_Type"]),
        "Processing_Time_ms": proc_time,
        "Data_Size_MB": float(request["Data_Size_MB"]),
        "Server": selected_server,
        "Server_Cumulative_Load_ms": updated_loads[selected_server],
    }

    return selected_server, assignment_record, updated_loads

