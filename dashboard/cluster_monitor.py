"""
Cluster Monitor Component for Cloud Chaos Lab.
Provides a modern, ultra-compact Datacenter Blade monitor that fits cleanly on screen
without consuming excessive vertical height, plus an optional detailed Node Inspector.
"""

from typing import List, Dict, Any
import streamlit as st
import pandas as pd
from simulator.models import CloudServer, ServerState


STATE_COLORS = {
    ServerState.HEALTHY: {"border": "#10B981", "bg": "rgba(16, 185, 129, 0.12)", "text": "#34D399", "icon": "🟢"},
    ServerState.BUSY: {"border": "#3B82F6", "bg": "rgba(59, 130, 246, 0.12)", "text": "#60A5FA", "icon": "🔵"},
    ServerState.OVERLOADED: {"border": "#F59E0B", "bg": "rgba(245, 158, 11, 0.15)", "text": "#FBBF24", "icon": "⚠️"},
    ServerState.DEGRADED: {"border": "#A855F7", "bg": "rgba(168, 85, 247, 0.15)", "text": "#C084FC", "icon": "⚡"},
    ServerState.FAILED: {"border": "#EF4444", "bg": "rgba(239, 68, 68, 0.20)", "text": "#F87171", "icon": "🔴"},
    ServerState.RECOVERING: {"border": "#06B6D4", "bg": "rgba(6, 182, 212, 0.15)", "text": "#38BDF8", "icon": "🔄"},
    ServerState.IDLE: {"border": "#64748B", "bg": "rgba(100, 116, 139, 0.10)", "text": "#94A3B8", "icon": "⚪"},
}


def render_compact_server_blade(server: CloudServer) -> None:
    """Render an ultra-compact horizontal cloud node blade card (Height ~140px)."""
    theme = STATE_COLORS.get(server.state, STATE_COLORS[ServerState.HEALTHY])
    cpu_pct = server.cpu_utilization_pct
    ram_pct = server.ram_utilization_pct
    eff_cap = server.effective_capacity
    is_draining = getattr(server, "is_draining", False)
    
    state_label = server.state.value
    if is_draining:
        state_label += " (DRAINING)"

    active_desc = "Idle"
    if server.active_request:
        active_desc = f"{server.active_request.request_id} ({server.active_request.processing_time_ms:.0f}ms)"

    blade_html = f"""
    <div style="
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1.5px solid {theme['border']};
        border-radius: 10px;
        padding: 0.75rem 0.85rem;
        margin-bottom: 0.6rem;
        box-shadow: 0 4px 12px {theme['bg']};
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    ">
        <!-- Header: Node Name + State Badge -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
            <div style="font-weight: 700; font-size: 0.95rem; color: #F8FAFC; display: flex; align-items: center; gap: 0.35rem;">
                <span>🖥️</span> <span>{server.name}</span>
            </div>
            <span style="
                background: {theme['bg']};
                color: {theme['text']};
                border: 1px solid {theme['border']};
                padding: 0.12rem 0.5rem;
                border-radius: 12px;
                font-size: 0.72rem;
                font-weight: 700;
                display: inline-flex;
                align-items: center;
                gap: 0.25rem;
            ">
                {theme['icon']} {state_label}
            </span>
        </div>

        <!-- Inline CPU & RAM Mini Bars -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-bottom: 0.45rem; font-size: 0.74rem;">
            <div>
                <div style="display: flex; justify-content: space-between; color: #94A3B8; margin-bottom: 2px;">
                    <span>CPU: <strong style="color: #CBD5E1;">{cpu_pct:.0f}%</strong></span>
                    <span style="color: #38BDF8; font-weight: 600;">{eff_cap:.2f}x</span>
                </div>
                <div style="background: rgba(255,255,255,0.08); border-radius: 4px; height: 5px; overflow: hidden;">
                    <div style="background: linear-gradient(90deg, {theme['border']}, #38BDF8); width: {min(100.0, cpu_pct)}%; height: 100%;"></div>
                </div>
            </div>
            <div>
                <div style="display: flex; justify-content: space-between; color: #94A3B8; margin-bottom: 2px;">
                    <span>RAM: <strong style="color: #CBD5E1;">{ram_pct:.0f}%</strong></span>
                </div>
                <div style="background: rgba(255,255,255,0.08); border-radius: 4px; height: 5px; overflow: hidden;">
                    <div style="background: #818CF8; width: {min(100.0, ram_pct)}%; height: 100%;"></div>
                </div>
            </div>
        </div>

        <!-- Active Task & Queue Backlog Strip -->
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(15,23,42,0.65);
            border-radius: 6px;
            padding: 0.3rem 0.55rem;
            font-size: 0.74rem;
            margin-bottom: 0.4rem;
        ">
            <span style="color: #94A3B8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 68%;">
                ⚡ <span style="color: {'#34D399' if server.active_request else '#94A3B8'}; font-weight: 600;">{active_desc}</span>
            </span>
            <span style="
                background: {'rgba(245, 158, 11, 0.2)' if server.queue_length > 0 else 'rgba(100, 116, 139, 0.15)'};
                color: {'#FBBF24' if server.queue_length > 0 else '#94A3B8'};
                border-radius: 10px;
                padding: 0.05rem 0.45rem;
                font-weight: 700;
                font-size: 0.7rem;
            ">
                Q: {server.queue_length}
            </span>
        </div>

        <!-- Micro Telemetry Chips -->
        <div style="
            display: flex;
            justify-content: space-between;
            color: #94A3B8;
            font-size: 0.72rem;
            border-top: 1px solid rgba(148,163,184,0.12);
            padding-top: 0.35rem;
        ">
            <span>Done: <strong style="color: #38BDF8;">{len(server.completed_requests)}</strong></span>
            <span>Retried: <strong style="color: {'#F59E0B' if server.retried_requests_count > 0 else '#94A3B8'};">{server.retried_requests_count}</strong></span>
            <span>Lost: <strong style="color: {'#EF4444' if server.total_lost_work_ms > 0 else '#94A3B8'};">{server.total_lost_work_ms:.0f}ms</strong></span>
        </div>
    </div>
    """
    st.markdown(blade_html, unsafe_allow_html=True)


