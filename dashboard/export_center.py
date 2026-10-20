"""
Export Center Component for Cloud Chaos Lab.
Provides instant CSV and JSON download generation for simulation event logs,
request lifecycle records, recovery statistics, and auto-scaling audit trails.
"""

import json
from typing import Dict, Any
import pandas as pd
import streamlit as st
from simulator.chaos_engine import ChaosSimulationEngine


def render_export_center(engine: ChaosSimulationEngine) -> None:
    """Render export cards and download buttons for all simulation artifacts."""
    st.markdown("### 📥 Cloud Chaos Lab Data & Audit Export Center")
    st.caption("Download comprehensive scientific logs and experimental data in standard CSV and JSON formats.")

    col1, col2, col3, col4 = st.columns(4)

    # 1. Event Logs
    df_logs = engine.logger.to_dataframe()
    with col1:
        st.markdown("**1. Audit Event Logs**")
        st.caption(f"{len(df_logs)} recorded disaster & recovery events.")
        st.download_button(
            label="📄 Event Logs (CSV)",
            data=df_logs.to_csv(index=False).encode("utf-8"),
            file_name=f"chaos_lab_event_logs_{len(engine.servers)}servers.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            label="📦 Event Logs (JSON)",
            data=engine.logger.to_json(indent=2).encode("utf-8"),
            file_name=f"chaos_lab_event_logs_{len(engine.servers)}servers.json",
            mime="application/json",
            use_container_width=True,
        )

    # 2. Request Lifecycle Assignments
    req_dicts = [r.to_dict() for r in engine.completed_requests + engine.failed_requests]
    df_reqs = pd.DataFrame(req_dicts) if req_dicts else pd.DataFrame()
    with col2:
        st.markdown("**2. Request Assignments**")
        st.caption(f"{len(df_reqs)} completed/failed request lifecycles.")
        if not df_reqs.empty:
            st.download_button(
                label="📄 Request Lifecycle (CSV)",
                data=df_reqs.to_csv(index=False).encode("utf-8"),
                file_name=f"chaos_lab_requests_{len(engine.servers)}servers.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.download_button(
                label="📦 Request Lifecycle (JSON)",
                data=json.dumps(req_dicts, indent=2).encode("utf-8"),
                file_name=f"chaos_lab_requests_{len(engine.servers)}servers.json",
                mime="application/json",
                use_container_width=True,
            )
        else:
            st.info("No requests completed.")

    # 3. Per-Server Telemetry Ledger
    metrics = engine.compute_comprehensive_metrics()
    server_metrics_list = [
        {"Server": sname, **sdata}
        for sname, sdata in metrics.get("Server_Metrics", {}).items()
    ]
    df_srv = pd.DataFrame(server_metrics_list)
    with col3:
        st.markdown("**3. Server Performance**")
        st.caption(f"{len(df_srv)} server node metrics.")
        st.download_button(
            label="📄 Server Metrics (CSV)",
            data=df_srv.to_csv(index=False).encode("utf-8"),
            file_name=f"chaos_lab_server_metrics_{len(engine.servers)}servers.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            label="📦 Server Metrics (JSON)",
            data=json.dumps(metrics.get("Server_Metrics", {}), indent=2).encode("utf-8"),
            file_name=f"chaos_lab_server_metrics_{len(engine.servers)}servers.json",
            mime="application/json",
            use_container_width=True,
        )

    # 4. Auto-Scaling Decisions
    scaling_decisions = [d.to_dict() for d in engine.autoscaler.decision_history]
    df_scaling = pd.DataFrame(scaling_decisions) if scaling_decisions else pd.DataFrame()
    with col4:
        st.markdown("**4. Auto-Scaling Audit**")
        st.caption(f"{len(df_scaling)} elastic scaling decisions.")
        if not df_scaling.empty:
            st.download_button(
                label="📄 Scaling Decisions (CSV)",
                data=df_scaling.to_csv(index=False).encode("utf-8"),
                file_name=f"chaos_lab_autoscaling_{len(engine.servers)}servers.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.download_button(
                label="📦 Scaling Decisions (JSON)",
                data=json.dumps(scaling_decisions, indent=2).encode("utf-8"),
                file_name=f"chaos_lab_autoscaling_{len(engine.servers)}servers.json",
                mime="application/json",
                use_container_width=True,
            )
        else:
            st.caption("No scaling decisions logged yet.")
