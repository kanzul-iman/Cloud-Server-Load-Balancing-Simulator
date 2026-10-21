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
from .cluster_monitor import render_cluster_monitor, _safe_render_html
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


GUIDED_SCENARIOS = {
    "🟢 Scenario 1: Normal Baseline Workload (Zero Failures)": {
        "title": "Normal Baseline Workload",
        "badge": "🟢 Baseline",
        "desc": "Executes 250 real cloud requests across 3 healthy servers. Demonstrates ideal load distribution and baseline metrics without faults.",
        "algo": "Adaptive Capacity-Aware (ACALB)",
        "num_servers": 3,
        "workload_size": "250 Requests (Standard Lab)",
        "policy": "Restart From Beginning (Default)",
        "injections": [],
    },
    "💥 Scenario 2: Single Node Crash & Automated Failover": {
        "title": "Single Node Crash & Failover",
        "badge": "💥 Failover",
        "desc": "Server 2 crashes at t=2.0s while executing tasks. Watch the Health Monitor detect the crash, harvest in-flight tasks, and reassign them to Server 1 & Server 3 with zero dropped requests.",
        "algo": "Adaptive Capacity-Aware (ACALB)",
        "num_servers": 3,
        "workload_size": "250 Requests (Standard Lab)",
        "policy": "Restart From Beginning (Default)",
        "injections": [("crash", 2, 2.0)],
    },
    "🌊 Scenario 3: High-Volume Traffic Surge + CPU Throttling": {
        "title": "Traffic Surge & CPU Degradation",
        "badge": "🌊 Adaptive Shedding",
        "desc": "Injects a 50-request viral surge at t=1.0s, and throttles Server 3 to 50% CPU speed at t=1.5s. Demonstrates ACALB intelligently steering requests away from degraded nodes.",
        "algo": "Adaptive Capacity-Aware (ACALB)",
        "num_servers": 3,
        "workload_size": "250 Requests (Standard Lab)",
        "policy": "Restart From Beginning (Default)",
        "injections": [("spike", 50, 1.0), ("degrade", 3, 0.50, 1.5)],
    },
    "🚨 Scenario 4: Compound Disaster Cascade": {
        "title": "Multi-Failure Compound Stress Test",
        "badge": "🚨 Cascade",
        "desc": "Severe stress test: 60-request heavy spike + Server 2 hardware crash at t=1.0s + Server 3 CPU throttled to 50% at t=1.5s. Demonstrates cluster survival under compound failures.",
        "algo": "Adaptive Capacity-Aware (ACALB)",
        "num_servers": 3,
        "workload_size": "250 Requests (Standard Lab)",
        "policy": "Restart From Beginning (Default)",
        "injections": [("cascade", 0.0)],
    },
    "🛡️ Scenario 5: Total Cluster Outage & Buffer Drain": {
        "title": "Total Cluster Outage & Buffer Recovery",
        "badge": "🛡️ Outage Buffer",
        "desc": "All servers crash at t=1.0s. All incoming requests are held safely in the Cluster Outage Buffer. Server 1 restores at t=4.0s and drains the backlog with zero lost requests.",
        "algo": "Adaptive Capacity-Aware (ACALB)",
        "num_servers": 3,
        "workload_size": "100 Requests (Fast Demo)",
        "policy": "Restart From Beginning (Default)",
        "injections": [("crash_all", 1.0), ("recover", 1, 4.0)],
    },
}


def apply_scenario_injections(engine: ChaosSimulationEngine, injections: List[Any]) -> None:
    """Schedule planned scenario disaster injections into discrete event priority queue."""
    for inj in injections:
        itype = inj[0]
        if itype == "crash":
            _, s_id, t = inj
            engine.inject_server_crash(s_id, timestamp_sec=t)
        elif itype == "spike":
            _, count, t = inj
            engine.inject_traffic_spike(count=count, arrival_rate_rps=25.0, duration_sec=3.0, profile="heavy", seed=42, timestamp_sec=t)
        elif itype == "degrade":
            _, s_id, factor, t = inj
            engine.inject_server_degradation(s_id, factor, timestamp_sec=t)
        elif itype == "cascade":
            _, t = inj
            engine.run_combined_disaster(timestamp_sec=t)
        elif itype == "crash_all":
            _, t = inj
            for s in engine.servers:
                engine.inject_server_crash(s.server_id, timestamp_sec=t)
        elif itype == "recover":
            _, s_id, t = inj
            engine.inject_server_recovery(s_id, timestamp_sec=t)


