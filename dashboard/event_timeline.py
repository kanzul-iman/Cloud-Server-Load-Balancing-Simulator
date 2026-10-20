"""
Event Timeline Component for Cloud Chaos Lab.
Renders real-time, timestamped simulation event logs with severity tags,
search filters, and audit trail inspection.
"""

from typing import List
import streamlit as st
from simulator.event_logger import EventLogger, EventSeverity, LogEntry


SEVERITY_STYLES = {
    EventSeverity.CRITICAL: {"bg": "rgba(239, 68, 68, 0.2)", "border": "#EF4444", "color": "#FCA5A5", "icon": "🚨"},
    EventSeverity.WARNING: {"bg": "rgba(245, 158, 11, 0.2)", "border": "#F59E0B", "color": "#FCD34D", "icon": "⚠️"},
    EventSeverity.SUCCESS: {"bg": "rgba(16, 185, 129, 0.2)", "border": "#10B981", "color": "#6EE7B7", "icon": "✔"},
    EventSeverity.INFO: {"bg": "rgba(56, 189, 248, 0.15)", "border": "#38BDF8", "color": "#BAE6FD", "icon": "ℹ️"},
}


def render_event_timeline(logger: EventLogger) -> None:
    """Render the chronological simulation event timeline."""
    st.markdown("### 📜 Live Disaster & Recovery Audit Timeline")
    entries = logger.get_entries()

    if not entries:
        st.info("No simulation events logged yet. Start or step the simulation to view events.")
        return

    # Filter Controls
    f_col1, f_col2 = st.columns([2, 3])
    with f_col1:
        sev_filter = st.selectbox(
            "Filter by Severity:",
            options=["All Events", "Warnings & Failures Only", "Success & Normal Only"],
            index=0
        )
    with f_col2:
        search_kw = st.text_input("Search Event Description:", value="", placeholder="e.g. Server 2, retry, crash").strip().lower()

    # Apply filters
    filtered_entries = list(entries)
    if sev_filter == "Warnings & Failures Only":
        filtered_entries = [e for e in filtered_entries if e.severity in (EventSeverity.WARNING, EventSeverity.CRITICAL)]
    elif sev_filter == "Success & Normal Only":
        filtered_entries = [e for e in filtered_entries if e.severity in (EventSeverity.INFO, EventSeverity.SUCCESS)]

    if search_kw:
        filtered_entries = [e for e in filtered_entries if search_kw in e.description.lower() or search_kw in e.source.lower()]

    st.caption(f"Showing **{len(filtered_entries)}** of {len(entries)} events (latest events at top):")

    # Render latest first
    reversed_entries = list(reversed(filtered_entries))[:80]  # Display up to latest 80 events

    timeline_items = []
    for e in reversed_entries:
        style = SEVERITY_STYLES.get(e.severity, SEVERITY_STYLES[EventSeverity.INFO])
        item_html = f"""
        <div style="
            background: rgba(30, 41, 59, 0.55);
            border-left: 4px solid {style['border']};
            border-radius: 0 8px 8px 0;
            padding: 0.5rem 0.85rem;
            margin-bottom: 0.45rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 0.83rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.6rem;">
                <span style="font-family: monospace; color: #94A3B8; font-size: 0.76rem; background: rgba(15, 23, 42, 0.6); padding: 0.15rem 0.4rem; border-radius: 4px;">
                    {e.sim_time_str}
                </span>
                <span style="
                    background: {style['bg']};
                    color: {style['color']};
                    border: 1px solid {style['border']};
                    border-radius: 12px;
                    padding: 0.1rem 0.5rem;
                    font-size: 0.72rem;
                    font-weight: 700;
                ">
                    {style['icon']} {e.severity.value}
                </span>
                <strong style="color: #F8FAFC; margin-left: 0.2rem;">[{e.source}]</strong>
                <span style="color: #CBD5E1;">{e.description}</span>
            </div>
        </div>
        """
        timeline_items.append(item_html)

    timeline_container = f"""
    <div style="
        max-height: 380px;
        overflow-y: auto;
        padding-right: 0.5rem;
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 10px;
        padding: 0.75rem;
        background: rgba(15, 23, 42, 0.4);
    ">
        {''.join(timeline_items)}
    </div>
    """
    st.markdown(timeline_container, unsafe_allow_html=True)
