"""
Main Cloud Chaos Lab Page Controller.
Orchestrates virtual clusters, discrete-event simulation controls, fault injection,
live event telemetry, and scientific algorithm comparisons.
"""

from typing import List, Dict, Any, Optional
import copy
import pandas as pd
import streamlit as st

from simulator.models import (
    CloudRequest,
    CloudServer,
    ServerState,
    RecoveryPolicy
)
from simulator.algorithms import (
    BaseScheduler,
    RoundRobinScheduler,
    LeastLoadedScheduler,
    AdaptiveCapacityAwareScheduler,
)
from simulator.chaos_engine import ChaosSimulationEngine
from .cluster_monitor import render_cluster_monitor
from .chaos_controls import render_chaos_controls
from .event_timeline import render_event_timeline
from .performance_charts import render_performance_charts
from .export_center import render_export_center


def get_or_create_engine(
    num_servers: int = 3,
    algorithm_choice: str = "Adaptive Capacity-Aware (ACALB)",
    autoscale_enabled: bool = False
) -> ChaosSimulationEngine:
    """Retrieve or instantiate stateful simulation engine in st.session_state."""
    if "chaos_engine" not in st.session_state:
        # Create initial servers
        servers = [
            CloudServer(server_id=i + 1, name=f"Server {i + 1}", capacity_weight=1.0)
            for i in range(num_servers)
        ]
        
        # Instantiate algorithm
        if "Adaptive" in algorithm_choice:
            scheduler = AdaptiveCapacityAwareScheduler()
        elif "Least Loaded" in algorithm_choice:
            scheduler = LeastLoadedScheduler()
        else:
            scheduler = RoundRobinScheduler()

        engine = ChaosSimulationEngine(
            servers=servers,
            scheduler=scheduler,
            autoscale_enabled=autoscale_enabled
        )
        st.session_state.chaos_engine = engine
        st.session_state.chaos_server_count = num_servers
        st.session_state.chaos_algorithm = algorithm_choice
    else:
        engine = st.session_state.chaos_engine
        
        # Update server count if changed
        if st.session_state.get("chaos_server_count") != num_servers:
            servers = [
                CloudServer(server_id=i + 1, name=f"Server {i + 1}", capacity_weight=1.0)
                for i in range(num_servers)
            ]
            engine.set_servers(servers)
            st.session_state.chaos_server_count = num_servers

        # Update algorithm if changed
        if st.session_state.get("chaos_algorithm") != algorithm_choice:
            if "Adaptive" in algorithm_choice:
                engine.set_scheduler(AdaptiveCapacityAwareScheduler())
            elif "Least Loaded" in algorithm_choice:
                engine.set_scheduler(LeastLoadedScheduler())
            else:
                engine.set_scheduler(RoundRobinScheduler())
            st.session_state.chaos_algorithm = algorithm_choice

    return engine


def convert_df_to_requests(df: pd.DataFrame, limit: Optional[int] = None) -> List[CloudRequest]:
    """Convert pandas DataFrame to list of CloudRequest objects."""
    subset = df.head(limit) if limit else df
    requests: List[CloudRequest] = []
    first_row = True
    baseline_ts = 0.0

    for _, row in subset.iterrows():
        req = CloudRequest.from_row(row.to_dict(), baseline_timestamp=None)
        if first_row:
            baseline_ts = req.arrival_time_sec
            first_row = False
        req.arrival_time_sec -= baseline_ts
        req.first_arrival_sec = req.arrival_time_sec
        requests.append(req)

    return requests


