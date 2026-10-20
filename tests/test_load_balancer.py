"""
Automated Unit & Integration Test Suite for Cloud Server Load Balancing Simulator.
Thorough quality-assurance pass covering all required functional scenarios and edge cases.
Compatible with both pytest and standard unittest runner.
"""

import os
import tempfile
from pathlib import Path
import unittest
import pandas as pd

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
    DEFAULT_SERVERS,
)
from src.metrics import (
    calculate_algorithm_metrics,
    calculate_load_imbalance_reduction,
    verify_simulation_correctness,
    build_performance_comparison_dataframe,
    build_server_workload_dataframe,
    export_simulation_reports,
)


class TestExistingDataset(unittest.TestCase):
    """TEST CASE 1: Verification of the existing supplied dataset."""

    def setUp(self):
        self.df = load_and_validate_dataset()

    def test_dataset_dimensions_and_schema(self):
        """Verify the supplied CSV has exactly 1,000 rows and all required columns."""
        self.assertEqual(len(self.df), 1000)
        for col in REQUIRED_COLUMNS:
            self.assertIn(col, self.df.columns)

    def test_no_lost_or_duplicated_requests(self):
        """Confirm no request is lost or assigned more than once."""
        servers = generate_server_names(3)
        rr_assign, _ = round_robin_scheduler(self.df, servers)
        ll_assign, _ = least_loaded_scheduler(self.df, servers)

        # Check Round Robin
        self.assertEqual(len(rr_assign), 1000)
        self.assertEqual(rr_assign["Request_ID"].nunique(), 1000)
        self.assertEqual(set(rr_assign["Request_ID"]), set(self.df["Request_ID"]))

        # Check Least Loaded
        self.assertEqual(len(ll_assign), 1000)
        self.assertEqual(ll_assign["Request_ID"].nunique(), 1000)
        self.assertEqual(set(ll_assign["Request_ID"]), set(self.df["Request_ID"]))

    def test_workload_conservation(self):
        """Verify total assigned processing time strictly equals total input processing time."""
        total_input_ms = int(self.df["Processing_Time_ms"].sum())
        self.assertEqual(total_input_ms, 195367)

        servers = generate_server_names(3)
        _, rr_loads = round_robin_scheduler(self.df, servers)
        _, ll_loads = least_loaded_scheduler(self.df, servers)

        self.assertEqual(sum(rr_loads.values()), total_input_ms)
        self.assertEqual(sum(ll_loads.values()), total_input_ms)


class TestRoundRobinScheduling(unittest.TestCase):
    """TEST CASE 2: Verification of Round Robin algorithm mechanics."""

    def setUp(self):
        self.df = load_and_validate_dataset()
        self.servers = ["Server 1", "Server 2", "Server 3"]

    def test_cyclic_assignment_sequence(self):
        """Verify the server assignment sequence is strictly cyclic: S1, S2, S3, S1..."""
        assignments, _ = round_robin_scheduler(self.df, self.servers)
        num_servers = len(self.servers)

        for idx, (_, row) in enumerate(assignments.iterrows()):
            expected_server = self.servers[idx % num_servers]
            self.assertEqual(row["Server"], expected_server)

    def test_deterministic_output(self):
        """Verify deterministic results for repeated runs on identical input."""
        assign1, loads1 = round_robin_scheduler(self.df, self.servers)
        assign2, loads2 = round_robin_scheduler(self.df, self.servers)

        self.assertEqual(loads1, loads2)
        pd.testing.assert_frame_equal(assign1, assign2)

    def test_workload_totals_match_assigned_requests(self):
        """Verify server workload totals equal the processing times of assigned requests."""
        assignments, loads = round_robin_scheduler(self.df, self.servers)
        computed_totals = assignments.groupby("Server")["Processing_Time_ms"].sum().to_dict()

        for s in self.servers:
            self.assertEqual(loads[s], computed_totals[s])


