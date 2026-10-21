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
    validate_request_inputs,
    assign_single_request,
)
from src.metrics import (
    calculate_algorithm_metrics,
    calculate_load_imbalance_reduction,
    verify_simulation_correctness,
    build_performance_comparison_dataframe,
    build_server_workload_dataframe,
    export_simulation_reports,
)
import importlib
import dashboard.cluster_monitor
import dashboard.chaos_lab
importlib.reload(dashboard.cluster_monitor)
importlib.reload(dashboard.chaos_lab)
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
    /* -------------------------------------------------------------------------
       1. GLOBAL TYPOGRAPHY, CONTAINER & FLUID SPACING
       ------------------------------------------------------------------------- */
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2.5rem;
        max-width: 1400px;
    }
    @media (max-width: 768px) {
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
        }
    }
    
    /* -------------------------------------------------------------------------
       2. RESPONSIVE HEADER BOX
       ------------------------------------------------------------------------- */
    .header-box {
        background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 55%, #312E81 100%);
        color: #FFFFFF;
        padding: clamp(1.2rem, 3vw, 2rem);
        border-radius: 14px;
        margin-bottom: 1.25rem;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.25);
        border: 1px solid rgba(99, 102, 241, 0.3);
    }
    .header-title {
        font-size: clamp(1.4rem, 4vw, 2.2rem);
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
        color: #FFFFFF;
        line-height: 1.25;
    }
    .header-subtitle {
        font-size: clamp(0.85rem, 2vw, 1.02rem);
        color: #93C5FD;
        margin-top: 0.45rem;
        font-weight: 400;
        line-height: 1.5;
    }
    .header-badge-container {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        align-items: center;
        margin-top: 0.85rem;
    }
    .header-badge {
        display: inline-block;
        background-color: rgba(99, 102, 241, 0.25);
        border: 1px solid rgba(165, 180, 252, 0.4);
        color: #E0E7FF;
        font-size: 0.76rem;
        font-weight: 600;
        padding: 0.22rem 0.65rem;
        border-radius: 20px;
    }
    .transition-live-badge {
        display: inline-block;
        background: linear-gradient(135deg, #10B981, #059669);
        color: #FFFFFF;
        font-size: 0.74rem;
        font-weight: 700;
        padding: 0.22rem 0.65rem;
        border-radius: 20px;
        box-shadow: 0 0 10px rgba(16, 185, 129, 0.4);
        animation: pulseLive 2s infinite ease-in-out;
    }

    /* -------------------------------------------------------------------------
       3. INTERACTIVE QUICK JUMP NAVIGATION BAR
       ------------------------------------------------------------------------- */
    .quick-nav-bar {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        overflow-x: auto;
        padding: 0.55rem 0.75rem;
        margin-bottom: 1.4rem;
        background: rgba(15, 23, 42, 0.68);
        border: 1px solid rgba(148, 163, 184, 0.22);
        border-radius: 12px;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        -webkit-overflow-scrolling: touch;
        scrollbar-width: thin;
    }
    .quick-nav-label {
        font-size: 0.76rem;
        font-weight: 700;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        white-space: nowrap;
        margin-right: 0.25rem;
    }
    .quick-nav-pill {
        display: inline-flex;
        align-items: center;
        background: rgba(30, 41, 59, 0.75);
        color: #93C5FD !important;
        border: 1px solid rgba(59, 130, 246, 0.25);
        padding: 0.25rem 0.7rem;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        text-decoration: none !important;
        white-space: nowrap;
        transition: all 0.22s ease;
    }
    .quick-nav-pill:hover {
        background: #1E3A8A;
        color: #FFFFFF !important;
        border-color: #38BDF8;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(56, 189, 248, 0.25);
    }

    /* -------------------------------------------------------------------------
       4. SECTION HEADERS & ANCHOR STYLES
       ------------------------------------------------------------------------- */
    .section-header-box {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 1.5rem;
        margin-bottom: 0.4rem;
        padding-bottom: 0.35rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    }
    .section-header-title {
        font-size: clamp(1.15rem, 2.5vw, 1.45rem);
        font-weight: 700;
        margin: 0;
        color: #F8FAFC;
    }
    .section-header-desc {
        font-size: 0.86rem;
        color: #94A3B8;
        margin-top: -0.1rem;
        margin-bottom: 0.85rem;
        line-height: 1.45;
    }

    /* -------------------------------------------------------------------------
       5. RESPONSIVE COLUMNS & GRID WRAPPING
       ------------------------------------------------------------------------- */
    @media (max-width: 900px) {
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 0.65rem !important;
        }
        div[data-testid="column"] {
            min-width: calc(50% - 0.65rem) !important;
            flex: 1 1 calc(50% - 0.65rem) !important;
        }
    }
    @media (max-width: 580px) {
        div[data-testid="column"] {
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }
    }

    /* -------------------------------------------------------------------------
       6. METRIC KPI CARDS RESPONSIVENESS
       ------------------------------------------------------------------------- */
    div[data-testid="stMetric"] {
        background: rgba(148, 163, 184, 0.08);
        padding: clamp(0.7rem, 1.8vw, 1rem) clamp(0.85rem, 2vw, 1.2rem);
        border-radius: 10px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        backdrop-filter: blur(6px);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        animation: outcomeEntrance 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
        transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s ease, border-color 0.3s ease;
        min-width: 0;
        word-break: break-word;
        overflow-wrap: break-word;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 20px rgba(59, 130, 246, 0.2);
        border-color: #60A5FA;
    }
    div[data-testid="stMetricValue"] {
        font-size: clamp(1.05rem, 2.2vw, 1.65rem) !important;
        font-weight: 700 !important;
        line-height: 1.25 !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: clamp(0.72rem, 1.6vw, 0.86rem) !important;
        font-weight: 600 !important;
        color: #94A3B8 !important;
    }

    /* -------------------------------------------------------------------------
       7. SECTION CARDS & EDUCATIONAL CALLOUTS
       ------------------------------------------------------------------------- */
    .section-card {
        background-color: rgba(148, 163, 184, 0.06);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 10px;
        padding: 1.25rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        animation: outcomeEntrance 0.65s cubic-bezier(0.16, 1, 0.3, 1) both;
    }
    .callout-box {
        background: rgba(37, 99, 235, 0.12);
        border-left: 4px solid #3B82F6;
        padding: 1rem 1.25rem;
        border-radius: 0 8px 8px 0;
        font-size: clamp(0.85rem, 1.8vw, 0.95rem);
        line-height: 1.55;
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
    .edu-tip-box {
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid rgba(59, 130, 246, 0.28);
        border-left: 4px solid #38BDF8;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-size: 0.86rem;
        line-height: 1.5;
        margin-top: 0.6rem;
        margin-bottom: 0.8rem;
        color: #E2E8F0;
    }

    /* Verification Pills */
    .pill-success {
        background-color: rgba(16, 185, 129, 0.15);
        color: #10B981;
        border: 1px solid rgba(16, 185, 129, 0.35);
        padding: 0.35rem 0.75rem;
        border-radius: 6px;
        font-size: clamp(0.75rem, 1.6vw, 0.85rem);
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

    /* -------------------------------------------------------------------------
       8. CIRCULAR SPINNER & ANIMATED CURSOR SIMULATION CARD
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
       9. OUTCOME TRANSITIONS FOR GRAPHS, TABLES & METRIC CARDS
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
        max-width: 100%;
        height: auto;
    }

    /* Table Transitions (DataFrames) */
    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        animation: outcomeEntrance 0.65s cubic-bezier(0.16, 1, 0.3, 1) both;
        transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
        width: 100% !important;
        overflow-x: auto;
    }
    div[data-testid="stDataFrame"]:hover {
        box-shadow: 0 8px 20px rgba(59, 130, 246, 0.12);
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
       10. GLASSY SCROLLER & SCROLLBAR
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

    /* Floating scroller button */
    .glassy-scroller-btn {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 999999;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        width: 48px;
        height: 48px;
        border-radius: 50%;
        background: rgba(15, 23, 42, 0.72);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1.5px solid rgba(56, 189, 248, 0.45);
        color: #38BDF8 !important;
        box-shadow: 0 8px 32px 0 rgba(15, 23, 42, 0.55), inset 0 0 14px rgba(56, 189, 248, 0.18);
        cursor: pointer;
        text-decoration: none !important;
        transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
        user-select: none;
        animation: scrollerFloat 3s ease-in-out infinite alternate;
    }
    .glassy-scroller-btn:hover {
        transform: translateY(-5px) scale(1.1);
        background: rgba(30, 41, 59, 0.88);
        border-color: #38BDF8;
        color: #FFFFFF !important;
        box-shadow: 0 14px 40px rgba(56, 189, 248, 0.5), 0 0 24px rgba(56, 189, 248, 0.65), inset 0 0 16px rgba(56, 189, 248, 0.35);
    }
    .glassy-scroller-btn .arrow-icon {
        font-size: 1.05rem;
        font-weight: 900;
        line-height: 1;
    }
    .glassy-scroller-btn .btn-label {
        font-size: 0.52rem;
        font-weight: 800;
        letter-spacing: 0.8px;
        color: #93C5FD;
        margin-top: 2px;
    }
    @media (max-width: 600px) {
        .glassy-scroller-btn {
            bottom: 14px;
            right: 14px;
            width: 40px;
            height: 40px;
        }
        .glassy-scroller-btn .arrow-icon {
            font-size: 0.9rem;
        }
        .glassy-scroller-btn .btn-label {
            font-size: 0.45rem;
        }
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
            "📊 Classic Workload Benchmark",
            "⚡ Cloud Chaos Lab (Intelligent Recovery)"
        ],
        index=0,
        help="Switch between the baseline academic benchmark and the interactive Cloud Chaos Lab."
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
            <div class="header-badge-container">
                <span class="header-badge">Distributed Systems Simulator</span>
                <span class="header-badge">Pure Python & Pandas</span>
                <span class="transition-live-badge">⚡ Real-Time Engine Active</span>
            </div>
        </div>

        <div class="quick-nav-bar">
            <span class="quick-nav-label">⚡ Jump To:</span>
            <a href="#section-1" class="quick-nav-pill">📊 1. Dataset Profile</a>
            <a href="#section-2" class="quick-nav-pill">🖥️ 2. Workload Monitor</a>
            <a href="#section-3" class="quick-nav-pill">➕ 3. Add Request</a>
            <a href="#section-4" class="quick-nav-pill">⚖️ 4. Comparative Benchmark</a>
            <a href="#section-5" class="quick-nav-pill">🔎 5. Assignment Browser</a>
            <a href="#section-6" class="quick-nav-pill">🛡️ 6. Correctness Guarantees</a>
            <a href="#section-7" class="quick-nav-pill">📥 7. Export Center</a>
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
    # 1. DATASET OVERVIEW SECTION
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <div id="section-1"></div>
        <div class="section-header-box">
            <h3 class="section-header-title">📊 1. Workload Dataset Profile</h3>
            <span class="header-badge">Baseline Trace • 1,000 Tasks</span>
        </div>
        <div class="section-header-desc">
            Structural characteristics, duration metrics, and task category distributions of the benchmark workload trace.
        </div>
        """,
        unsafe_allow_html=True,
    )
    
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
            st.pyplot(fig_types, use_container_width=True)

    st.markdown("---")

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
    # SIMULATION STATE INITIALIZATION & SESSION PERSISTENCE
    # -------------------------------------------------------------------------
    needs_state_init = (
        "simulation_state" not in st.session_state
        or st.session_state.get("sim_num_servers") != num_servers
        or run_clicked
    )

    if needs_state_init:
        init_rr_assign, init_rr_loads = round_robin_scheduler(df, servers)
        init_ll_assign, init_ll_loads = least_loaded_scheduler(df, servers)
        st.session_state.simulation_state = {
            "rr_assignments": init_rr_assign.copy(),
            "rr_loads": dict(init_rr_loads),
            "ll_assignments": init_ll_assign.copy(),
            "ll_loads": dict(init_ll_loads),
            "rr_index": len(df),
            "next_req_num": 1001,
            "added_requests": [],
            "last_message": None,
        }
        st.session_state.sim_num_servers = num_servers

    sim_state = st.session_state.simulation_state
    rr_assignments = sim_state["rr_assignments"]
    rr_loads = sim_state["rr_loads"]
    ll_assignments = sim_state["ll_assignments"]
    ll_loads = sim_state["ll_loads"]

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
    # -------------------------------------------------------------------------
    # 2. SERVER CLUSTER WORKLOAD MONITORING
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <div id="section-2"></div>
        <div class="section-header-box">
            <h3 class="section-header-title">🖥️ 2. Server Cluster Workload Monitoring</h3>
            <span class="transition-live-badge">⚡ Live Telemetry Active</span>
        </div>
        <div class="section-header-desc">
            Real-time cumulative processing workload (ms) and task counts allocated across virtual cloud servers.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("💡 Quick Guide: How to Read Server Workloads & Deltas", expanded=False):
        st.markdown(
            r"""
            - **Cumulative Workload (ms):** Total CPU burst duration assigned to this server node.
            - **Task Count:** Number of requests dispatched to this server. Round Robin strictly equalizes counts ($i \pmod N$), while Least Loaded dynamically routes based on cumulative burst time.
            - **Workload Delta ($+$ / $-$ ms):** Deviation from the ideal cluster average ($Total \div N$). A positive delta ($+$) indicates an overloaded node; a negative delta ($-$) indicates spare compute headroom.
            - **Progress Bar:** Workload proportion relative to the highest-loaded server in the cluster.
            """
        )
    
    total_active_workload = sum(ll_loads.values())
    mean_target_workload = total_active_workload / num_servers

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
    # 3. ADD NEW REQUEST (DYNAMIC LOAD BALANCING)
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <div id="section-3"></div>
        <div class="section-header-box">
            <h3 class="section-header-title">➕ 3. Add New Request (Dynamic Dispatcher)</h3>
            <span class="transition-live-badge">✨ Dynamic Injection Active</span>
        </div>
        <div class="section-header-desc">
            Inject custom tasks after the initial 1,000-request simulation to evaluate live server backlog allocation in real time.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Show success notification if a request was just added
    if sim_state.get("last_message"):
        st.success(f"✅ **{sim_state['last_message']}**")

    with st.expander("📝 Manually Create New Request", expanded=True):
        st.markdown(
            "Dynamically inject a new cloud request after the baseline 1,000-request simulation. "
            "The selected load balancing strategy will evaluate current server workloads and route the request immediately."
        )

        with st.expander("ℹ️ Reference: Cloud Request Types & Typical Execution Characteristics", expanded=False):
            st.markdown(
                """
                | Request Type | Typical Duration | Network Payload | Real-World Cloud Analogy |
                | :--- | :---: | :---: | :--- |
                | **API Read** | 30 – 200 ms | 0.5 – 5 MB | Lightweight REST/GraphQL queries, cache reads |
                | **Database Query** | 50 – 400 ms | 1 – 15 MB | Complex SQL joins, filtered record indexing |
                | **File Upload** | 100 – 600 ms | 10 – 50 MB | Multi-part S3 object uploads, media ingestion |
                | **Report Generation** | 300 – 800 ms | 20 – 100 MB | Aggregated analytical reports, PDF compilation |
                """
            )

        form_c1, form_c2, form_c3 = st.columns(3)

        with form_c1:
            auto_generate_id = st.checkbox(
                "Auto-generate Request ID",
                value=True,
                help="Automatically generates the next sequential ID: Request 1001, 1002, 1003, etc."
            )
            next_id_val = f"Request {sim_state['next_req_num']}"
            if auto_generate_id:
                manual_req_id = st.text_input(
                    "Request ID:",
                    value=next_id_val,
                    disabled=True,
                    help="Auto-generated sequential Request ID."
                )
            else:
                manual_req_id = st.text_input(
                    "Request ID:",
                    value=next_id_val,
                    placeholder="e.g. Request 1001 or REQ1001",
                    help="Custom unique Request ID."
                )

        with form_c2:
            request_type_choice = st.selectbox(
                "Request Type:",
                options=["API Read", "File Upload", "Report Generation", "Database Query"],
                index=0,
                help="Category of cloud workload request."
            )

        with form_c3:
            strategy_options = ["Least Loaded", "Round Robin"]
            default_strat_idx = 0 if algo_choice in ("Compare Both (Recommended)", "Least Loaded") else 1
            request_strategy = st.selectbox(
                "Load Balancing Strategy:",
                options=strategy_options,
                index=default_strat_idx,
                help="Scheduling strategy to assign this incoming request."
            )

        param_c1, param_c2, param_c3 = st.columns(3)

        with param_c1:
            processing_time_val = st.number_input(
                "Processing Time (ms):",
                min_value=1,
                max_value=100000,
                value=250,
                step=25,
                help="CPU execution time in milliseconds required on the server."
            )

        with param_c2:
            data_size_val = st.number_input(
                "Data Size (MB):",
                min_value=0.0,
                max_value=10000.0,
                value=5.00,
                step=0.5,
                format="%.2f",
                help="Payload data size in megabytes."
            )

        with param_c3:
            # Telemetry Preview Box
            current_min_srv = min(servers, key=lambda s: ll_loads[s])
            rr_next_srv = servers[sim_state["rr_index"] % len(servers)]
            st.markdown(
                f"""
                <div style="background: rgba(148, 163, 184, 0.08); border: 1px solid rgba(148, 163, 184, 0.25); border-radius: 8px; padding: 0.65rem 0.9rem; font-size: 0.85rem; margin-top: 0.35rem;">
                    <div style="color: #93C5FD; font-weight: 600; margin-bottom: 2px;">⚡ Live Server Backlog Status</div>
                    <div>Least Loaded Candidate: <strong style="color: #10B981;">{current_min_srv}</strong> ({ll_loads[current_min_srv]:,} ms)</div>
                    <div>Round Robin Next Node: <strong style="color: #3B82F6;">{rr_next_srv}</strong></div>
                </div>
                """,
                unsafe_allow_html=True
            )

        btn_c1, btn_c2, _ = st.columns([2, 2, 4])
        with btn_c1:
            add_request_clicked = st.button("🚀 Add Request", type="primary", use_container_width=True)
        with btn_c2:
            if len(sim_state["added_requests"]) > 0:
                reset_dynamic_clicked = st.button("🔄 Reset to Initial 1,000 Requests", use_container_width=True)
            else:
                reset_dynamic_clicked = False

        if reset_dynamic_clicked:
            init_rr_assign, init_rr_loads = round_robin_scheduler(df, servers)
            init_ll_assign, init_ll_loads = least_loaded_scheduler(df, servers)
            sim_state["rr_assignments"] = init_rr_assign.copy()
            sim_state["rr_loads"] = dict(init_rr_loads)
            sim_state["ll_assignments"] = init_ll_assign.copy()
            sim_state["ll_loads"] = dict(init_ll_loads)
            sim_state["rr_index"] = len(df)
            sim_state["next_req_num"] = 1001
            sim_state["added_requests"] = []
            sim_state["last_message"] = None
            st.toast("Cluster reset to baseline 1,000 requests.", icon="🔄")
            st.rerun()

        if add_request_clicked:
            # Check for ID collisions across initial dataset and assignments
            all_existing_ids = set(df["Request_ID"]).union(
                set(sim_state["rr_assignments"]["Request_ID"])
            ).union(
                set(sim_state["ll_assignments"]["Request_ID"])
            )

            is_valid, err_msg, cleaned_req = validate_request_inputs(
                request_id=manual_req_id,
                request_type=request_type_choice,
                processing_time_ms=processing_time_val,
                data_size_mb=data_size_val,
                existing_ids=all_existing_ids
            )

            if not is_valid:
                st.error(f"❌ Input Validation Error: {err_msg}")
            else:
                id_raw = str(cleaned_req["Request_ID"]).strip()
                id_display = id_raw if id_raw.lower().startswith("request") else f"Request {id_raw}"

                if request_strategy == "Least Loaded":
                    selected_srv, rec, updated_loads = assign_single_request(
                        request=cleaned_req,
                        servers=servers,
                        current_loads=sim_state["ll_loads"],
                        strategy="Least Loaded"
                    )
                    sim_state["ll_loads"] = updated_loads
                    sim_state["ll_assignments"] = pd.concat(
                        [sim_state["ll_assignments"], pd.DataFrame([rec])],
                        ignore_index=True
                    )
                    success_msg = f"{id_display} assigned to {selected_srv} using Least Loaded strategy."
                else:  # Round Robin
                    selected_srv, rec, updated_loads = assign_single_request(
                        request=cleaned_req,
                        servers=servers,
                        current_loads=sim_state["rr_loads"],
                        strategy="Round Robin",
                        current_index=sim_state["rr_index"]
                    )
                    sim_state["rr_loads"] = updated_loads
                    sim_state["rr_assignments"] = pd.concat(
                        [sim_state["rr_assignments"], pd.DataFrame([rec])],
                        ignore_index=True
                    )
                    sim_state["rr_index"] += 1
                    success_msg = f"{id_display} assigned to {selected_srv} using Round Robin strategy."

                sim_state["added_requests"].append({
                    "Request_ID": cleaned_req["Request_ID"],
                    "Request_Type": cleaned_req["Request_Type"],
                    "Processing_Time_ms": cleaned_req["Processing_Time_ms"],
                    "Data_Size_MB": cleaned_req["Data_Size_MB"],
                    "Strategy": request_strategy,
                    "Assigned_Server": selected_srv,
                })
                sim_state["next_req_num"] += 1
                sim_state["last_message"] = success_msg
                st.toast(success_msg, icon="☁️")
                st.rerun()

        # Display history of manually added requests if any exist
        if len(sim_state["added_requests"]) > 0:
            st.markdown(f"**Manually Injected Requests Log ({len(sim_state['added_requests'])}):**")
            render_dataframe(pd.DataFrame(sim_state["added_requests"]), height=160)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 4. ALGORITHM COMPARISON & VISUALIZATIONS
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <div id="section-4"></div>
        <div class="section-header-box">
            <h3 class="section-header-title">⚖️ 4. Comparative Performance Analysis</h3>
            <span class="transition-live-badge">📊 Analytics Active</span>
        </div>
        <div class="section-header-desc">
            Side-by-side evaluation of load distribution uniformity, inter-server imbalance, and estimated makespan.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("ℹ️ Metrics Guide: Key Performance Indicators Explained", expanded=False):
        st.markdown(
            """
            - **Inter-Server Load Imbalance:** The gap between the heaviest loaded server and the least loaded server ($Max - Min$). **Lower is better.** A lower imbalance means compute resources are utilized uniformly without starvation.
            - **Estimated Makespan:** The workload of the busiest server ($Max$). Under concurrent batch execution, makespan represents the total elapsed time to finish all tasks. **Lower is better.**
            - **Load Imbalance Reduction (%):** How much Least Loaded compressed the load disparity compared to Round Robin:
              $$\\text{Reduction (\\%)} = \\frac{\\text{Imbalance}_{RR} - \\text{Imbalance}_{LL}}{\\text{Imbalance}_{RR}} \\times 100$$
            """
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
            st.pyplot(fig_servers, use_container_width=True)

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
            st.pyplot(fig_imb, use_container_width=True)

    with tab_table:
        st.markdown("**Performance Comparison Summary:**")
        render_dataframe(comp_df)
        st.markdown("**Per-Server Workload & Task Allocation Breakdown:**")
        render_dataframe(sw_df)

    st.markdown("---")

    # ---------------------------------------------------------
    # 5. REQUEST ASSIGNMENTS INSPECTOR
    # ---------------------------------------------------------
    st.markdown(
        """
        <div id="section-5"></div>
        <div class="section-header-box">
            <h3 class="section-header-title">🔎 5. Request Assignment Browser</h3>
            <span class="header-badge">Granular Audit Log</span>
        </div>
        <div class="section-header-desc">
            Filter, search, and verify individual task dispatch records, arrival timestamps, and cumulative backlogs.
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    inspect_algo = st.radio(
        "Select assignments table to browse:",
        options=["Least Loaded", "Round Robin"],
        horizontal=True,
    )
    active_assignments = ll_assignments if inspect_algo == "Least Loaded" else rr_assignments
    active_loads = ll_loads if inspect_algo == "Least Loaded" else rr_loads

    # Interactive Filters
    filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 2])
    with filter_col1:
        search_req_id = st.text_input("Search by Request ID:", value="", placeholder="e.g. REQ0015 or Request 1001").strip().upper()
    with filter_col2:
        filter_srv = st.selectbox("Filter by Server:", options=["All"] + servers)
    with filter_col3:
        filter_type = st.selectbox("Filter by Request Type:", options=["All"] + sorted(list(set(active_assignments["Request_Type"].unique()))))

    filtered_df = active_assignments.copy()
    if search_req_id:
        filtered_df = filtered_df[filtered_df["Request_ID"].astype(str).str.upper().str.contains(search_req_id, na=False)]
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
    # 6. CORRECTNESS VERIFICATION PILLS
    # ---------------------------------------------------------
    st.markdown(
        """
        <div id="section-6"></div>
        <div class="section-header-box">
            <h3 class="section-header-title">🛡️ 6. Formal Simulation Correctness Guarantees</h3>
            <span class="header-badge">100% Invariant Verification</span>
        </div>
        <div class="section-header-desc">
            Rigorous mathematical checks verifying total workload conservation, zero lost tasks, and non-duplication.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("💡 Mathematical Invariants Proven by This Simulation", expanded=False):
        st.markdown(
            r"""
            1. **Single Assignment Invariant:** Every input request is assigned to exactly one server ($|A| = |D|$).
            2. **No Duplication / No Loss Invariant:** Set of assigned IDs strictly matches dataset IDs ($\{A_{id}\} = \{D_{id}\}$).
            3. **Workload Conservation Law:** Total assigned CPU time matches the total input burst time ($\sum L_s = \sum P_i$).
            4. **Load Accounting Accuracy:** Recorded server cumulative backlogs match the grouped sum of assigned request durations.
            """
        )
    
    # Active requests to verify (original 1,000 requests + any manually added requests)
    if len(active_assignments) == len(df):
        active_input_df = df
    else:
        active_input_df = active_assignments[[
            "Request_ID", "Arrival_Time", "Request_Type", "Processing_Time_ms", "Data_Size_MB"
        ]]

    active_check = verify_simulation_correctness(active_input_df, active_assignments, active_loads)

    if active_check["all_passed"]:
        total_active_ms = sum(active_loads.values())
        st.markdown(
            f"""
            <div>
                <span class="pill-success">✔ All {len(active_assignments):,} requests assigned exactly once</span>
                <span class="pill-success">✔ Zero lost or duplicate requests</span>
                <span class="pill-success">✔ Total workload strictly conserved ({total_active_ms:,} ms)</span>
                <span class="pill-success">✔ Server workloads match assignment sums</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.error("⚠️ One or more simulation correctness constraints failed verification.")

    st.markdown("---")

    # ---------------------------------------------------------
    # 7. EXPORTS & DOWNLOAD BUTTONS
    # ---------------------------------------------------------
    st.markdown(
        """
        <div id="section-7"></div>
        <div class="section-header-box">
            <h3 class="section-header-title">📥 7. Export Center & Research Artifacts</h3>
            <span class="header-badge">CSV Data Export</span>
        </div>
        <div class="section-header-desc">
            Download assignment mapping files and performance comparisons matching the current configuration.
        </div>
        """,
        unsafe_allow_html=True,
    )

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
    # 8. SCIENTIFIC LIMITATION & EDUCATIONAL NOTES
    # ---------------------------------------------------------
    st.markdown(
        """
        <div id="section-8"></div>
        <div class="section-header-box">
            <h3 class="section-header-title">📖 8. Scientific Limitations & Architectural Takeaways</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