def render_algorithm_comparison_section(
    raw_requests: List[CloudRequest],
    num_servers: int
) -> None:
    """Run an isolated, deterministic side-by-side benchmark of RR vs LL vs ACALB."""
    st.markdown("### 🔬 Scientific Algorithm Benchmark (Stress Test Comparison)")
    st.caption("Evaluates Round Robin vs. Least Loaded vs. ACALB under identical workload traces and disaster scenarios.")

    run_comp = st.button("🧪 Run Comparative Experiment", type="secondary", use_container_width=False)
    
    if run_comp or "comparison_results" in st.session_state:
        if run_comp:
            with st.spinner("Executing comparative experiments across all 3 algorithms..."):
                algorithms = [
                    ("Round Robin", RoundRobinScheduler()),
                    ("Least Loaded", LeastLoadedScheduler()),
                    ("Adaptive Capacity-Aware (ACALB)", AdaptiveCapacityAwareScheduler()),
                ]
                comp_rows = []

                for algo_name, sched in algorithms:
                    # Fresh isolated cluster
                    test_servers = [
                        CloudServer(server_id=i + 1, name=f"Server {i + 1}", capacity_weight=1.0)
                        for i in range(num_servers)
                    ]
                    test_engine = ChaosSimulationEngine(
                        servers=test_servers,
                        scheduler=sched,
                        autoscale_enabled=False
                    )
                    test_engine.initialize_workload(raw_requests[:250])  # Benchmark on 250 requests
                    
                    # Apply identical fault: Server 2 crashes at t=2.0s
                    if len(test_servers) >= 2:
                        test_engine.inject_server_crash(2, timestamp_sec=2.0)

                    test_engine.run_all()
                    m = test_engine.compute_comprehensive_metrics()

                    comp_rows.append({
                        "Algorithm": algo_name,
                        "Makespan (s)": m["Simulation_Makespan_sec"],
                        "Throughput (RPS)": m["Throughput_RPS"],
                        "Avg Waiting (ms)": m["Average_Waiting_Time_ms"],
                        "Avg Response (ms)": m["Average_Response_Time_ms"],
                        "P95 Latency (ms)": m["P95_Response_Time_ms"],
                        "Load Imbalance (ms)": m["Load_Imbalance_ms"],
                        "Retried Requests": m["Retried_Request_Events"],
                        "Lost Work (ms)": m["Total_Lost_Work_ms"],
                        "Conservation Passed": "✔ YES" if m["Request_Conservation_Passed"] else "❌ NO"
                    })

                st.session_state.comparison_results = pd.DataFrame(comp_rows)

        df_comp = st.session_state.comparison_results
        st.dataframe(df_comp, use_container_width=True)

        st.markdown(
            """
            <div style="background: rgba(30, 41, 59, 0.7); border-left: 4px solid #38BDF8; border-radius: 0 8px 8px 0; padding: 0.8rem 1.1rem; font-size: 0.88rem; margin-top: 0.8rem;">
                <strong>Scientific Findings:</strong><br>
                1. <strong>Fault Resilience:</strong> When Server 2 crashes, ACALB actively recalculates expected completion time across remaining healthy nodes, preventing task piling onto slow or overwhelmed servers.<br>
                2. <strong>Load Balance vs Response Time:</strong> Least Loaded strictly balances cumulative workload sums, but ACALB accounts for both active execution time and queue waiting delay, achieving competitive P95 latency.
            </div>
            """,
            unsafe_allow_html=True
        )