class TestLeastLoadedScheduling(unittest.TestCase):
    """TEST CASE 3: Verification of Least Loaded algorithm mechanics."""

    def setUp(self):
        self.df = load_and_validate_dataset()
        self.servers = ["Server 1", "Server 2", "Server 3"]

    def test_step_by_step_minimum_backlog_selection(self):
        """
        Verify each request is assigned to a server with the minimum accumulated workload
        immediately before that request is assigned.
        """
        server_loads = {s: 0 for s in self.servers}

        for _, request in self.df.iterrows():
            min_load_before = min(server_loads.values())
            # Deterministic selection
            selected_server = min(self.servers, key=lambda s: server_loads[s])

            # Assert that the selected server had the minimum load immediately before assignment
            self.assertEqual(server_loads[selected_server], min_load_before)

            server_loads[selected_server] += int(request["Processing_Time_ms"])

        # Compare with scheduler function output
        _, actual_loads = least_loaded_scheduler(self.df, self.servers)
        self.assertEqual(server_loads, actual_loads)

    def test_deterministic_tie_breaking(self):
        """
        Verify ties are resolved deterministically using server declaration order.
        When all servers have 0 load, the first 3 requests must go to Server 1, Server 2, Server 3.
        """
        sample_df = self.df.head(3).copy()
        assignments, _ = least_loaded_scheduler(sample_df, self.servers)

        self.assertEqual(assignments.iloc[0]["Server"], "Server 1")
        self.assertEqual(assignments.iloc[1]["Server"], "Server 2")
        self.assertEqual(assignments.iloc[2]["Server"], "Server 3")

    def test_workload_totals_match_assigned_requests(self):
        """Verify server workload totals equal the processing times of requests assigned to each server."""
        assignments, loads = least_loaded_scheduler(self.df, self.servers)
        computed_totals = assignments.groupby("Server")["Processing_Time_ms"].sum().to_dict()

        for s in self.servers:
            self.assertEqual(loads[s], computed_totals[s])


