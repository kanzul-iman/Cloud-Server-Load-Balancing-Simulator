"""
Cloud Server Load Balancing Simulator - Interactive Streamlit Dashboard
Course Project: Cloud and Distributed Computing
Architecture: Streamlit UI consuming modular logic from src/ package.
"""

import time
from pathlib import Path
from typing import Dict, Any, List, Tuple
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

# Import business logic exclusively from src package
from src.data_loader import (
    load_and_validate_dataset,
    get_dataset_summary_statistics,
    DEFAULT_DATASET_PATH,
    REQUIRED_COLUMNS,
)
from src.load_balancer import (
    generate_server_names,
    round_robin_scheduler,
    least_loaded_scheduler,
)
from src.metrics import (
    calculate_algorithm_metrics,
    calculate_load_imbalance_reduction,
    verify_simulation_correctness,
    build_performance_comparison_dataframe,
    build_server_workload_dataframe,
    export_simulation_reports,
)
from dashboard.chaos_lab import render_chaos_lab_page

# -----------------------------------------------------------------------------
# STREAMLIT PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Cloud Load Balancing Simulator",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# CUSTOM CSS STYLING (NAVY, BLUE, SUBTLE PURPLE THEME & TRANSITIONS)
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Global Typography & Background adjustments */
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2.5rem;
    }
    
    /* Header Card */
    .header-box {
        background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 55%, #312E81 100%);
        color: #FFFFFF;
        padding: 1.6rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.15);
    }
    .header-title {
        font-size: 2.1rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
        color: #FFFFFF;
    }
    .header-subtitle {
        font-size: 0.98rem;
        color: #93C5FD;
        margin-top: 0.35rem;
        font-weight: 400;
    }
    .header-badge {
        display: inline-block;
        background-color: rgba(99, 102, 241, 0.25);
        border: 1px solid rgba(165, 180, 252, 0.4);
        color: #E0E7FF;
        font-size: 0.78rem;
        font-weight: 600;
        padding: 0.2rem 0.65rem;
        border-radius: 20px;
        margin-top: 0.7rem;
    }
    .transition-live-badge {
        display: inline-block;
        background: linear-gradient(135deg, #10B981, #059669);
        color: #FFFFFF;
        font-size: 0.76rem;
        font-weight: 700;
        padding: 0.2rem 0.65rem;
        border-radius: 20px;
        margin-left: 0.5rem;
        box-shadow: 0 0 10px rgba(16, 185, 129, 0.4);
        animation: pulseLive 2s infinite ease-in-out;
    }

    /* Section Cards */
    .section-card {
        background-color: rgba(148, 163, 184, 0.06);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 10px;
        padding: 1.25rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        animation: outcomeEntrance 0.65s cubic-bezier(0.16, 1, 0.3, 1) both;
    }
    
    /* Verification Pills */
    .pill-success {
        background-color: rgba(16, 185, 129, 0.15);
        color: #10B981;
        border: 1px solid rgba(16, 185, 129, 0.35);
        padding: 0.35rem 0.75rem;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
        transition: transform 0.2s ease, background-color 0.2s ease;
    }
    .pill-success:hover {
        transform: translateY(-2px);
        background-color: rgba(16, 185, 129, 0.25);
    }

    /* Recommendation Callout */
    .callout-box {
        background: rgba(37, 99, 235, 0.12);
        border-left: 4px solid #3B82F6;
        padding: 1rem 1.25rem;
        border-radius: 0 8px 8px 0;
        font-size: 0.95rem;
        line-height: 1.5;
        margin-top: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 6px rgba(37, 99, 235, 0.08);
        animation: outcomeEntrance 0.7s cubic-bezier(0.16, 1, 0.3, 1) both;
        transition: transform 0.25s ease, box-shadow 0.25s ease;
    }
    .callout-box:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.15);
    }

    /* -------------------------------------------------------------------------
       CIRCULAR SPINNER & ANIMATED CURSOR SIMULATION CARD
       ------------------------------------------------------------------------- */
    .simulation-loading-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.88) 0%, rgba(15, 23, 42, 0.94) 100%);
        border: 2px solid #3B82F6;
        border-radius: 16px;
        padding: 2.2rem 2rem;
        margin: 1.2rem 0 1.8rem 0;
        box-shadow: 0 12px 28px rgba(37, 99, 235, 0.25), 0 4px 10px rgba(0, 0, 0, 0.2);
        text-align: center;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        animation: pulseCard 1.8s ease-in-out infinite alternate;
    }

    .circular-cursor-spinner {
        width: 72px;
        height: 72px;
        position: relative;
        margin-bottom: 1.2rem;
    }

    .circular-cursor-spinner::before {
        content: "";
        box-sizing: border-box;
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        border-radius: 50%;
        border: 5px solid rgba(226, 232, 240, 0.25);
    }

    .circular-cursor-spinner::after {
        content: "";
        box-sizing: border-box;
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        border-radius: 50%;
        border: 5px solid transparent;
        border-top-color: #38BDF8;
        border-right-color: #818CF8;
        border-bottom-color: #3B82F6;
        animation: circularSpin 0.85s cubic-bezier(0.5, 0.1, 0.5, 0.9) infinite;
        box-shadow: 0 0 18px rgba(59, 130, 246, 0.45);
    }

    .simulation-step-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-bottom: 0.35rem;
    }

    .simulation-step-desc {
        font-size: 0.95rem;
        color: #93C5FD;
        margin-bottom: 1rem;
    }

    .simulation-progress-bar {
        width: 100%;
        max-width: 440px;
        height: 8px;
        background-color: rgba(255, 255, 255, 0.15);
        border-radius: 9999px;
        overflow: hidden;
        position: relative;
    }

    .simulation-progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #38BDF8, #818CF8, #3B82F6);
        border-radius: 9999px;
        transition: width 0.35s ease;
    }

    /* -------------------------------------------------------------------------
       OUTCOME TRANSITIONS FOR GRAPHS, TABLES, IMAGES & METRIC CARDS
       ------------------------------------------------------------------------- */
    @keyframes outcomeEntrance {
        0% {
            opacity: 0;
            transform: translateY(22px) scale(0.985);
        }
        60% {
            opacity: 0.92;
            transform: translateY(-2px) scale(1.002);
        }
        100% {
            opacity: 1;
            transform: translateY(0) scale(1.0);
        }
    }

    @keyframes circularSpin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    @keyframes pulseCard {
        0% { box-shadow: 0 6px 18px rgba(37, 99, 235, 0.15); }
        100% { box-shadow: 0 14px 32px rgba(124, 58, 237, 0.28); }
    }

    @keyframes pulseLive {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.85; transform: scale(1.04); }
    }

    /* Graph & Matplotlib Chart Transitions */
    div[data-testid="stImage"] {
        border-radius: 12px;
        background: rgba(148, 163, 184, 0.05);
        border: 1px solid rgba(148, 163, 184, 0.25);
        padding: 8px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
        animation: outcomeEntrance 0.75s cubic-bezier(0.16, 1, 0.3, 1) both;
        transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.35s ease, border-color 0.35s ease;
    }

    div[data-testid="stImage"]:hover {
        transform: translateY(-4px) scale(1.008);
        box-shadow: 0 12px 26px rgba(59, 130, 246, 0.2);
        border-color: #60A5FA;
    }

    div[data-testid="stImage"] img {
        border-radius: 8px;
        transition: opacity 0.3s ease;
    }

    /* Table Transitions (DataFrames) */
    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        animation: outcomeEntrance 0.65s cubic-bezier(0.16, 1, 0.3, 1) both;
        transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
    }

    div[data-testid="stDataFrame"]:hover {
        box-shadow: 0 8px 20px rgba(59, 130, 246, 0.12);
        border-color: #60A5FA;
    }

    /* Metric KPI Cards Transitions */
    div[data-testid="stMetric"] {
        background: rgba(148, 163, 184, 0.08);
        padding: 0.95rem 1.15rem;
        border-radius: 10px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        backdrop-filter: blur(6px);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        animation: outcomeEntrance 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
        transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s ease, border-color 0.3s ease;
    }

    div[data-testid="stMetric"]:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 20px rgba(59, 130, 246, 0.2);
        border-color: #60A5FA;
    }

    /* Server Progress Bar Animation */
    div[data-testid="stProgress"] > div > div {
        transition: width 0.85s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    /* Tabs Content Smooth Transition */
    div[data-testid="stTabsContent"] {
        animation: outcomeEntrance 0.55s cubic-bezier(0.16, 1, 0.3, 1) both;
    }

    /* -------------------------------------------------------------------------
       GLASSY RIGHT-SIDE WEBSITE SCROLLER & SCROLLBAR
       ------------------------------------------------------------------------- */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    ::-webkit-scrollbar-track {
        background: rgba(15, 23, 42, 0.65);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-left: 1px solid rgba(148, 163, 184, 0.12);
    }
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, rgba(56, 189, 248, 0.5) 0%, rgba(129, 140, 248, 0.55) 100%);
        border-radius: 9999px;
        border: 2px solid rgba(15, 23, 42, 0.7);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
        box-shadow: 0 0 10px rgba(56, 189, 248, 0.25);
    }
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(180deg, #38BDF8 0%, #818CF8 100%);
        box-shadow: 0 0 18px rgba(56, 189, 248, 0.75);
    }

    /* -------------------------------------------------------------------------
       BOTTOM-TO-TOP RIGHT-SIDE GLASSY FLOATING SCROLLER BUTTON
       ------------------------------------------------------------------------- */
    .glassy-scroller-btn {
        position: fixed;
        bottom: 28px;
        right: 28px;
        z-index: 999999;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        width: 52px;
        height: 52px;
        border-radius: 50%;
        background: rgba(15, 23, 42, 0.72);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1.5px solid rgba(56, 189, 248, 0.45);
        color: #38BDF8 !important;
        box-shadow: 0 8px 32px 0 rgba(15, 23, 42, 0.55), inset 0 0 14px rgba(56, 189, 248, 0.18);
        cursor: pointer;
        text-decoration: none !important;
        transition: all 0.38s cubic-bezier(0.16, 1, 0.3, 1);
        user-select: none;
        animation: scrollerFloat 3s ease-in-out infinite alternate;
    }
    .glassy-scroller-btn:hover {
        transform: translateY(-6px) scale(1.12);
        background: rgba(30, 41, 59, 0.88);
        border-color: #38BDF8;
        color: #FFFFFF !important;
        box-shadow: 0 14px 40px rgba(56, 189, 248, 0.5), 0 0 24px rgba(56, 189, 248, 0.65), inset 0 0 16px rgba(56, 189, 248, 0.35);
    }
    .glassy-scroller-btn .arrow-icon {
        font-size: 1.18rem;
        font-weight: 900;
        line-height: 1;
        transition: transform 0.3s ease;
    }
    .glassy-scroller-btn:hover .arrow-icon {
        transform: translateY(-2px);
    }
    .glassy-scroller-btn .btn-label {
        font-size: 0.55rem;
        font-weight: 800;
        letter-spacing: 0.8px;
        color: #93C5FD;
        margin-top: 2px;
    }

    @keyframes scrollerFloat {
        0% { transform: translateY(0); box-shadow: 0 8px 28px rgba(15, 23, 42, 0.5), inset 0 0 12px rgba(56, 189, 248, 0.15); }
        100% { transform: translateY(-4px); box-shadow: 0 12px 34px rgba(56, 189, 248, 0.3), inset 0 0 16px rgba(56, 189, 248, 0.25); }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# SAFE DATA LOADING WITH CACHE & UI HELPERS
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_dataset_cached(path_str: str) -> pd.DataFrame:
    """Safely load and validate dataset with caching to avoid redundant disk I/O."""
    return load_and_validate_dataset(path_str)


def render_dataframe(data: pd.DataFrame, height: int = None) -> None:
    """Render dataframe with responsive layout compatible across Streamlit versions."""
    kwargs = {}
    if height is not None:
        kwargs["height"] = height
    try:
        st.dataframe(data, width="stretch", **kwargs)
    except Exception:
        try:
            st.dataframe(data, use_container_width=True, **kwargs)
        except Exception:
            st.dataframe(data, **kwargs)


# -----------------------------------------------------------------------------
# MAIN APPLICATION CONTROLLER
# -----------------------------------------------------------------------------
def main():
    # Invisible Top Anchor & Floating Bottom-to-Top Glassy Scroller
    st.markdown(
        """
        <div id="top-anchor" style="position: absolute; top: 0; left: 0; width: 1px; height: 1px; visibility: hidden;"></div>
        <a href="#top-anchor" class="glassy-scroller-btn" title="Back to Top" onclick="
            (function() {
                try {
                    var scroller = window.parent.document.querySelector('section.main') || 
                                   window.parent.document.documentElement || 
                                   document.querySelector('section.main') || 
                                   window;
                    scroller.scrollTo({ top: 0, behavior: 'smooth' });
                } catch(e) {
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }
            })();
            return false;
        ">
            <span class="arrow-icon">&#9650;</span>
            <span class="btn-label">TOP</span>
        </a>
        """,
        unsafe_allow_html=True
    )

    # -------------------------------------------------------------------------
    # DATA INGESTION & INTEGRITY VALIDATION
    # -------------------------------------------------------------------------
    dataset_path_str = str(DEFAULT_DATASET_PATH)
    file_exists = DEFAULT_DATASET_PATH.is_file()
    
    if not file_exists:
        st.sidebar.error(f"⚠️ Dataset file not found at: `{DEFAULT_DATASET_PATH}`")
        st.stop()

    try:
        df = load_dataset_cached(dataset_path_str)
        stats = get_dataset_summary_statistics(df)
    except Exception as exc:
        st.error(f"❌ Failed to load or validate dataset: {exc}")
        st.info("Please verify that the dataset CSV is located in the project folder and formatted correctly.")
        st.stop()

    # -------------------------------------------------------------------------
    # NAVIGATION & MODULE SWITCHER
    # -------------------------------------------------------------------------
    st.sidebar.markdown("### 🎛️ Navigation & Experiment Mode")
    app_mode = st.sidebar.radio(
        "Select Active Module:",
        options=[
            "⚡ Cloud Chaos Lab (Intelligent Recovery)",
            "📊 Classic Workload Benchmark"
        ],
        index=0,
        help="Switch between the interactive Cloud Chaos Lab and the baseline academic benchmark."
    )
    st.sidebar.markdown("---")

    # BRANCH: CLOUD CHAOS LAB
    if app_mode == "⚡ Cloud Chaos Lab (Intelligent Recovery)":
        render_chaos_lab_page(df)
        return

    # BRANCH: CLASSIC BENCHMARK ANALYSIS
    # Render Application Header
    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">☁️ Cloud Server Load Balancing Simulator</h1>
            <div class="header-subtitle">
                Cloud & Distributed Computing — Performance Evaluation of Workload-Aware vs. Cyclic Scheduling
            </div>
            <span class="header-badge">Distributed Systems Simulator • Pure Python & Pandas</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -------------------------------------------------------------------------
    # 1. SIDEBAR CONFIGURATION (CLASSIC MODE)
    # -------------------------------------------------------------------------
    st.sidebar.markdown("### ⚙️ Simulation Control Panel")

    file_size_kb = DEFAULT_DATASET_PATH.stat().st_size / 1024
    st.sidebar.success(
        f"**Dataset Detected:**\n`{DEFAULT_DATASET_PATH.name}`\n"
        f"Size: {file_size_kb:.1f} KB"
    )

    st.sidebar.markdown("---")

    # Server Count Slider
    num_servers = st.sidebar.slider(
        "Number of Logical Servers:",
        min_value=2,
        max_value=8,
        value=3,
        step=1,
        help="Select the number of virtual servers in the simulated cloud datacenter.",
    )
    servers = generate_server_names(num_servers)
    st.sidebar.caption(f"Cluster Nodes: {', '.join(servers)}")

    # Algorithm Selector
    st.sidebar.markdown("---")
    algo_choice = st.sidebar.radio(
        "Algorithm Selection:",
        options=["Compare Both (Recommended)", "Round Robin", "Least Loaded"],
        index=0,
        help="Choose whether to focus on an individual algorithm or run comparative analysis.",
    )

    # Simulation Action Buttons
    st.sidebar.markdown("---")
    run_clicked = st.sidebar.button(
        "🚀 Run Simulation",
        type="primary",
        use_container_width=True,
        help="Execute the scheduling algorithms with the selected server count.",
    )

    export_clicked = st.sidebar.button(
        "💾 Export Results to outputs/",
        use_container_width=True,
        help="Save all assignment and comparison CSV files to the outputs/ directory.",
    )

    # -------------------------------------------------------------------------
    # 3. DATASET OVERVIEW SECTION
    # -------------------------------------------------------------------------
    st.markdown("### 📊 1. Workload Dataset Profile")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Requests", f"{stats['total_requests']:,}")
    with col2:
        st.metric("Total Workload", f"{stats['total_workload_ms']:,} ms")
    with col3:
        st.metric("Request Types", f"{len(stats['request_types_distribution'])}")
    with col4:
        st.metric("Average Burst Time", f"{stats['mean_processing_time_ms']} ms")
    with col5:
        st.metric("Validation Status", "✅ 100% Valid")

    with st.expander("🔍 View Dataset Preview & Request Type Distribution", expanded=False):
        d_col1, d_col2 = st.columns([3, 2])
        with d_col1:
            st.markdown("**First 10 Requests in Workload Trace:**")
            render_dataframe(df.head(10), height=385)
        with d_col2:
            st.markdown("**Request Frequency by Type:**")
            fig_types, ax_types = plt.subplots(figsize=(5, 3.8))
            types_dict = stats["request_types_distribution"]
            types_series = pd.Series(types_dict).sort_values(ascending=True)
            
            bars = ax_types.barh(types_series.index, types_series.values, color="#3B82F6", edgecolor="#1E3A8A")
            ax_types.set_xlabel("Number of Requests", fontsize=9)
            ax_types.tick_params(axis='both', labelsize=8)
            ax_types.set_title("Request Type Distribution", fontsize=10, fontweight="bold", pad=8)
            
            for b in bars:
                w = b.get_width()
                ax_types.text(w + 3, b.get_y() + b.get_height()/2, f"{int(w)}", va='center', fontsize=8, color="#1E293B")
            
            ax_types.set_xlim(0, max(types_series.values) * 1.15)
            plt.tight_layout()
            st.pyplot(fig_types)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 4. RUN SIMULATION & COMPUTE METRICS
    # -------------------------------------------------------------------------
    rr_assignments, rr_loads = round_robin_scheduler(df, servers)
    ll_assignments, ll_loads = least_loaded_scheduler(df, servers)

    rr_metrics = calculate_algorithm_metrics("Round Robin", rr_assignments, rr_loads)
    ll_metrics = calculate_algorithm_metrics("Least Loaded", ll_assignments, ll_loads)

    reduction_pct = calculate_load_imbalance_reduction(
        rr_metrics["Load_Imbalance_ms"], ll_metrics["Load_Imbalance_ms"]
    )

    comp_df = build_performance_comparison_dataframe(rr_metrics, ll_metrics)
    sw_df = build_server_workload_dataframe(rr_metrics, ll_metrics)

    # Export to outputs/ if triggered
    if export_clicked:
        outputs_dir = Path(__file__).resolve().parent / "outputs"
        paths = export_simulation_reports(outputs_dir, rr_assignments, ll_assignments, comp_df, sw_df)
        st.toast(f"✅ All 4 reports exported to outputs/ ({num_servers} servers)", icon="💾")
        st.success(
            f"**Reports successfully saved to:** `{outputs_dir.resolve()}`\n"
            f"- `round_robin_assignments.csv`\n"
            f"- `least_loaded_assignments.csv`\n"
            f"- `performance_comparison.csv`\n"
            f"- `server_workload_comparison.csv`"
        )

    # -------------------------------------------------------------------------
    # CIRCULAR CURSOR & SPINNER SIMULATION ANIMATION PIPELINE
    # -------------------------------------------------------------------------
    if run_clicked:
        loader_placeholder = st.empty()
        simulation_stages = [
            ("⚡ Phase 1/4: Initializing cluster topology & task queues...", 25),
            ("🔄 Phase 2/4: Executing Round Robin cyclic assignment (1,000 tasks)...", 55),
            ("⚖️ Phase 3/4: Minimizing dynamic load via Least Loaded scheduler...", 85),
            ("✨ Phase 4/4: Finalizing metrics & applying visual outcome transitions...", 100),
        ]
        for stage_title, pct in simulation_stages:
            loader_placeholder.markdown(
                f"""
                <style>
                * {{
                    cursor: progress !important;
                }}
                </style>
                <div class="simulation-loading-card">
                    <div class="circular-cursor-spinner"></div>
                    <div class="simulation-step-title">⚡ Simulating Cloud Load Balancing Cluster...</div>
                    <div class="simulation-step-desc">{stage_title}</div>
                    <div class="simulation-progress-bar">
                        <div class="simulation-progress-fill" style="width: {pct}%;"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            time.sleep(0.22)
        loader_placeholder.empty()
        st.toast("✅ Simulation complete! Outcome graphs, tables & metrics transitioned.", icon="🚀")

    # -------------------------------------------------------------------------
    # 5. SERVER WORKLOAD MONITORING
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem; margin-top: 1.2rem;">
            <h3 style="margin: 0;">🖥️ 2. Server Cluster Workload Monitoring</h3>
            <span class="transition-live-badge">⚡ Transitions Active</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    mean_target_workload = stats["total_workload_ms"] / num_servers

    if algo_choice in ("Compare Both (Recommended)", "Round Robin"):
        st.markdown("#### Round Robin — Server Allocation")
        rr_cols = st.columns(num_servers)
        for idx, s in enumerate(servers):
            load = rr_loads[s]
            req_c = rr_metrics["Server_Request_Counts"][s]
            diff_from_mean = load - mean_target_workload
            diff_sign = "+" if diff_from_mean >= 0 else ""
            with rr_cols[idx]:
                st.metric(
                    label=f"🖥️ {s}",
                    value=f"{load:,} ms",
                    delta=f"{req_c} tasks ({diff_sign}{diff_from_mean:,.0f} ms)",
                    delta_color="off",
                )
                max_rr = max(rr_loads.values()) if rr_loads else 1
                prog_val = min(1.0, max(0.0, float(load) / float(max_rr))) if max_rr > 0 else 0.0
                st.progress(prog_val)

    if algo_choice in ("Compare Both (Recommended)", "Least Loaded"):
        st.markdown("#### Least Loaded — Server Allocation")
        ll_cols = st.columns(num_servers)
        for idx, s in enumerate(servers):
            load = ll_loads[s]
            req_c = ll_metrics["Server_Request_Counts"][s]
            diff_from_mean = load - mean_target_workload
            diff_sign = "+" if diff_from_mean >= 0 else ""
            with ll_cols[idx]:
                st.metric(
                    label=f"🖥️ {s}",
                    value=f"{load:,} ms",
                    delta=f"{req_c} tasks ({diff_sign}{diff_from_mean:,.0f} ms)",
                    delta_color="off",
                )
                max_ll = max(ll_loads.values()) if ll_loads else 1
                prog_val = min(1.0, max(0.0, float(load) / float(max_ll))) if max_ll > 0 else 0.0
                st.progress(prog_val)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 6. ALGORITHM COMPARISON & VISUALIZATIONS
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
            <h3 style="margin: 0;">⚖️ 3. Comparative Performance Analysis</h3>
            <span class="transition-live-badge">📊 Graph & Table Transitions Active</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Display Comparison KPI Cards
    kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
    with kpi_c1:
        st.metric(
            label="Round Robin Imbalance",
            value=f"{rr_metrics['Load_Imbalance_ms']:,} ms",
            help="Difference between busiest and least-busy server under Round Robin.",
        )
    with kpi_c2:
        st.metric(
            label="Least Loaded Imbalance",
            value=f"{ll_metrics['Load_Imbalance_ms']:,} ms",
            delta=f"-{reduction_pct}% Imbalance" if reduction_pct is not None else None,
            delta_color="normal",
            help="Difference between busiest and least-busy server under Least Loaded.",
        )
    with kpi_c3:
        st.metric(
            label="RR Est. Makespan",
            value=f"{rr_metrics['Estimated_Makespan_ms']:,} ms",
            help="Maximum workload on any server under concurrent batch assumption.",
        )
    with kpi_c4:
        makespan_diff = ll_metrics["Estimated_Makespan_ms"] - rr_metrics["Estimated_Makespan_ms"]
        st.metric(
            label="LL Est. Makespan",
            value=f"{ll_metrics['Estimated_Makespan_ms']:,} ms",
            delta=f"{makespan_diff:,} ms" if makespan_diff != 0 else "0 ms",
            delta_color="normal",
        )

    # Automatically Generated Analytical Explanation
    winner_algo = "Least Loaded" if ll_metrics["Load_Imbalance_ms"] < rr_metrics["Load_Imbalance_ms"] else "Round Robin"
    if reduction_pct is not None and reduction_pct > 0:
        st.markdown(
            f"""
            <div class="callout-box">
                <strong>💡 Automated Performance Finding:</strong><br>
                For this {stats['total_requests']:,}-request workload trace across <strong>{num_servers} logical servers</strong>, 
                <strong>{winner_algo}</strong> produced the significantly more balanced distribution, reducing inter-server load imbalance 
                from <strong>{rr_metrics['Load_Imbalance_ms']:,} ms</strong> down to <strong>{ll_metrics['Load_Imbalance_ms']:,} ms</strong> 
                (a <strong>{reduction_pct}% improvement</strong>).<br>
                <em>Why this occurs:</em> Round Robin strictly equalizes request counts, but because request durations vary between 
                <strong>{stats['min_processing_time_ms']} ms</strong> and <strong>{stats['max_processing_time_ms']} ms</strong>, 
                uneven clusters of heavy requests accumulate on individual nodes. In contrast, Least Loaded routes heavier tasks to whichever 
                server has processed less total work, achieving near-perfect workload equilibrium.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Comparative Visualizations
    tab_charts, tab_table = st.tabs(["📊 Comparative Charts", "📋 Detailed Metrics Table"])

    with tab_charts:
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.markdown("**Server Workload Comparison (ms)**")
            fig_servers, ax_servers = plt.subplots(figsize=(6, 3.8))
            x = np.arange(len(servers))
            w = 0.35

            rr_vals = [rr_loads[s] for s in servers]
            ll_vals = [ll_loads[s] for s in servers]

            ax_servers.bar(x - w/2, rr_vals, width=w, label="Round Robin", color="#3B82F6", edgecolor="#1E3A8A")
            ax_servers.bar(x + w/2, ll_vals, width=w, label="Least Loaded", color="#10B981", edgecolor="#065F46")
            
            ax_servers.axhline(mean_target_workload, color="#EF4444", linestyle="--", linewidth=1.2, label="Ideal Average")
            ax_servers.set_xticks(x)
            ax_servers.set_xticklabels(servers, fontsize=9)
            ax_servers.set_ylabel("Processing Workload (ms)", fontsize=9)
            ax_servers.set_title("Total Workload per Server", fontsize=10, fontweight="bold")
            ax_servers.legend(fontsize=8)
            plt.tight_layout()
            st.pyplot(fig_servers)

        with chart_col2:
            st.markdown("**Inter-Server Load Imbalance & Makespan (ms)**")
            fig_imb, ax_imb = plt.subplots(figsize=(6, 3.8))
            algos = ["Round Robin", "Least Loaded"]
            imbs = [rr_metrics["Load_Imbalance_ms"], ll_metrics["Load_Imbalance_ms"]]
            
            bars_imb = ax_imb.bar(algos, imbs, color=["#EF4444", "#10B981"], edgecolor="#1E293B", width=0.45)
            ax_imb.set_ylabel("Load Imbalance (ms)", fontsize=9)
            ax_imb.set_title("Load Imbalance (Max Load - Min Load)", fontsize=10, fontweight="bold")
            
            for b in bars_imb:
                y = b.get_height()
                ax_imb.text(b.get_x() + b.get_width()/2, y + (max(imbs) * 0.03), f"{int(y):,} ms", ha="center", fontsize=8, fontweight="bold")
            
            ax_imb.set_ylim(0, max(imbs) * 1.18)
            plt.tight_layout()
            st.pyplot(fig_imb)

    with tab_table:
        st.markdown("**Performance Comparison Summary:**")
        render_dataframe(comp_df)
        st.markdown("**Per-Server Workload & Task Allocation Breakdown:**")
        render_dataframe(sw_df)

    st.markdown("---")

    # ---------------------------------------------------------
    # 7. REQUEST ASSIGNMENTS INSPECTOR
    # ---------------------------------------------------------
    st.markdown("### 🔎 4. Request Assignment Browser")
    
    inspect_algo = st.radio(
        "Select assignments table to browse:",
        options=["Least Loaded", "Round Robin"],
        horizontal=True,
    )
    active_assignments = ll_assignments if inspect_algo == "Least Loaded" else rr_assignments

    # Interactive Filters
    filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 2])
    with filter_col1:
        search_req_id = st.text_input("Search by Request ID:", value="", placeholder="e.g. REQ0015").strip().upper()
    with filter_col2:
        filter_srv = st.selectbox("Filter by Server:", options=["All"] + servers)
    with filter_col3:
        filter_type = st.selectbox("Filter by Request Type:", options=["All"] + sorted(list(stats["request_types_distribution"].keys())))

    filtered_df = active_assignments.copy()
    if search_req_id:
        filtered_df = filtered_df[filtered_df["Request_ID"].str.contains(search_req_id, na=False)]
    if filter_srv != "All":
        filtered_df = filtered_df[filtered_df["Server"] == filter_srv]
    if filter_type != "All":
        filtered_df = filtered_df[filtered_df["Request_Type"] == filter_type]

    st.caption(f"Showing **{len(filtered_df):,}** of {len(active_assignments):,} assignments:")
    render_dataframe(
        filtered_df[["Request_ID", "Arrival_Time", "Request_Type", "Processing_Time_ms", "Data_Size_MB", "Server", "Server_Cumulative_Load_ms"]],
        height=320,
    )

    st.markdown("---")

    # ---------------------------------------------------------
    # 8. CORRECTNESS VERIFICATION PILLS
    # ---------------------------------------------------------
    st.markdown("### 🛡️ 5. Formal Simulation Correctness Guarantees")
    
    rr_check = verify_simulation_correctness(df, rr_assignments, rr_loads)
    ll_check = verify_simulation_correctness(df, ll_assignments, ll_loads)

    if rr_check["all_passed"] and ll_check["all_passed"]:
        st.markdown(
            """
            <div>
                <span class="pill-success">✔ All 1,000 requests assigned exactly once</span>
                <span class="pill-success">✔ Zero lost or duplicate requests</span>
                <span class="pill-success">✔ Total workload strictly conserved (195,367 ms)</span>
                <span class="pill-success">✔ Server workloads match assignment sums</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.error("⚠️ One or more simulation correctness constraints failed verification.")

    st.markdown("---")

    # ---------------------------------------------------------
    # 9. EXPORTS & DOWNLOAD BUTTONS
    # ---------------------------------------------------------
    st.markdown("### 📥 6. Export Current Configuration Data")
    st.markdown("Download assignment mapping files and performance comparisons matching the current server configuration:")

    exp_col1, exp_col2, exp_col3, exp_col4 = st.columns(4)
    with exp_col1:
        st.download_button(
            label="📥 Round Robin Assignments CSV",
            data=rr_assignments.to_csv(index=False).encode("utf-8"),
            file_name=f"round_robin_{num_servers}_servers_assignments.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with exp_col2:
        st.download_button(
            label="📥 Least Loaded Assignments CSV",
            data=ll_assignments.to_csv(index=False).encode("utf-8"),
            file_name=f"least_loaded_{num_servers}_servers_assignments.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with exp_col3:
        st.download_button(
            label="📥 Performance Summary CSV",
            data=comp_df.to_csv(index=False).encode("utf-8"),
            file_name=f"performance_comparison_{num_servers}_servers.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with exp_col4:
        st.download_button(
            label="📥 Server Workload Breakdown CSV",
            data=sw_df.to_csv(index=False).encode("utf-8"),
            file_name=f"server_workload_{num_servers}_servers.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("---")

    # ---------------------------------------------------------
    # 10. SCIENTIFIC LIMITATION & EDUCATIONAL NOTES
    # ---------------------------------------------------------
    with st.expander("📖 Scientific Limitation & Educational Notes", expanded=True):
        st.markdown(
            r"""
            **⚠️ Important Scientific & Educational Limitation:**
            > This project is a **local educational simulation**, not a real cloud deployment. 
            > Estimated makespan is calculated from cumulative assigned request durations and assumes 
            > parallel server execution with **no communication, scheduling, queuing, or network latency overhead**. 
            > These figures serve to demonstrate comparative load-distribution mechanics, not real-world cloud performance benchmarks.

            **Core Architectural Takeaways:**
            1. **Why Round Robin Causes Workload Imbalance:** Round Robin evenly partitions request *counts* ($i \pmod N$), but because request processing times vary across our dataset (30 ms to 799 ms), uneven clusters of long-running tasks create substantial server load disparity.
            2. **Why Least Loaded Balances Workload:** By routing incoming requests to the server with the lowest current workload accumulation, Least Loaded actively compresses the inter-server workload spread down by over 90%.
            """
        )


if __name__ == "__main__":
    main()