def render_chaos_lab_page(df_dataset: pd.DataFrame) -> None:
    """Render the full Cloud Chaos Lab interactive page."""
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, #090D16 0%, #1E1B4B 50%, #1E293B 100%);
            border: 1px solid rgba(99, 102, 241, 0.35);
            border-radius: 14px;
            padding: 1.4rem 1.8rem;
            margin-bottom: 1.4rem;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.4);
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.8rem;">
                <div>
                    <h1 style="color: #F8FAFC; margin: 0; font-size: 1.85rem; font-weight: 800; letter-spacing: -0.5px;">
                        ⚡ Cloud Chaos Lab: Failure Recovery & Adaptive Load Balancing
                    </h1>
                    <div style="color: #93C5FD; font-size: 0.92rem; margin-top: 0.3rem;">
                        Distributed Systems Semester Project • Discrete-Event Priority Queue Simulation Engine
                    </div>
                </div>
                <div>
                    <span style="
                        background: rgba(99, 102, 241, 0.25);
                        color: #C7D2FE;
                        border: 1px solid rgba(165, 180, 252, 0.4);
                        padding: 0.35rem 0.85rem;
                        border-radius: 20px;
                        font-size: 0.82rem;
                        font-weight: 700;
                    ">
                        🔬 Time-Aware Engine
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # -------------------------------------------------------------------------
    # 1. SIMULATION CONTROLS & CONFIGURATION BAR
    # -------------------------------------------------------------------------
    st.markdown("### ⚙️ 1. Simulation Setup & Playback Controls")
    
    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([2, 2, 2, 2])
    with ctrl_col1:
        algo_choice = st.selectbox(
            "Scheduling Algorithm:",
            options=[
                "Adaptive Capacity-Aware (ACALB)",
                "Least Loaded (Cumulative)",
                "Round Robin"
            ],
            index=0,
            help="Select load balancing algorithm for incoming and reassigned requests."
        )
    with ctrl_col2:
        num_servers = st.slider(
            "Initial Servers:",
            min_value=2,
            max_value=8,
            value=3,
            step=1,
            help="Number of virtual nodes in the cloud datacenter."
        )
    with ctrl_col3:
        workload_size = st.selectbox(
            "Workload Trace Size:",
            options=[
                "100 Requests (Fast Demo)",
                "250 Requests (Standard Lab)",
                "500 Requests (Stress Test)",
                "All 1,000 Requests (Full Trace)"
            ],
            index=1,
            help="Select volume of real CSV requests to inject into the discrete-event queue."
        )
    with ctrl_col4:
        recovery_policy_choice = st.selectbox(
            "Fault Recovery Policy:",
            options=[
                "Restart From Beginning (Default)",
                "Checkpoint Recovery"
            ],
            index=0,
            help="Determine whether in-flight tasks restart completely or resume from checkpoint upon server crash."
        )

    # Extract limit integer
    size_map = {
        "100 Requests (Fast Demo)": 100,
        "250 Requests (Standard Lab)": 250,
        "500 Requests (Stress Test)": 500,
        "All 1,000 Requests (Full Trace)": 1000
    }
    req_limit = size_map.get(workload_size, 250)

    # Retrieve or build engine
    engine = get_or_create_engine(num_servers=num_servers, algorithm_choice=algo_choice)
    engine.recovery_manager.recovery_policy = (
        RecoveryPolicy.RESTART_FROM_BEGINNING
        if "Restart" in recovery_policy_choice
        else RecoveryPolicy.CHECKPOINT
    )

    # Simulation Playback Action Buttons
    act_col1, act_col2, act_col3, act_col4 = st.columns(4)
    with act_col1:
        if st.button("🚀 Run Full Simulation", type="primary", use_container_width=True):
            requests = convert_df_to_requests(df_dataset, limit=req_limit)
            engine.initialize_workload(requests)
            with st.spinner("Processing discrete-event queue to completion..."):
                engine.run_all()
            st.toast("✅ Simulation executed to completion!", icon="🚀")
            st.rerun()

    with act_col2:
        if st.button("⏯️ Step Forward (+5 Events)", use_container_width=True):
            if not engine._event_queue and not engine.submitted_requests:
                requests = convert_df_to_requests(df_dataset, limit=req_limit)
                engine.initialize_workload(requests)
            for _ in range(5):
                engine.step()
            st.rerun()

    with act_col3:
        if st.button("⏱️ Advance Clock (+3.0s)", use_container_width=True):
            if not engine._event_queue and not engine.submitted_requests:
                requests = convert_df_to_requests(df_dataset, limit=req_limit)
                engine.initialize_workload(requests)
            target = engine.current_time_sec + 3.0
            engine.run_until(target)
            st.rerun()

    with act_col4:
        if st.button("🔁 Reset Simulation State", use_container_width=True):
            requests = convert_df_to_requests(df_dataset, limit=req_limit)
            engine.initialize_workload(requests)
            st.session_state.pop("comparison_results", None)
            st.toast("Simulation state completely reset.", icon="🔁")
            st.rerun()

    # -------------------------------------------------------------------------
    # 2. SIMULATION STATUS HEADER
    # -------------------------------------------------------------------------
    metrics = engine.compute_comprehensive_metrics()
    healthy_count = len([s for s in engine.servers if s.state != ServerState.FAILED])
    outage_count = len(engine.recovery_manager.cluster_outage_buffer)

    st.markdown(
        f"""
        <div style="
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 0.6rem;
            margin: 0.8rem 0 1.2rem 0;
        ">
            <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 8px; padding: 0.6rem; text-align: center;">
                <div style="color: #94A3B8; font-size: 0.75rem;">Sim Clock</div>
                <div style="color: #38BDF8; font-size: 1.15rem; font-weight: 700; font-family: monospace;">{engine.current_time_sec:.2f}s</div>
            </div>
            <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 8px; padding: 0.6rem; text-align: center;">
                <div style="color: #94A3B8; font-size: 0.75rem;">Active Nodes</div>
                <div style="color: {'#10B981' if healthy_count > 0 else '#EF4444'}; font-size: 1.15rem; font-weight: 700;">{healthy_count} / {len(engine.servers)}</div>
            </div>
            <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 8px; padding: 0.6rem; text-align: center;">
                <div style="color: #94A3B8; font-size: 0.75rem;">Completed</div>
                <div style="color: #34D399; font-size: 1.15rem; font-weight: 700;">{metrics['Completed_Requests']}</div>
            </div>
            <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 8px; padding: 0.6rem; text-align: center;">
                <div style="color: #94A3B8; font-size: 0.75rem;">Retried Events</div>
                <div style="color: {'#F59E0B' if metrics['Retried_Request_Events'] > 0 else '#94A3B8'}; font-size: 1.15rem; font-weight: 700;">{metrics['Retried_Request_Events']}</div>
            </div>
            <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 8px; padding: 0.6rem; text-align: center;">
                <div style="color: #94A3B8; font-size: 0.75rem;">Lost Work</div>
                <div style="color: {'#EF4444' if metrics['Total_Lost_Work_ms'] > 0 else '#94A3B8'}; font-size: 1.15rem; font-weight: 700;">{metrics['Total_Lost_Work_ms']:.0f} ms</div>
            </div>
            <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 8px; padding: 0.6rem; text-align: center;">
                <div style="color: #94A3B8; font-size: 0.75rem;">Outage Buffer</div>
                <div style="color: {'#EF4444' if outage_count > 0 else '#94A3B8'}; font-size: 1.15rem; font-weight: 700;">{outage_count}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 3. VIRTUAL SERVER CLUSTER MONITOR
    # -------------------------------------------------------------------------
    render_cluster_monitor(engine.servers)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 4. DISASTER CONTROL CENTER
    # -------------------------------------------------------------------------
    render_chaos_controls(engine)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 5. LIVE EVENT TIMELINE
    # -------------------------------------------------------------------------
    render_event_timeline(engine.logger)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 6. PERFORMANCE CHARTS & TELEMETRY
    # -------------------------------------------------------------------------
    render_performance_charts(engine)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 7. ALGORITHM COMPARISON STRESS TEST
    # -------------------------------------------------------------------------
    all_raw_reqs = convert_df_to_requests(df_dataset)
    render_algorithm_comparison_section(all_raw_reqs, num_servers)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 8. EXPORT CENTER
    # -------------------------------------------------------------------------
    render_export_center(engine)
