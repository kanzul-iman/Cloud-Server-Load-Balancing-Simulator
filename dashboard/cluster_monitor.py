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
    ServerState.HEALTHY: {
        "border": "#10B981",
        "bg": "rgba(16, 185, 129, 0.15)",
        "text": "#34D399",
        "glow": "rgba(16, 185, 129, 0.25)",
        "icon": "🟢",
    },
    ServerState.BUSY: {
        "border": "#3B82F6",
        "bg": "rgba(59, 130, 246, 0.15)",
        "text": "#60A5FA",
        "glow": "rgba(59, 130, 246, 0.25)",
        "icon": "🔵",
    },
    ServerState.OVERLOADED: {
        "border": "#F59E0B",
        "bg": "rgba(245, 158, 11, 0.18)",
        "text": "#FBBF24",
        "glow": "rgba(245, 158, 11, 0.3)",
        "icon": "⚠️",
    },
    ServerState.DEGRADED: {
        "border": "#A855F7",
        "bg": "rgba(168, 85, 247, 0.18)",
        "text": "#C084FC",
        "glow": "rgba(168, 85, 247, 0.3)",
        "icon": "⚡",
    },
    ServerState.FAILED: {
        "border": "#EF4444",
        "bg": "rgba(239, 68, 68, 0.22)",
        "text": "#F87171",
        "glow": "rgba(239, 68, 68, 0.35)",
        "icon": "🔴",
    },
    ServerState.RECOVERING: {
        "border": "#06B6D4",
        "bg": "rgba(6, 182, 212, 0.18)",
        "text": "#38BDF8",
        "glow": "rgba(6, 182, 212, 0.3)",
        "icon": "🔄",
    },
    ServerState.IDLE: {
        "border": "#64748B",
        "bg": "rgba(100, 116, 139, 0.12)",
        "text": "#94A3B8",
        "glow": "rgba(100, 116, 139, 0.18)",
        "icon": "⚪",
    },
}


def _safe_render_html(html_str: str) -> None:
    """Render HTML safely, preferring st.html to prevent markdown parsing bugs."""
    if hasattr(st, "html"):
        st.html(html_str)
    else:
        st.markdown(html_str, unsafe_allow_html=True)