class TestEdgeCases(unittest.TestCase):
    """TEST CASE 4: Verification of boundary conditions and edge cases."""

    def test_empty_dataset_with_valid_columns(self):
        """Verify handling of an empty dataset containing valid column headers."""
        empty_df = pd.DataFrame(columns=REQUIRED_COLUMNS)
        servers = generate_server_names(3)

        # DataLoader with allow_empty=True
        loaded_empty = load_and_validate_dataset(empty_df, allow_empty=True)
        self.assertEqual(len(loaded_empty), 0)

        # Schedulers
        rr_assign, rr_loads = round_robin_scheduler(loaded_empty, servers)
        ll_assign, ll_loads = least_loaded_scheduler(loaded_empty, servers)

        self.assertEqual(len(rr_assign), 0)
        self.assertEqual(len(ll_assign), 0)
        self.assertEqual(sum(rr_loads.values()), 0)
        self.assertEqual(sum(ll_loads.values()), 0)

        # Correctness check passes
        check = verify_simulation_correctness(loaded_empty, rr_assign, rr_loads)
        self.assertTrue(check["all_passed"])

    def test_one_request(self):
        """Verify cluster execution with exactly one incoming request."""
        one_req_df = pd.DataFrame([{
            "Request_ID": "REQ_SINGLE",
            "Arrival_Time": "2026-10-20 10:00:00",
            "Request_Type": "API_Read",
            "Processing_Time_ms": 250,
            "Data_Size_MB": 1.5,
        }])
        servers = generate_server_names(3)

        rr_assign, rr_loads = round_robin_scheduler(one_req_df, servers)
        ll_assign, ll_loads = least_loaded_scheduler(one_req_df, servers)

        # Both route single request to Server 1
        self.assertEqual(rr_assign.iloc[0]["Server"], "Server 1")
        self.assertEqual(ll_assign.iloc[0]["Server"], "Server 1")
        self.assertEqual(rr_loads["Server 1"], 250)
        self.assertEqual(rr_loads["Server 2"], 0)
        self.assertEqual(rr_loads["Server 3"], 0)
        self.assertEqual(ll_loads["Server 1"], 250)

    def test_one_server(self):
        """Verify scheduling when cluster consists of only one logical server."""
        one_server = generate_server_names(1)
        self.assertEqual(one_server, ["Server 1"])

        sample_df = pd.DataFrame([
            {"Request_ID": "R1", "Arrival_Time": "t1", "Request_Type": "API", "Processing_Time_ms": 100, "Data_Size_MB": 1.0},
            {"Request_ID": "R2", "Arrival_Time": "t2", "Request_Type": "API", "Processing_Time_ms": 200, "Data_Size_MB": 2.0},
        ])

        rr_assign, rr_loads = round_robin_scheduler(sample_df, one_server)
        ll_assign, ll_loads = least_loaded_scheduler(sample_df, one_server)

        self.assertEqual(rr_loads["Server 1"], 300)
        self.assertEqual(ll_loads["Server 1"], 300)

        # Metrics: load imbalance must be 0
        rr_m = calculate_algorithm_metrics("Round Robin", rr_assign, rr_loads)
        self.assertEqual(rr_m["Load_Imbalance_ms"], 0)
        self.assertIsNone(calculate_load_imbalance_reduction(0, 0))

    def test_more_servers_than_requests(self):
        """Verify behavior when number of servers exceeds incoming request count."""
        servers = generate_server_names(5)  # 5 servers
        two_req_df = pd.DataFrame([
            {"Request_ID": "R1", "Arrival_Time": "t1", "Request_Type": "API", "Processing_Time_ms": 150, "Data_Size_MB": 1.0},
            {"Request_ID": "R2", "Arrival_Time": "t2", "Request_Type": "API", "Processing_Time_ms": 350, "Data_Size_MB": 2.0},
        ])

        rr_assign, rr_loads = round_robin_scheduler(two_req_df, servers)
        ll_assign, ll_loads = least_loaded_scheduler(two_req_df, servers)

        # Server 1 and 2 receive requests; Server 3, 4, 5 receive 0
        self.assertEqual(rr_assign.iloc[0]["Server"], "Server 1")
        self.assertEqual(rr_assign.iloc[1]["Server"], "Server 2")
        self.assertEqual(rr_loads["Server 3"], 0)
        self.assertEqual(rr_loads["Server 4"], 0)
        self.assertEqual(rr_loads["Server 5"], 0)

        # Least Loaded ties break in declaration order: S1 then S2
        self.assertEqual(ll_assign.iloc[0]["Server"], "Server 1")
        self.assertEqual(ll_assign.iloc[1]["Server"], "Server 2")
        self.assertEqual(sum(ll_loads.values()), 500)

    def test_zero_processing_time_rules(self):
        """
        Verify validation rules for zero processing time:
        - When allow_zero_processing_time=False (default), 0 is rejected.
        - When allow_zero_processing_time=True, 0 is permitted.
        - Negative processing times are ALWAYS rejected.
        """
        zero_df = pd.DataFrame([{
            "Request_ID": "REQ_ZERO",
            "Arrival_Time": "2026-10-20 10:00:00",
            "Request_Type": "API_Read",
            "Processing_Time_ms": 0,
            "Data_Size_MB": 0.5,
        }])

        # Default: 0 ms rejected
        with self.assertRaises(ValueError):
            load_and_validate_dataset(zero_df, allow_zero_processing_time=False)

        # With explicit permission: 0 ms accepted
        validated = load_and_validate_dataset(zero_df, allow_zero_processing_time=True)
        self.assertEqual(validated.iloc[0]["Processing_Time_ms"], 0)

        # Negative value: always rejected
        neg_df = pd.DataFrame([{
            "Request_ID": "REQ_NEG",
            "Arrival_Time": "2026-10-20 10:00:00",
            "Request_Type": "API_Read",
            "Processing_Time_ms": -50,
            "Data_Size_MB": 0.5,
        }])
        with self.assertRaises(ValueError):
            load_and_validate_dataset(neg_df, allow_zero_processing_time=True)

    def test_missing_dataset_file(self):
        """Verify FileNotFoundError is raised when file does not exist."""
        with self.assertRaises(FileNotFoundError):
            load_and_validate_dataset("missing_nonexistent_dataset.csv")

    def test_missing_required_columns(self):
        """Verify ValueError is raised if schema columns are missing."""
        invalid_cols_df = pd.DataFrame([{
            "Request_ID": "R1",
            "Arrival_Time": "t1",
            # Missing Request_Type, Processing_Time_ms, Data_Size_MB
        }])
        with self.assertRaises(ValueError) as ctx:
            load_and_validate_dataset(invalid_cols_df)
        self.assertIn("Missing required column", str(ctx.exception))

    def test_invalid_processing_time_values(self):
        """Verify non-numeric processing times raise ValueError."""
        non_numeric_df = pd.DataFrame([{
            "Request_ID": "R1",
            "Arrival_Time": "t1",
            "Request_Type": "API",
            "Processing_Time_ms": "fast_burst",
            "Data_Size_MB": 1.0,
        }])
        with self.assertRaises(ValueError):
            load_and_validate_dataset(non_numeric_df)

    def test_duplicate_request_ids(self):
        """Verify duplicate Request IDs raise ValueError."""
        dup_df = pd.DataFrame([
            {"Request_ID": "REQ_DUP", "Arrival_Time": "t1", "Request_Type": "API", "Processing_Time_ms": 100, "Data_Size_MB": 1.0},
            {"Request_ID": "REQ_DUP", "Arrival_Time": "t2", "Request_Type": "API", "Processing_Time_ms": 150, "Data_Size_MB": 1.0},
        ])
        with self.assertRaises(ValueError) as ctx:
            load_and_validate_dataset(dup_df)
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_invalid_server_counts(self):
        """Verify invalid server counts (0, negative, empty pool) are rejected."""
        with self.assertRaises(ValueError):
            generate_server_names(0)
        with self.assertRaises(ValueError):
            generate_server_names(-5)

        sample_df = pd.DataFrame([{
            "Request_ID": "R1", "Arrival_Time": "t1", "Request_Type": "API", "Processing_Time_ms": 100, "Data_Size_MB": 1.0
        }])
        with self.assertRaises(ValueError):
            round_robin_scheduler(sample_df, servers=[])
        with self.assertRaises(ValueError):
            least_loaded_scheduler(sample_df, servers=[])