def render_cluster_monitor(servers: List[CloudServer]) -> None:
    """Render all server nodes in an ultra-compact, high-density layout."""
    h_col1, h_col2 = st.columns([3, 2])
    with h_col1:
        st.markdown("### 🖥️ Virtual Cloud Server Cluster")
    with h_col2:
        view_mode = st.radio(
            "Cluster View:",
            options=["🎛️ Compact Server Blades", "📋 Telemetry Matrix Table"],
            horizontal=True,
            label_visibility="collapsed"
        )

    if not servers:
        st.info("No servers currently active in the cluster.")
        return

    if view_mode == "🎛️ Compact Server Blades":
        # Multi-column grid: 3-4 columns max to keep cards side-by-side
        cols_count = min(4, max(2, len(servers)))
        cols = st.columns(cols_count)
        for idx, srv in enumerate(servers):
            with cols[idx % cols_count]:
                render_compact_server_blade(srv)

    else:
        # High-density Matrix Table View (takes only ~100px total height!)
        rows = []
        for s in servers:
            theme = STATE_COLORS.get(s.state, STATE_COLORS[ServerState.HEALTHY])
            active_info = f"{s.active_request.request_id} ({s.active_request.processing_time_ms:.0f}ms)" if s.active_request else "Idle"
            rows.append({
                "Status": f"{theme['icon']} {s.state.value}",
                "Server Node": s.name,
                "Speed": f"{s.effective_capacity:.2f}x",
                "CPU Util": f"{s.cpu_utilization_pct:.1f}%",
                "RAM Util": f"{s.ram_utilization_pct:.1f}%",
                "Active Task": active_info,
                "Queue Depth": s.queue_length,
                "Completed": len(s.completed_requests),
                "Retried": s.retried_requests_count,
                "Lost Work": f"{s.total_lost_work_ms:.0f} ms"
            })
        df_matrix = pd.DataFrame(rows)
        st.dataframe(df_matrix, use_container_width=True, height=140)