def build_blade_card_html(server: CloudServer) -> str:
    """Build ultra-compact HTML markup for a single server blade card (Height ~130px)."""
    theme = STATE_COLORS.get(server.state, STATE_COLORS[ServerState.HEALTHY])
    cpu_pct = server.cpu_utilization_pct
    ram_pct = server.ram_utilization_pct
    eff_cap = server.effective_capacity
    is_draining = getattr(server, "is_draining", False)

    state_label = server.state.value
    if is_draining:
        state_label += " (DRAIN)"

    active_desc = "Idle / Standby"
    if server.active_request:
        active_desc = f"{server.active_request.request_id} ({server.active_request.processing_time_ms:.0f}ms)"

    # Determine CPU bar color dynamically based on health/utilization
    if server.state == ServerState.FAILED:
        cpu_bar_gradient = "#475569"
        cpu_val_color = "#94A3B8"
    elif cpu_pct >= 90.0:
        cpu_bar_gradient = "linear-gradient(90deg, #F59E0B, #EF4444)"
        cpu_val_color = "#EF4444"
    elif cpu_pct >= 70.0:
        cpu_bar_gradient = "linear-gradient(90deg, #38BDF8, #F59E0B)"
        cpu_val_color = "#F59E0B"
    else:
        cpu_bar_gradient = "linear-gradient(90deg, #10B981, #38BDF8)"
        cpu_val_color = "#38BDF8"

    # Queue styling
    q_len = server.queue_length
    if q_len > 0:
        q_bg = "rgba(245, 158, 11, 0.22)"
        q_color = "#FBBF24"
        q_border = "rgba(245, 158, 11, 0.45)"
    else:
        q_bg = "rgba(100, 116, 139, 0.15)"
        q_color = "#94A3B8"
        q_border = "rgba(148, 163, 184, 0.15)"

    retried_count = server.retried_requests_count
    lost_ms = server.total_lost_work_ms

    return (
        f'<div style="background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); '
        f'border: 1px solid rgba(148, 163, 184, 0.2); border-top: 3.5px solid {theme["border"]}; '
        f'border-radius: 10px; padding: 0.65rem 0.85rem; box-shadow: 0 4px 12px rgba(0,0,0,0.25), 0 0 10px {theme["glow"]}; '
        f'display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box; '
        f'min-height: 128px; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">'
        f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">'
        f'<div style="display: flex; align-items: center; gap: 0.4rem;">'
        f'<span style="font-size: 0.95rem;">🖥️</span>'
        f'<strong style="font-size: 0.92rem; color: #F8FAFC; letter-spacing: -0.2px;">{server.name}</strong>'
        f'<span style="font-size: 0.68rem; font-weight: 600; color: #38BDF8; background: rgba(56, 189, 248, 0.12); '
        f'border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 4px; padding: 0.05rem 0.35rem;" title="Effective Speed Multiplier">{eff_cap:.2f}x</span>'
        f'</div>'
        f'<span style="background: {theme["bg"]}; color: {theme["text"]}; border: 1px solid {theme["border"]}; '
        f'padding: 0.12rem 0.5rem; border-radius: 12px; font-size: 0.72rem; font-weight: 700; '
        f'display: inline-flex; align-items: center; gap: 0.25rem; box-shadow: 0 0 6px {theme["glow"]};">'
        f'{theme["icon"]} {state_label}'
        f'</span>'
        f'</div>'
        f'<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.55rem; margin-bottom: 0.42rem;">'
        f'<div>'
        f'<div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; color: #94A3B8; margin-bottom: 2px;">'
        f'<span>CPU: <strong style="color: {cpu_val_color};">{cpu_pct:.0f}%</strong></span>'
        f'</div>'
        f'<div style="background: rgba(255,255,255,0.08); border-radius: 4px; height: 5px; overflow: hidden;">'
        f'<div style="background: {cpu_bar_gradient}; width: {min(100.0, cpu_pct)}%; height: 100%; border-radius: 4px;"></div>'
        f'</div>'
        f'</div>'
        f'<div>'
        f'<div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; color: #94A3B8; margin-bottom: 2px;">'
        f'<span>RAM: <strong style="color: #A78BFA;">{ram_pct:.0f}%</strong></span>'
        f'</div>'
        f'<div style="background: rgba(255,255,255,0.08); border-radius: 4px; height: 5px; overflow: hidden;">'
        f'<div style="background: linear-gradient(90deg, #6366F1, #A855F7); width: {min(100.0, ram_pct)}%; height: 100%; border-radius: 4px;"></div>'
        f'</div>'
        f'</div>'
        f'</div>'
        f'<div style="display: flex; justify-content: space-between; align-items: center; '
        f'background: rgba(15, 23, 42, 0.65); border: 1px solid rgba(148, 163, 184, 0.12); '
        f'border-radius: 6px; padding: 0.25rem 0.5rem; font-size: 0.72rem; margin-bottom: 0.42rem;">'
        f'<span style="color: #94A3B8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 70%;" title="{active_desc}">'
        f'⚡ <span style="color: {"#34D399" if server.active_request else "#94A3B8"}; font-weight: 600;">{active_desc}</span>'
        f'</span>'
        f'<span style="background: {q_bg}; color: {q_color}; border: 1px solid {q_border}; '
        f'border-radius: 6px; padding: 0.05rem 0.4rem; font-weight: 700; font-size: 0.68rem;">'
        f'Q: {q_len}'
        f'</span>'
        f'</div>'
        f'<div style="display: flex; justify-content: space-between; align-items: center; '
        f'color: #94A3B8; font-size: 0.71rem; border-top: 1px solid rgba(148, 163, 184, 0.12); padding-top: 0.32rem;">'
        f'<span>Done: <strong style="color: #38BDF8;">{len(server.completed_requests)}</strong></span>'
        f'<span>Retried: <strong style="color: {"#F59E0B" if retried_count > 0 else "#94A3B8"};">{retried_count}</strong></span>'
        f'<span>Lost: <strong style="color: {"#EF4444" if lost_ms > 0 else "#94A3B8"};">{lost_ms:.0f}ms</strong></span>'
        f'</div>'
        f'</div>'
    )


def render_compact_server_blade(server: CloudServer) -> None:
    """Render an ultra-compact horizontal cloud node blade card (Height ~130px)."""
    blade_html = build_blade_card_html(server)
    _safe_render_html(blade_html)


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
            label_visibility="collapsed",
        )

    if not servers:
        st.info("No servers currently active in the cluster.")
        return

    if view_mode == "🎛️ Compact Server Blades":
        cards_html = "".join([build_blade_card_html(srv) for srv in servers])
        grid_html = (
            f'<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); '
            f'gap: 0.75rem; margin-top: 0.35rem; margin-bottom: 0.6rem; align-items: stretch;">'
            f'{cards_html}'
            f'</div>'
        )
        _safe_render_html(grid_html)

    else:
        # High-density Matrix Table View (takes only ~120px total height)
        rows = []
        for s in servers:
            theme = STATE_COLORS.get(s.state, STATE_COLORS[ServerState.HEALTHY])
            active_info = (
                f"{s.active_request.request_id} ({s.active_request.processing_time_ms:.0f}ms)"
                if s.active_request
                else "Idle"
            )
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
                "Lost Work": f"{s.total_lost_work_ms:.0f} ms",
            })
        df_matrix = pd.DataFrame(rows)
        st.dataframe(df_matrix, use_container_width=True, height=135)
