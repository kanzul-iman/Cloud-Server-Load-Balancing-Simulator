"""
Cloud Server Load Balancing Simulator - Main CLI Runner
Demonstrates and compares load balancing algorithms on cloud workload traces.
"""

import argparse
import os
import sys
from typing import List

from simulator.models import CloudServer
from simulator.algorithms import (
    RoundRobinScheduler,
    LeastLoadedScheduler,
    WeightedRoundRobinScheduler,
    DynamicLeastConnectionsScheduler,
    ShortestJobFirstScheduler,
    AdaptiveCapacityAwareScheduler,
)
from simulator.engine import SimulationEngine


def print_banner():
    banner = r"""
========================================================================
       CLOUD SERVER LOAD BALANCING SIMULATOR (SEMESTER PROJECT)
       Distributed Systems & Cloud Computing Performance Evaluation
========================================================================
    """
    print(banner)


def format_table(headers: List[str], rows: List[List[str]]) -> str:
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, val in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(str(val)))
    
    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header_line = "| " + " | ".join(f"{h:<{col_widths[i]}}" for i, h in enumerate(headers)) + " |"
    
    lines = [sep, header_line, sep]
    for row in rows:
        r_line = "| " + " | ".join(f"{str(val):<{col_widths[i]}}" for i, val in enumerate(row)) + " |"
        lines.append(r_line)
    lines.append(sep)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Cloud Server Load Balancing Simulator CLI"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="cloud_load_balancer_dataset_1000.csv",
        help="Path to workload dataset CSV (default: cloud_load_balancer_dataset_1000.csv)",
    )
    parser.add_argument(
        "--servers",
        type=int,
        default=3,
        help="Number of simulated cloud servers (default: 3)",
    )
    parser.add_argument(
        "--heterogeneous",
        action="store_true",
        help="Simulate heterogeneous server capacities (different processing speeds)",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "static", "dynamic"],
        default="all",
        help="Simulation mode: 'static', 'dynamic', or 'all' (default: all)",
    )
    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="Save simulation results to CSV files",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Generate comparison plots using matplotlib if available",
    )

    args = parser.parse_args()
    print_banner()

    if not os.path.exists(args.dataset):
        print(f"Error: Dataset file '{args.dataset}' not found.")
        sys.exit(1)

    # Initialize servers
    servers: List[CloudServer] = []
    if args.heterogeneous:
        # Example heterogeneous cluster: S1 (High Performance 2.0x), S2 (Standard 1.0x), S3 (Economy 0.75x)
        weights = [2.0, 1.0, 0.75, 1.5, 0.5]
        for i in range(args.servers):
            weight = weights[i % len(weights)]
            servers.append(CloudServer(i + 1, f"Server {i + 1} ({weight}x)", capacity_weight=weight))
        print(f"[Configuration] Initialized {args.servers} HETEROGENEOUS Cloud Servers:")
        for s in servers:
            print(f"  * {s.name}: Capacity Weight = {s.capacity_weight}x")
    else:
        for i in range(args.servers):
            servers.append(CloudServer(i + 1, f"Server {i + 1}", capacity_weight=1.0))
        print(f"[Configuration] Initialized {args.servers} HOMOGENEOUS Cloud Servers (1.0x capacity).")

    engine = SimulationEngine(servers)
    count = engine.load_dataset_from_csv(args.dataset)
    print(f"[Dataset] Successfully loaded {count} incoming cloud requests from '{args.dataset}'.\n")

    algorithms = [
        RoundRobinScheduler(),
        LeastLoadedScheduler(),
        AdaptiveCapacityAwareScheduler(),
        DynamicLeastConnectionsScheduler(),
        ShortestJobFirstScheduler(),
    ]
    if args.heterogeneous:
        algorithms.insert(2, WeightedRoundRobinScheduler())

    # 1. Static Simulation Mode
    if args.mode in ("all", "static"):
        print("=" * 72)
        print("  1. STATIC WORKLOAD ALLOCATION BENCHMARK (CUMULATIVE HEURISTIC)")
        print("=" * 72)
        static_rows = []
        static_headers = [
            "Algorithm",
            "Total Load (ms)",
            "Max Load (ms)",
            "Min Load (ms)",
            "Imbalance (ms)",
            "Std Dev (ms)",
            "Est. Makespan (ms)",
        ]

        for algo in algorithms:
            res = engine.run(algo, mode="static")
            m = res.metrics
            static_rows.append([
                m["Algorithm"],
                f"{m['Total_Workload_ms']:,.0f}",
                f"{m['Maximum_Server_Load_ms']:,.0f}",
                f"{m['Minimum_Server_Load_ms']:,.0f}",
                f"{m['Load_Imbalance_ms']:,.0f}",
                f"{m['Load_Std_Dev_ms']:.2f}",
                f"{m['Estimated_Makespan_ms']:,.0f}",
            ])

        print(format_table(static_headers, static_rows))
        print()

    # 2. Dynamic Simulation Mode
    if args.mode in ("all", "dynamic"):
        print("=" * 72)
        print("  2. DYNAMIC DISCRETE-EVENT QUEUE SIMULATION (TIME-AWARE)")
        print("=" * 72)
        dynamic_rows = []
        dynamic_headers = [
            "Algorithm",
            "Makespan (s)",
            "Avg Wait (ms)",
            "Avg Turnaround (ms)",
            "P95 Latency (ms)",
            "Utilization (%)",
            "Throughput (RPS)",
        ]

        for algo in algorithms:
            res = engine.run(algo, mode="dynamic")
            m = res.metrics
            dynamic_rows.append([
                m["Algorithm"],
                f"{m['Simulation_Makespan_sec']:.2f}",
                f"{m['Avg_Waiting_Time_ms']:.2f}",
                f"{m['Avg_Response_Time_ms']:.2f}",
                f"{m['P95_Response_Time_ms']:.2f}",
                f"{m['Overall_Utilization_Pct']:.1f}%",
                f"{m['Throughput_RPS']:.2f}",
            ])

        print(format_table(dynamic_headers, dynamic_rows))
        print()

    # Optional plotting
    if args.plot:
        try:
            import matplotlib.pyplot as plt
            # Generate comparative dynamic chart
            alg_names = []
            avg_waits = []
            utilizations = []
            for algo in algorithms:
                res = engine.run(algo, mode="dynamic")
                alg_names.append(algo.name)
                avg_waits.append(res.metrics["Avg_Waiting_Time_ms"])
                utilizations.append(res.metrics["Overall_Utilization_Pct"])

            fig, ax1 = plt.subplots(figsize=(10, 5))
            color = 'tab:blue'
            ax1.set_xlabel('Scheduling Algorithm')
            ax1.set_ylabel('Avg Waiting Time (ms)', color=color)
            bars = ax1.bar(alg_names, avg_waits, color=color, alpha=0.7, width=0.4, label='Avg Waiting Time')
            ax1.tick_params(axis='y', labelcolor=color)
            plt.xticks(rotation=15)

            ax2 = ax1.twinx()
            color = 'tab:orange'
            ax2.set_ylabel('Cluster Utilization (%)', color=color)
            ax2.plot(alg_names, utilizations, color=color, marker='o', linewidth=2, label='Cluster Utilization')
            ax2.tick_params(axis='y', labelcolor=color)

            plt.title('Dynamic Simulation: Waiting Time vs Cluster Utilization')
            fig.tight_layout()
            out_img = "dynamic_performance_benchmark.png"
            plt.savefig(out_img, dpi=150)
            print(f"[Visualization] Saved benchmark plot to '{out_img}'.")
        except ImportError:
            print("[Visualization] Matplotlib is not installed in the active environment. Skipping plot.")

    print("[Complete] Simulation run finished successfully.")


if __name__ == "__main__":
    main()
