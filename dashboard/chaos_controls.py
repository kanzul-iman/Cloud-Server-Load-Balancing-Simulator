"""
Chaos Control Panel Component for Cloud Chaos Lab.
Provides real-time interactive triggers for faults, traffic spikes,
CPU throttling, server recoveries, and auto-scaling toggles.
"""

from typing import List, Optional, Tuple, Callable
import streamlit as st
from simulator.models import CloudServer, ServerState
from simulator.chaos_engine import ChaosSimulationEngine


def render_chaos_controls(engine: ChaosSimulationEngine) -> None:
    """Render the interactive Chaos Injection Control Panel."""
    st.markdown("### ⚡ Chaos Disaster Control Center")
    st.caption("Intentionally inject simulated distributed system failures and observe automated recovery.")

    tab_crash, tab_spike, tab_degrade, tab_recover, tab_cascade, tab_autoscale = st.tabs([
        "💥 Crash Server",
        "🌊 Traffic Spike",
        "📉 CPU Throttling",
        "🔄 Recover Server",
        "🚨 Combined Disaster",
        "⚖️ Auto-Scaling"
    ])

    # -------------------------------------------------------------------------
    # TAB 1: CRASH SERVER
    # -------------------------------------------------------------------------
    with tab_crash:
        st.markdown("**Simulate Immediate Node Hardware Crash:**")
        healthy_candidates = [s for s in engine.servers if s.state != ServerState.FAILED]
        
        if healthy_candidates:
            c_col1, c_col2 = st.columns([3, 2])
            with c_col1:
                selected_server_id = st.selectbox(
                    "Target Server to Crash:",
                    options=[s.server_id for s in healthy_candidates],
                    format_func=lambda sid: f"{engine.get_server_by_id(sid).name} (Current: {engine.get_server_by_id(sid).state.value})"
                )
            with c_col2:
                st.write("")
                st.write("")
                if st.button("💥 Crash Selected Server", type="primary", use_container_width=True):
                    success = engine.inject_server_crash(selected_server_id)
                    if success:
                        st.toast(f"🚨 Dispatched failure event for Server {selected_server_id}!", icon="💥")
                        st.rerun()
        else:
            st.error("All servers are currently failed! Cluster is in a total outage state.")

    # -------------------------------------------------------------------------
    # TAB 2: TRAFFIC SPIKE
    # -------------------------------------------------------------------------
    with tab_spike:
        st.markdown("**Generate Sudden High-Volume Traffic Influx:**")
        sp_col1, sp_col2, sp_col3, sp_col4 = st.columns(4)
        with sp_col1:
            spike_count = st.slider("Additional Requests:", min_value=10, max_value=200, value=50, step=10)
        with sp_col2:
            spike_rate = st.slider("Arrival Rate (RPS):", min_value=5, max_value=60, value=25, step=5)
        with sp_col3:
            spike_dur = st.slider("Duration (seconds):", min_value=1.0, max_value=10.0, value=3.0, step=0.5)
        with sp_col4:
            spike_profile = st.selectbox("Workload Profile:", options=["light", "medium", "heavy"], index=1)

        seed = st.number_input("Random Seed:", min_value=1, max_value=9999, value=42)
        if st.button("🌊 Inject Traffic Spike", use_container_width=True):
            engine.inject_traffic_spike(
                count=spike_count,
                arrival_rate_rps=spike_rate,
                duration_sec=spike_dur,
                profile=spike_profile,
                seed=seed
            )
            st.toast(f"🌊 Injected {spike_count} {spike_profile} requests over {spike_dur}s!", icon="🌊")
            st.rerun()

    # -------------------------------------------------------------------------
    # TAB 3: CPU THROTTLING / DEGRADATION
    # -------------------------------------------------------------------------
    with tab_degrade:
        st.markdown("**Simulate Thermal Throttling / Resource Contention:**")
        active_nodes = [s for s in engine.servers if s.state != ServerState.FAILED]
        if active_nodes:
            d_col1, d_col2 = st.columns([3, 2])
            with d_col1:
                deg_server_id = st.selectbox(
                    "Target Server to Degrade:",
                    options=[s.server_id for s in active_nodes],
                    format_func=lambda sid: f"{engine.get_server_by_id(sid).name} (Speed: {engine.get_server_by_id(sid).effective_capacity:.2f}x)"
                )
                deg_level = st.select_slider(
                    "Select CPU Processing Capacity Multiplier:",
                    options=[0.25, 0.50, 0.75, 1.0],
                    value=0.50,
                    format_func=lambda v: f"{int(v*100)}% ({v:.2f}x Speed)"
                )
            with d_col2:
                st.write("")
                st.write("")
                if st.button("📉 Apply CPU Throttling", use_container_width=True):
                    engine.inject_server_degradation(deg_server_id, deg_level)
                    st.toast(f"⚡ Throttled Server {deg_server_id} to {int(deg_level*100)}% speed!", icon="⚡")
                    st.rerun()
        else:
            st.info("No active servers available to degrade.")

    # -------------------------------------------------------------------------
    # TAB 4: RECOVER SERVER
    # -------------------------------------------------------------------------
    with tab_recover:
        st.markdown("**Restore Crashed Servers Back to Cluster:**")
        failed_servers = [s for s in engine.servers if s.state == ServerState.FAILED]
        if failed_servers:
            r_col1, r_col2 = st.columns([3, 2])
            with r_col1:
                rec_server_id = st.selectbox(
                    "Select Crashed Server to Restore:",
                    options=[s.server_id for s in failed_servers],
                    format_func=lambda sid: f"{engine.get_server_by_id(sid).name} (Failed at t={engine.get_server_by_id(sid).failure_timestamp or 0.0:.1f}s)"
                )
            with r_col2:
                st.write("")
                st.write("")
                if st.button("🔄 Initiate Server Recovery", type="primary", use_container_width=True):
                    engine.inject_server_recovery(rec_server_id)
                    st.toast(f"🔄 Recovery protocol started for Server {rec_server_id}!", icon="🔄")
                    st.rerun()
        else:
            st.success("✔ All servers are currently healthy. No servers in FAILED state.")

    # -------------------------------------------------------------------------
    # TAB 5: COMBINED DISASTER
    # -------------------------------------------------------------------------
    with tab_cascade:
        st.markdown("**Execute Multi-Failure Stress Test:**")
        st.warning(
            "⚠️ **Disaster Cascade:** Injects a 60-request heavy traffic surge, immediately crashes Server 2, "
            "and throttles Server 3 to 50% capacity. Tests how the cluster reassigns tasks and whether auto-scaling catches the load."
        )
        if st.button("🚨 Trigger Combined Disaster Cascade", type="primary", use_container_width=True):
            engine.run_combined_disaster()
            st.toast("🚨 Combined Disaster Cascade Initiated!", icon="🚨")
            st.rerun()

    # -------------------------------------------------------------------------
    # TAB 6: AUTO-SCALING TOGGLE
    # -------------------------------------------------------------------------
    with tab_autoscale:
        st.markdown("**Horizontal Elastic Auto-Scaling Controller:**")
        a_col1, a_col2 = st.columns([2, 3])
        with a_col1:
            scale_toggle = st.toggle("Enable Elastic Auto-Scaling", value=engine.autoscaler.enabled)
            if scale_toggle != engine.autoscaler.enabled:
                engine.autoscaler.enabled = scale_toggle
                st.toast(f"Auto-scaling {'ENABLED' if scale_toggle else 'DISABLED'}!", icon="⚖️")
                st.rerun()
        with a_col2:
            st.markdown(
                f"""
                <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 8px; padding: 0.6rem 0.9rem; font-size: 0.85rem;">
                    <div>Status: <strong style="color: {'#10B981' if engine.autoscaler.enabled else '#94A3B8'};">{'🟢 ACTIVE' if engine.autoscaler.enabled else '⚪ DISABLED'}</strong></div>
                    <div style="color: #94A3B8; margin-top: 0.2rem;">
                        Scale Out Threshold: <strong>> {engine.autoscaler.scale_out_threshold_pct}% CPU</strong> &bull;
                        Scale In Threshold: <strong>< {engine.autoscaler.scale_in_threshold_pct}% CPU</strong>
                    </div>
                    <div style="color: #94A3B8; margin-top: 0.2rem;">
                        Cluster Bounds: <strong>{engine.autoscaler.min_servers} to {engine.autoscaler.max_servers} nodes</strong> &bull;
                        Cooldown: <strong>{engine.autoscaler.cooldown_sec}s</strong>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