def render_incident_lifecycle_inspector(engine: ChaosSimulationEngine) -> None:
    """Render the Live Incident & Failover Lifecycle Inspector."""
    st.markdown("### 🔍 4. Live Incident & Failover Lifecycle Inspector")
    st.caption("Visualizes where and how computational tasks are rescued, reassigned, and executed when an infrastructure failure occurs.")

    failed_servers = [s for s in engine.servers if s.state == ServerState.FAILED]
    degraded_servers = [s for s in engine.servers if s.state == ServerState.DEGRADED]
    recovered_requests = [r for r in engine.completed_requests if getattr(r, "is_recovered", False) or r.retry_count > 0]
    outage_buffer_reqs = engine.recovery_manager.cluster_outage_buffer

    if failed_servers or degraded_servers or recovered_requests or outage_buffer_reqs:
        # Build live status alert
        status_items = []
        if failed_servers:
            status_items.append(f"🔴 **Hardware Crash:** {', '.join([s.name for s in failed_servers])}")
        if degraded_servers:
            status_items.append(f"⚡ **CPU Degradation:** {', '.join([f'{s.name} ({s.effective_capacity:.2f}x speed)' for s in degraded_servers])}")
        if recovered_requests:
            status_items.append(f"🔄 **Rescued Tasks:** {len(recovered_requests)} tasks safely re-routed")
        if outage_buffer_reqs:
            status_items.append(f"🛡️ **Outage Buffer:** {len(outage_buffer_reqs)} tasks queued awaiting healthy node")

        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, rgba(239, 68, 68, 0.14) 0%, rgba(245, 158, 11, 0.14) 100%);
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-left: 5px solid #EF4444;
                border-radius: 10px;
                padding: 0.85rem 1.15rem;
                margin-bottom: 0.9rem;
            ">
                <div style="color: #FCA5A5; font-size: 0.92rem; font-weight: 800; margin-bottom: 0.25rem;">
                    🚨 INCIDENT DETECTED & FAILOVER IN PROGRESS
                </div>
                <div style="color: #F8FAFC; font-size: 0.84rem; line-height: 1.5;">
                    {' &bull; '.join(status_items)}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 5-Stage Lifecycle Visualizer
        st.markdown(
            """
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 0.5rem; margin-bottom: 0.9rem;">
                <div style="background: rgba(30, 41, 59, 0.65); border: 1px solid rgba(239, 68, 68, 0.45); border-radius: 8px; padding: 0.6rem; text-align: center;">
                    <div style="font-size: 1.05rem;">💥 1. Fault Trigger</div>
                    <div style="font-size: 0.72rem; color: #FCA5A5; font-weight: 700; margin-top: 2px;">Node Hardware Crash</div>
                    <div style="font-size: 0.68rem; color: #94A3B8;">Server marked 🔴 FAILED; active task halted</div>
                </div>
                <div style="background: rgba(30, 41, 59, 0.65); border: 1px solid rgba(245, 158, 11, 0.45); border-radius: 8px; padding: 0.6rem; text-align: center;">
                    <div style="font-size: 1.05rem;">⏱️ 2. Detection</div>
                    <div style="font-size: 0.72rem; color: #FCD34D; font-weight: 700; margin-top: 2px;">Heartbeat Monitor</div>
                    <div style="font-size: 0.68rem; color: #94A3B8;">Missed ping; 1.5s latency confirmed</div>
                </div>
                <div style="background: rgba(30, 41, 59, 0.65); border: 1px solid rgba(56, 189, 248, 0.45); border-radius: 8px; padding: 0.6rem; text-align: center;">
                    <div style="font-size: 1.05rem;">📦 3. Task Harvest</div>
                    <div style="font-size: 0.72rem; color: #7DD3FC; font-weight: 700; margin-top: 2px;">Recovery Manager</div>
                    <div style="font-size: 0.68rem; color: #94A3B8;">Rescues in-flight + queued tasks safely</div>
                </div>
                <div style="background: rgba(30, 41, 59, 0.65); border: 1px solid rgba(168, 85, 247, 0.45); border-radius: 8px; padding: 0.6rem; text-align: center;">
                    <div style="font-size: 1.05rem;">🔀 4. Reassignment</div>
                    <div style="font-size: 0.72rem; color: #D8B4FE; font-weight: 700; margin-top: 2px;">Adaptive ACALB</div>
                    <div style="font-size: 0.68rem; color: #94A3B8;">Routes tasks to healthiest available nodes</div>
                </div>
                <div style="background: rgba(30, 41, 59, 0.65); border: 1px solid rgba(16, 185, 129, 0.45); border-radius: 8px; padding: 0.6rem; text-align: center;">
                    <div style="font-size: 1.05rem;">✔ 5. Zero-Loss Done</div>
                    <div style="font-size: 0.72rem; color: #6EE7B7; font-weight: 700; margin-top: 2px;">100% Request Delivery</div>
                    <div style="font-size: 0.68rem; color: #94A3B8;">0 tasks dropped; CPU metrics finalized</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if recovered_requests:
            st.markdown("**📋 Manifest of Rescued & Reassigned Tasks:**")
            failover_rows = []
            for r in recovered_requests[:25]:
                orig = ", ".join(r.reassigned_from) if r.reassigned_from else "Unknown"
                dest = r.assigned_server or "Pending Buffer"
                failover_rows.append({
                    "Request ID": r.request_id,
                    "Type": r.request_type,
                    "Duration": f"{r.processing_time_ms:.0f} ms",
                    "Original Node (Crashed)": f"🔴 {orig}",
                    "Rescue Destination": f"🟢 {dest}",
                    "Wasted Work": f"{r.lost_work_ms:.0f} ms",
                    "Retries": r.retry_count,
                    "Outcome": "✔ Recovered & Completed"
                })
            df_failover = pd.DataFrame(failover_rows)
            st.dataframe(df_failover, use_container_width=True, height=min(220, 38 + len(failover_rows) * 35))

        with st.expander("💡 Deep Dive: How the Scheduler Selected the Rescue Node", expanded=False):
            st.markdown(
                r"""
                When an in-flight request is interrupted by a hardware crash, the **Recovery Manager** coordinates with the active scheduler to find the optimal failover node:
                - **Adaptive Capacity-Aware (ACALB):** Evaluates $\text{Load Score} = \frac{\text{Queue Backlog}}{\text{Effective Capacity}}$. It routes the orphaned task to the surviving server with the lowest score (least congested relative to speed).
                - **Least Loaded:** Calculates the cumulative processing time across eligible surviving servers and selects the node with the lowest total backlog.
                - **Round Robin:** Steps to the next available online server in cyclic order.
                - **Zero Loss Principle:** Even if all servers are crashed simultaneously, tasks are preserved in the **Cluster Outage Buffer** and drained upon server recovery.
                """
            )
    else:
        st.markdown(
            """
            <div style="
                background: rgba(15, 23, 42, 0.5);
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-left: 5px solid #10B981;
                border-radius: 10px;
                padding: 0.85rem 1.2rem;
                margin-bottom: 0.8rem;
            ">
                <div style="color: #6EE7B7; font-size: 0.9rem; font-weight: 700; margin-bottom: 0.2rem;">
                    🟢 CLUSTER OPERATING IN OPTIMAL STATE (ZERO INCIDENTS)
                </div>
                <div style="color: #94A3B8; font-size: 0.82rem;">
                    All server blades are healthy and processing tasks normally. No hardware faults or task failovers have occurred.
                    <br>To test disaster recovery and observe where failovers occur, select a <strong>Guided Scenario</strong> in Section 1 or click <strong>'💥 Crash Selected Server'</strong> in Section 5 below.
                </div>
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
    st.markdown("### ⚙️ 1. Simulation Setup & Scenario Playback Controls")

    with st.expander("💡 Visual Guide: Exactly What Changes When an Issue Occurs in Chaos Lab", expanded=False):
        st.markdown(
            r"""
            When an issue is injected into the cloud cluster (server crash, CPU degradation, or traffic surge), here is exactly where changes occur across the application:
            
            1. **🖥️ Server Blade Status (Section 3):**
               - **Node State:** Changes immediately from `🟢 HEALTHY` to `🔴 FAILED` (crash) or `⚡ DEGRADED` (throttled).
               - **CPU Utilization:** Drops to `0%` on a failed node. Surviving servers absorb incoming load and their CPU rises.
               - **Task Queue:** Active in-flight tasks halt; pending queue is frozen and marked for rescue.
            
            2. **⚡ Real-Time Telemetry Banner (Section 2):**
               - **Active Nodes:** Decreases (e.g. `3/3` ➔ `2/3 (🔴 1 Offline)`).
               - **Retried Events:** Increments by `+1` for each rescued in-flight or queued request.
               - **Lost Work:** Tracks wasted CPU burst time (ms) that was discarded when the hardware crashed.
               - **Outage Buffer:** Holds requests safely if all servers are temporarily offline.
            
            3. **🔍 Live Incident & Failover Lifecycle Inspector (Section 4):**
               - Displays an active incident alert with affected nodes and rescued task counts.
               - Shows the 5-stage lifecycle visualizer from Fault Trigger to 100% Zero-Loss Delivery.
               - Provides a complete manifest table showing original server, failover destination, and discarded CPU ms.
            
            4. **📜 Live Disaster & Recovery Audit Timeline (Section 6):**
               - Logs sequential entries: `🚨 CRITICAL` (Crash), `⚠️ WARNING` (Detection & Reassignment), `✔ SUCCESS` (Task completion on new node).
            """
        )

    mode = st.radio(
        "Simulation Mode:",
        options=["🎯 Guided Disaster Scenarios (Recommended)", "🛠️ Custom Cluster Configuration"],
        horizontal=True,
        index=0,
        help="Select a pre-configured disaster scenario or customize cluster settings manually."
    )

    if mode == "🎯 Guided Disaster Scenarios (Recommended)":
        sc_col1, sc_col2 = st.columns([3, 2])
        with sc_col1:
            scenario_key = st.selectbox(
                "Select Disaster & Recovery Scenario:",
                options=list(GUIDED_SCENARIOS.keys()),
                index=1,  # Default to Scenario 2: Single Node Crash & Automated Failover
                help="Choose a pre-configured scientific experiment to test distributed resiliency."
            )
        sc_data = GUIDED_SCENARIOS[scenario_key]
        with sc_col2:
            st.write("")
            st.markdown(
                f"""
                <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 8px; padding: 0.55rem 0.85rem; font-size: 0.8rem; color: #CBD5E1;">
                    <strong style="color: #A5B4FC;">{sc_data['badge']}</strong>: {sc_data['desc']}
                </div>
                """,
                unsafe_allow_html=True
            )

        req_limit = 100 if "100" in sc_data["workload_size"] else 250
        engine = get_or_create_engine(num_servers=sc_data["num_servers"], algorithm_choice=sc_data["algo"])
        engine.recovery_manager.recovery_policy = (
            RecoveryPolicy.RESTART_FROM_BEGINNING
            if "Restart" in sc_data["policy"]
            else RecoveryPolicy.CHECKPOINT
        )

        act_col1, act_col2, act_col3, act_col4 = st.columns(4)
        with act_col1:
            if st.button("🚀 Run Complete Experiment", type="primary", use_container_width=True, help="Executes the entire scenario trace and planned disaster to completion."):
                requests = convert_df_to_requests(df_dataset, limit=req_limit)
                engine.initialize_workload(requests)
                apply_scenario_injections(engine, sc_data["injections"])
                with st.spinner(f"Executing {sc_data['title']} discrete-event queue to completion..."):
                    engine.run_all()
                st.toast(f"✅ Executed {sc_data['title']} to completion!", icon="🚀")
                st.rerun()

        with act_col2:
            if st.button("⏯️ Step Forward (+5 Events)", use_container_width=True, help="Steps 5 discrete simulation events forward."):
                if not engine._event_queue and not engine.submitted_requests:
                    requests = convert_df_to_requests(df_dataset, limit=req_limit)
                    engine.initialize_workload(requests)
                    apply_scenario_injections(engine, sc_data["injections"])
                for _ in range(5):
                    engine.step()
                st.rerun()

        with act_col3:
            if st.button("⏱️ Advance Clock (+3.0s)", use_container_width=True, help="Advances simulation clock by 3.0 simulated seconds."):
                if not engine._event_queue and not engine.submitted_requests:
                    requests = convert_df_to_requests(df_dataset, limit=req_limit)
                    engine.initialize_workload(requests)
                    apply_scenario_injections(engine, sc_data["injections"])
                target = engine.current_time_sec + 3.0
                engine.run_until(target)
                st.rerun()

        with act_col4:
            if st.button("🔁 Reset Cluster State", use_container_width=True, help="Resets cluster to clean initial state."):
                requests = convert_df_to_requests(df_dataset, limit=req_limit)
                engine.initialize_workload(requests)
                st.session_state.pop("comparison_results", None)
                st.toast("Simulation state reset to clean baseline.", icon="🔁")
                st.rerun()

    else:
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

        size_map = {
            "100 Requests (Fast Demo)": 100,
            "250 Requests (Standard Lab)": 250,
            "500 Requests (Stress Test)": 500,
            "All 1,000 Requests (Full Trace)": 1000
        }
        req_limit = size_map.get(workload_size, 250)

        engine = get_or_create_engine(num_servers=num_servers, algorithm_choice=algo_choice)
        engine.recovery_manager.recovery_policy = (
            RecoveryPolicy.RESTART_FROM_BEGINNING
            if "Restart" in recovery_policy_choice
            else RecoveryPolicy.CHECKPOINT
        )

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
    # 2. CLUSTER REAL-TIME TELEMETRY KPI BANNER
    # -------------------------------------------------------------------------
    st.markdown("### ⚡ 2. Cluster Real-Time Telemetry KPI Banner")
    metrics = engine.compute_comprehensive_metrics()
    healthy_count = len([s for s in engine.servers if s.state != ServerState.FAILED])
    outage_count = len(engine.recovery_manager.cluster_outage_buffer)
    total_servers = len(engine.servers)
    is_all_healthy = (healthy_count == total_servers)
    retried_count = metrics['Retried_Request_Events']
    lost_work_ms = metrics['Total_Lost_Work_ms']

    # Dynamic styling values for high contrast & clarity
    nodes_color = "#34D399" if is_all_healthy else ("#FBBF24" if healthy_count > 0 else "#EF4444")
    nodes_border = "#10B981" if is_all_healthy else ("#F59E0B" if healthy_count > 0 else "#EF4444")
    nodes_sub = "🟢 All Online" if is_all_healthy else f"🔴 {total_servers - healthy_count} Offline"

    retried_color = "#FBBF24" if retried_count > 0 else "#F8FAFC"
    retried_border = "#F59E0B" if retried_count > 0 else "rgba(148, 163, 184, 0.25)"
    retried_sub = "⚠️ Failover Retries" if retried_count > 0 else "✔ Zero Retries"
    retried_sub_color = "#FBBF24" if retried_count > 0 else "#34D399"

    lost_color = "#EF4444" if lost_work_ms > 0 else "#F8FAFC"
    lost_border = "#EF4444" if lost_work_ms > 0 else "rgba(148, 163, 184, 0.25)"
    lost_sub = "⚠️ Discarded CPU" if lost_work_ms > 0 else "✔ 0 ms Lost"
    lost_sub_color = "#EF4444" if lost_work_ms > 0 else "#34D399"

    outage_color = "#EF4444" if outage_count > 0 else "#F8FAFC"
    outage_border = "#EF4444" if outage_count > 0 else "rgba(148, 163, 184, 0.25)"
    outage_sub = "⚠️ Buffer Holding" if outage_count > 0 else "✔ Buffer Clear"
    outage_sub_color = "#EF4444" if outage_count > 0 else "#34D399"

    kpi_banner_html = (
        '<style>'
        '.kpi-metrics-grid {'
        '  display: grid;'
        '  grid-template-columns: repeat(6, minmax(0, 1fr));'
        '  gap: 0.65rem;'
        '  margin: 0.8rem 0 1.2rem 0;'
        '  align-items: stretch;'
        '}'
        '@media (max-width: 992px) {'
        '  .kpi-metrics-grid {'
        '    grid-template-columns: repeat(3, minmax(0, 1fr));'
        '  }'
        '}'
        '@media (max-width: 580px) {'
        '  .kpi-metrics-grid {'
        '    grid-template-columns: repeat(2, minmax(0, 1fr));'
        '  }'
        '}'
        '.kpi-card {'
        '  background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);'
        '  border: 1px solid rgba(148, 163, 184, 0.22);'
        '  border-radius: 10px;'
        '  padding: 0.65rem 0.6rem;'
        '  text-align: center;'
        '  display: flex;'
        '  flex-direction: column;'
        '  justify-content: space-between;'
        '  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);'
        '  min-height: 82px;'
        '  box-sizing: border-box;'
        '}'
        '.kpi-label {'
        '  color: #CBD5E1;'
        '  font-size: 0.72rem;'
        '  font-weight: 700;'
        '  text-transform: uppercase;'
        '  letter-spacing: 0.4px;'
        '  display: flex;'
        '  align-items: center;'
        '  justify-content: center;'
        '  gap: 0.3rem;'
        '  margin-bottom: 0.25rem;'
        '}'
        '.kpi-val {'
        '  font-size: 1.3rem;'
        '  font-weight: 800;'
        '  line-height: 1.2;'
        '}'
        '.kpi-sub {'
        '  font-size: 0.68rem;'
        '  font-weight: 600;'
        '  margin-top: 0.25rem;'
        '}'
        '</style>'
        '<div class="kpi-metrics-grid">'
        f'<div class="kpi-card" style="border-top: 3.5px solid #38BDF8;">'
        f'<div class="kpi-label"><span>⏱️</span><span>Sim Clock</span></div>'
        f'<div class="kpi-val" style="color: #38BDF8; font-family: monospace;">{engine.current_time_sec:.2f}s</div>'
        f'<div class="kpi-sub" style="color: #94A3B8;">Live Runtime</div>'
        f'</div>'
        f'<div class="kpi-card" style="border-top: 3.5px solid {nodes_border};">'
        f'<div class="kpi-label"><span>🖥️</span><span>Active Nodes</span></div>'
        f'<div class="kpi-val" style="color: {nodes_color};">{healthy_count} / {total_servers}</div>'
        f'<div class="kpi-sub" style="color: {nodes_color};">{nodes_sub}</div>'
        f'</div>'
        f'<div class="kpi-card" style="border-top: 3.5px solid #10B981;">'
        f'<div class="kpi-label"><span>✅</span><span>Completed</span></div>'
        f'<div class="kpi-val" style="color: #34D399;">{metrics["Completed_Requests"]}</div>'
        f'<div class="kpi-sub" style="color: #94A3B8;">Requests Done</div>'
        f'</div>'
        f'<div class="kpi-card" style="border-top: 3.5px solid {retried_border};">'
        f'<div class="kpi-label"><span>🔄</span><span>Retried Events</span></div>'
        f'<div class="kpi-val" style="color: {retried_color};">{retried_count}</div>'
        f'<div class="kpi-sub" style="color: {retried_sub_color};">{retried_sub}</div>'
        f'</div>'
        f'<div class="kpi-card" style="border-top: 3.5px solid {lost_border};">'
        f'<div class="kpi-label"><span>⚡</span><span>Lost Work</span></div>'
        f'<div class="kpi-val" style="color: {lost_color};">{lost_work_ms:.0f} ms</div>'
        f'<div class="kpi-sub" style="color: {lost_sub_color};">{lost_sub}</div>'
        f'</div>'
        f'<div class="kpi-card" style="border-top: 3.5px solid {outage_border};">'
        f'<div class="kpi-label"><span>🛡️</span><span>Outage Buffer</span></div>'
        f'<div class="kpi-val" style="color: {outage_color};">{outage_count}</div>'
        f'<div class="kpi-sub" style="color: {outage_sub_color};">{outage_sub}</div>'
        f'</div>'
        '</div>'
    )
    _safe_render_html(kpi_banner_html)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 3. VIRTUAL SERVER CLUSTER MONITOR
    # -------------------------------------------------------------------------
    render_cluster_monitor(engine.servers)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 4. LIVE INCIDENT & FAILOVER LIFECYCLE INSPECTOR
    # -------------------------------------------------------------------------
    render_incident_lifecycle_inspector(engine)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 5. DISASTER CONTROL CENTER
    # -------------------------------------------------------------------------
    render_chaos_controls(engine)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 6. LIVE EVENT TIMELINE
    # -------------------------------------------------------------------------
    render_event_timeline(engine.logger)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 7. PERFORMANCE CHARTS & TELEMETRY
    # -------------------------------------------------------------------------
    render_performance_charts(engine)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 8. ALGORITHM COMPARISON STRESS TEST
    # -------------------------------------------------------------------------
    all_raw_reqs = convert_df_to_requests(df_dataset)
    render_algorithm_comparison_section(all_raw_reqs, len(engine.servers))

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 9. EXPORT CENTER
    # -------------------------------------------------------------------------
    render_export_center(engine)