class TestMetricsCalculations(unittest.TestCase):
    """TEST CASE 5: Verification of performance metrics and mathematical formulas."""

    def setUp(self):
        self.df = load_and_validate_dataset()
        self.servers = generate_server_names(3)
        self.rr_assign, self.rr_loads = round_robin_scheduler(self.df, self.servers)
        self.ll_assign, self.ll_loads = least_loaded_scheduler(self.df, self.servers)

        self.rr_m = calculate_algorithm_metrics("Round Robin", self.rr_assign, self.rr_loads)
        self.ll_m = calculate_algorithm_metrics("Least Loaded", self.ll_assign, self.ll_loads)

    def test_load_imbalance_formula(self):
        """Verify load imbalance equals maximum server load minus minimum server load."""
        rr_expected_imb = max(self.rr_loads.values()) - min(self.rr_loads.values())
        self.assertEqual(self.rr_m["Load_Imbalance_ms"], rr_expected_imb)
        self.assertEqual(self.rr_m["Load_Imbalance_ms"], 4252)

        ll_expected_imb = max(self.ll_loads.values()) - min(self.ll_loads.values())
        self.assertEqual(self.ll_m["Load_Imbalance_ms"], ll_expected_imb)
        self.assertEqual(self.ll_m["Load_Imbalance_ms"], 415)

    def test_estimated_makespan_formula(self):
        """Verify estimated makespan equals maximum assigned server workload."""
        self.assertEqual(self.rr_m["Estimated_Makespan_ms"], max(self.rr_loads.values()))
        self.assertEqual(self.rr_m["Estimated_Makespan_ms"], 67379)

        self.assertEqual(self.ll_m["Estimated_Makespan_ms"], max(self.ll_loads.values()))
        self.assertEqual(self.ll_m["Estimated_Makespan_ms"], 65396)

    def test_total_workload_equivalence(self):
        """Verify both algorithms process identical total workload on the same request set."""
        self.assertEqual(self.rr_m["Total_Workload_ms"], self.ll_m["Total_Workload_ms"])
        self.assertEqual(self.rr_m["Total_Workload_ms"], 195367)

    def test_reduction_percentage_zero_baseline_safety(self):
        """Verify reduction percentage handles zero or negative baseline without division by zero."""
        # Baseline = 0 -> returns None
        self.assertIsNone(calculate_load_imbalance_reduction(0.0, 0.0))
        self.assertIsNone(calculate_load_imbalance_reduction(0.0, 50.0))
        # Normal positive baseline
        reduction = calculate_load_imbalance_reduction(4252, 415)
        self.assertAlmostEqual(reduction, 90.24, places=2)


