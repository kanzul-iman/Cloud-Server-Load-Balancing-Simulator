"""
Performance Analytics and Visualization Charts for Cloud Chaos Lab.
Renders high-quality Matplotlib figures for cluster telemetry, CPU load,
queue backlogs, response latency distributions, and algorithm comparisons.
"""

from typing import Dict, Any, List
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from simulator.models import CloudServer
from simulator.chaos_engine import ChaosSimulationEngine


def setup_dark_plot_style(ax, fig):
    """Apply modern dark mode styling matching the dashboard aesthetic."""
    fig.patch.set_facecolor('#0F172A')
    ax.set_facecolor('#1E293B')
    ax.tick_params(colors='#94A3B8', labelsize=8)
    ax.xaxis.label.set_color('#CBD5E1')
    ax.yaxis.label.set_color('#CBD5E1')
    ax.title.set_color('#F8FAFC')
    for spine in ax.spines.values():
        spine.set_color('#334155')
    ax.grid(True, linestyle='--', alpha=0.25, color='#64748B')


def render_performance_charts(engine: ChaosSimulationEngine) -> None:
    """Render the complete telemetry charts suite."""
    st.markdown("### 📊 Performance Analytics & Live Telemetry")
    
    df_telemetry = engine.get_telemetry_dataframe()
    metrics = engine.compute_comprehensive_metrics()

    # KPI Metric Cards
    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
    with kpi1:
        st.metric("Total Submitted", f"{metrics['Total_Submitted_Requests']}")
    with kpi2:
        st.metric("Completed", f"{metrics['Completed_Requests']}")
    with kpi3:
        st.metric("Throughput", f"{metrics['Throughput_RPS']:.1f} RPS")
    with kpi4:
        st.metric("Avg Response", f"{metrics['Average_Response_Time_ms']:.0f} ms")
    with kpi5:
        st.metric("P95 Latency", f"{metrics['P95_Response_Time_ms']:.0f} ms")
    with kpi6:
        st.metric("Energy (kWh)", f"{metrics['Estimated_Energy_kWh']:.4f}")

    tab_telemetry, tab_latency, tab_energy, tab_table = st.tabs([
        "📈 CPU & Queue Telemetry",
        "⏱️ Latency Distribution (P50/P95/P99)",
        "⚡ Energy & Infrastructure Cost",
        "📋 Per-Server Metrics Table"
    ])

    # -------------------------------------------------------------------------
    # TAB 1: CPU & QUEUE OVER TIME
    # -------------------------------------------------------------------------
    with tab_telemetry:
        if df_telemetry.empty or len(df_telemetry) < 2:
            st.info("Run or step the simulation to generate time-series telemetry.")
        else:
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.markdown("**Server CPU Utilization Over Time (%)**")
                fig_cpu, ax_cpu = plt.subplots(figsize=(6, 3.4))
                setup_dark_plot_style(ax_cpu, fig_cpu)

                # Plot per server CPU
                palette = ['#38BDF8', '#818CF8', '#34D399', '#FBBF24', '#F87171', '#C084FC', '#FB7185', '#2DD4BF']
                for idx, s in enumerate(engine.servers):
                    col_name = f"{s.name}_CPU"
                    if col_name in df_telemetry.columns:
                        ax_cpu.plot(
                            df_telemetry["Sim_Time_sec"],
                            df_telemetry[col_name],
                            label=s.name,
                            color=palette[idx % len(palette)],
                            linewidth=1.8,
                            alpha=0.9
                        )

                # Plot Cluster Average
                if "Cluster_Avg_CPU_Pct" in df_telemetry.columns:
                    ax_cpu.plot(
                        df_telemetry["Sim_Time_sec"],
                        df_telemetry["Cluster_Avg_CPU_Pct"],
                        label="Cluster Avg",
                        color="#FFFFFF",
                        linestyle="--",
                        linewidth=1.2,
                        alpha=0.85
                    )

                ax_cpu.set_xlabel("Simulated Time (seconds)", fontsize=8)
                ax_cpu.set_ylabel("CPU Utilization (%)", fontsize=8)
                ax_cpu.set_ylim(-5, 105)
                ax_cpu.legend(fontsize=7, facecolor="#0F172A", edgecolor="#334155", labelcolor="#CBD5E1")
                plt.tight_layout()
                st.pyplot(fig_cpu)
                plt.close(fig_cpu)

            with col_chart2:
                st.markdown("**Queue Backlog Depth Over Time (Requests)**")
                fig_q, ax_q = plt.subplots(figsize=(6, 3.4))
                setup_dark_plot_style(ax_q, fig_q)

                for idx, s in enumerate(engine.servers):
                    col_name = f"{s.name}_Queue"
                    if col_name in df_telemetry.columns:
                        ax_q.plot(
                            df_telemetry["Sim_Time_sec"],
                            df_telemetry[col_name],
                            label=s.name,
                            color=palette[idx % len(palette)],
                            linewidth=1.8,
                            alpha=0.9
                        )

                ax_q.set_xlabel("Simulated Time (seconds)", fontsize=8)
                ax_q.set_ylabel("Pending Queue Length", fontsize=8)
                ax_q.legend(fontsize=7, facecolor="#0F172A", edgecolor="#334155", labelcolor="#CBD5E1")
                plt.tight_layout()
                st.pyplot(fig_q)
                plt.close(fig_q)

    # -------------------------------------------------------------------------
    # TAB 2: LATENCY DISTRIBUTION
    # -------------------------------------------------------------------------
    with tab_latency:
        if not engine.completed_requests:
            st.info("No requests completed yet.")
        else:
            lat_col1, lat_col2 = st.columns(2)
            with lat_col1:
                st.markdown("**Response Latency Percentiles (ms)**")
                fig_lat, ax_lat = plt.subplots(figsize=(6, 3.4))
                setup_dark_plot_style(ax_lat, fig_lat)

                pct_labels = ["Avg Wait", "Avg Turnaround", "Median (P50)", "P95 Latency", "P99 Latency"]
                pct_vals = [
                    metrics["Average_Waiting_Time_ms"],
                    metrics["Average_Response_Time_ms"],
                    metrics["Median_Response_Time_ms"],
                    metrics["P95_Response_Time_ms"],
                    metrics["P99_Response_Time_ms"]
                ]
                bar_colors = ["#38BDF8", "#818CF8", "#34D399", "#FBBF24", "#EF4444"]
                bars = ax_lat.bar(pct_labels, pct_vals, color=bar_colors, edgecolor="#334155", width=0.55)

                for b in bars:
                    y = b.get_height()
                    ax_lat.text(b.get_x() + b.get_width()/2, y + (max(pct_vals)*0.02), f"{int(y):,} ms", ha='center', fontsize=7.5, color='#F8FAFC', fontweight='bold')

                ax_lat.set_ylim(0, max(pct_vals) * 1.18 if pct_vals else 100)
                plt.xticks(rotation=15)
                plt.tight_layout()
                st.pyplot(fig_lat)
                plt.close(fig_lat)

            with lat_col2:
                st.markdown("**Turnaround Time Histogram (ms)**")
                fig_hist, ax_hist = plt.subplots(figsize=(6, 3.4))
                setup_dark_plot_style(ax_hist, fig_hist)

                turnarounds = [r.turnaround_time_ms for r in engine.completed_requests if r.turnaround_time_ms is not None]
                if turnarounds:
                    ax_hist.hist(turnarounds, bins=20, color='#3B82F6', edgecolor='#1E3A8A', alpha=0.85)
                    ax_hist.set_xlabel("Turnaround Time (ms)", fontsize=8)
                    ax_hist.set_ylabel("Request Count", fontsize=8)
                plt.tight_layout()
                st.pyplot(fig_hist)
                plt.close(fig_hist)

    # -------------------------------------------------------------------------
    # TAB 3: ENERGY & INFRASTRUCTURE COST
    # -------------------------------------------------------------------------
    with tab_energy:
        e_col1, e_col2 = st.columns(2)
        with e_col1:
            st.markdown("**Per-Server Modeled Energy Consumption (kWh)**")
            fig_eng, ax_eng = plt.subplots(figsize=(6, 3.4))
            setup_dark_plot_style(ax_eng, fig_eng)

            s_names = [s.name for s in engine.servers]
            s_energy = [s.calculate_energy_kwh(max(0.001, engine.current_time_sec)) for s in engine.servers]
            bars_e = ax_eng.bar(s_names, s_energy, color="#10B981", edgecolor="#064E3B", width=0.5)

            for b in bars_e:
                y = b.get_height()
                ax_eng.text(b.get_x() + b.get_width()/2, y + (max(s_energy)*0.02 if s_energy else 0), f"{y:.4f}", ha='center', fontsize=7.5, color='#34D399', fontweight='bold')

            ax_eng.set_ylabel("Energy (kWh)", fontsize=8)
            plt.xticks(rotation=15)
            plt.tight_layout()
            st.pyplot(fig_eng)
            plt.close(fig_eng)

        with e_col2:
            st.markdown("**Modeled Datacenter Cost Distribution ($ USD)**")
            st.markdown(
                f"""
                <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 10px; padding: 1.2rem; font-size: 0.9rem;">
                    <div style="font-size: 1.2rem; font-weight: 700; color: #38BDF8; margin-bottom: 0.5rem;">
                        Estimated Cloud Infrastructure Cost: ${metrics['Estimated_Cost_USD']:.4f} USD
                    </div>
                    <div style="color: #CBD5E1; line-height: 1.6;">
                        &bull; Modeled Rate: <strong>$0.05 / hour</strong> per provisioned server node.<br>
                        &bull; Active Server-Hours: <strong>{(engine.current_time_sec / 3600.0) * len(engine.servers):.4f} hrs</strong>.<br>
                        &bull; Total Cluster Energy: <strong>{metrics['Estimated_Energy_kWh']:.4f} kWh</strong>.<br>
                        &bull; Workload Imbalance: <strong>{metrics['Load_Imbalance_ms']:,.0f} ms</strong>.
                    </div>
                    <div style="margin-top: 1rem; color: #94A3B8; font-size: 0.78rem;">
                        <em>Note: Modeled educational estimate based on server uptime and CPU utilization power curves.</em>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    # -------------------------------------------------------------------------
    # TAB 4: PER-SERVER METRICS TABLE
    # -------------------------------------------------------------------------
    with tab_table:
        st.markdown("**Detailed Per-Server Telemetry Ledger:**")
        server_rows = []
        for s in engine.servers:
            server_rows.append({
                "Server": s.name,
                "State": s.state.value,
                "Speed": f"{s.effective_capacity:.2f}x",
                "CPU (%)": f"{s.cpu_utilization_pct:.1f}%",
                "RAM (%)": f"{s.ram_utilization_pct:.1f}%",
                "Queue": s.queue_length,
                "Completed": len(s.completed_requests),
                "Retried": s.retried_requests_count,
                "Failed": s.failed_requests_count,
                "Lost Work (ms)": f"{s.total_lost_work_ms:.0f}",
                "Workload (ms)": f"{s.cumulative_workload_ms:,.0f}",
                "Energy (kWh)": f"{s.calculate_energy_kwh(max(0.001, engine.current_time_sec)):.5f}"
            })
        df_servers = pd.DataFrame(server_rows)
        st.dataframe(df_servers, use_container_width=True)