class TestIntegrationAndNonDestructiveSafety(unittest.TestCase):
    """TEST CASE 6: Verification of exports and non-destructive integrity."""

    def test_exported_csvs_match_simulation_results(self):
        """Verify exported CSV files match the exact simulation results for the current run."""
        df = load_and_validate_dataset()
        servers = generate_server_names(4)  # Test with 4 servers

        rr_assign, rr_loads = round_robin_scheduler(df, servers)
        ll_assign, ll_loads = least_loaded_scheduler(df, servers)
        rr_m = calculate_algorithm_metrics("Round Robin", rr_assign, rr_loads)
        ll_m = calculate_algorithm_metrics("Least Loaded", ll_assign, ll_loads)
        comp_df = build_performance_comparison_dataframe(rr_m, ll_m)
        sw_df = build_server_workload_dataframe(rr_m, ll_m)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            paths = export_simulation_reports(out_dir, rr_assign, ll_assign, comp_df, sw_df)

            # Read back exported files and verify contents
            read_rr = pd.read_csv(paths["round_robin_assignments"])
            self.assertEqual(len(read_rr), 1000)
            self.assertEqual(read_rr["Server"].nunique(), 4)

            read_ll = pd.read_csv(paths["least_loaded_assignments"])
            self.assertEqual(len(read_ll), 1000)
            self.assertEqual(read_ll["Server"].nunique(), 4)

            read_comp = pd.read_csv(paths["performance_comparison"])
            self.assertEqual(len(read_comp), 2)
            self.assertEqual(read_comp.iloc[0]["Algorithm"], "Round Robin")

    def test_original_dataset_preservation(self):
        """
        Verify the original dataset 'cloud_load_balancer_dataset_1000.csv'
        exists in the workspace root, retains all 1,000 rows, and was not replaced or deleted.
        """
        dataset_path = DEFAULT_DATASET_PATH
        self.assertTrue(dataset_path.is_file(), "Original dataset file must exist.")

        raw_df = pd.read_csv(dataset_path)
        self.assertEqual(len(raw_df), 1000)
        self.assertEqual(list(raw_df.columns), REQUIRED_COLUMNS)
        self.assertEqual(raw_df.iloc[0]["Request_ID"], "REQ0001")
        self.assertEqual(raw_df.iloc[-1]["Request_ID"], "REQ1000")


if __name__ == "__main__":
    unittest.main()
