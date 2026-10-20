"""
Data Loader Module for Cloud Server Load Balancing Simulator.
Handles dataset ingestion, path resolution, and rigorous validation.
"""

from pathlib import Path
from typing import Dict, Any, Union, Optional
import pandas as pd

# Resolve project root relative to this file's directory (src/ -> root)
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# Standard locations where dataset may reside
DEFAULT_DATASET_PATH: Path = PROJECT_ROOT / "cloud_load_balancer_dataset_1000.csv"
DATA_DIR_DATASET_PATH: Path = PROJECT_ROOT / "data" / "cloud_load_balancer_dataset_1000.csv"

# Expected schema for the load balancing trace
REQUIRED_COLUMNS = [
    "Request_ID",
    "Arrival_Time",
    "Request_Type",
    "Processing_Time_ms",
    "Data_Size_MB",
]


def resolve_dataset_path(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve dataset path reliably based on project root rather than terminal working directory.
    
    Args:
        custom_path: Optional user-specified path (absolute or relative to project root).
        
    Returns:
        Path: Resolved absolute path to the dataset file.
        
    Raises:
        FileNotFoundError: If the resolved dataset file cannot be located.
    """
    if custom_path is not None:
        p = Path(custom_path)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if not p.is_file():
            raise FileNotFoundError(
                f"Dataset not found at specified path: '{p.resolve()}'. "
                f"Please verify the file exists."
            )
        return p.resolve()

    # Try default root location first, then data/ subdirectory
    if DEFAULT_DATASET_PATH.is_file():
        return DEFAULT_DATASET_PATH.resolve()
    elif DATA_DIR_DATASET_PATH.is_file():
        return DATA_DIR_DATASET_PATH.resolve()
    else:
        raise FileNotFoundError(
            f"Default dataset not found. Looked for '{DEFAULT_DATASET_PATH.name}' in:\n"
            f"  1. {DEFAULT_DATASET_PATH.resolve()}\n"
            f"  2. {DATA_DIR_DATASET_PATH.resolve()}\n"
            f"Please ensure 'cloud_load_balancer_dataset_1000.csv' is present in the project directory."
        )


def load_and_validate_dataset(
    file_path: Optional[Union[str, Path]] = None,
    allow_empty: bool = False,
    allow_zero_processing_time: bool = False,
) -> pd.DataFrame:
    """
    Load the cloud workload dataset and validate schema, integrity, and numeric values.
    Does not silently drop or impute invalid records.
    
    Args:
        file_path: Optional custom path or file buffer.
        allow_empty: If True, allows an empty dataset with valid columns (default False).
        allow_zero_processing_time: If True, permits 0 ms processing times; rejects negative values.
        
    Returns:
        pd.DataFrame: Validated DataFrame containing the workload requests.
        
    Raises:
        FileNotFoundError: If the dataset file does not exist.
        ValueError: If required columns are missing, values are null,
                    duplicate Request IDs exist, or processing times are invalid.
    """
    if isinstance(file_path, pd.DataFrame):
        df = file_path.copy()
    elif file_path is None or isinstance(file_path, (str, Path)):
        resolved_path = resolve_dataset_path(file_path)
        df = pd.read_csv(resolved_path)
    else:
        # Supports file-like objects (e.g. Streamlit UploadedFile)
        df = pd.read_csv(file_path)

    # 1. Validate Required Columns
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Dataset validation failed: Missing required column(s): {missing_cols}. "
            f"Expected schema: {REQUIRED_COLUMNS}."
        )

    # 2. Validate Empty Dataset
    if len(df) == 0:
        if not allow_empty:
            raise ValueError("Dataset validation failed: The dataset contains 0 request rows.")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    # 3. Validate Missing / Null Values (Strict - No silent imputation)
    null_counts = df[REQUIRED_COLUMNS].isnull().sum()
    columns_with_nulls = null_counts[null_counts > 0]
    if not columns_with_nulls.empty:
        null_details = columns_with_nulls.to_dict()
        raise ValueError(
            f"Dataset validation failed: Missing values detected: {null_details}. "
            f"Silent imputation is disabled to ensure experimental integrity."
        )

    # 4. Validate Duplicate Request IDs
    duplicates = df[df["Request_ID"].duplicated(keep=False)]
    if not duplicates.empty:
        dup_ids = duplicates["Request_ID"].unique().tolist()
        raise ValueError(
            f"Dataset validation failed: Found {len(duplicates)} duplicate Request_ID entries. "
            f"Sample duplicate IDs: {dup_ids[:5]}."
        )

    # 5. Validate Processing_Time_ms (Must be numeric and positive / non-negative)
    proc_series = pd.to_numeric(df["Processing_Time_ms"], errors="coerce")
    if proc_series.isnull().any():
        invalid_rows = df[proc_series.isnull()][["Request_ID", "Processing_Time_ms"]]
        raise ValueError(
            f"Dataset validation failed: Found non-numeric Processing_Time_ms values at:\n"
            f"{invalid_rows.head(5)}."
        )
    if allow_zero_processing_time:
        if (proc_series < 0).any():
            negative_rows = df[proc_series < 0][["Request_ID", "Processing_Time_ms"]]
            raise ValueError(
                f"Dataset validation failed: Found negative Processing_Time_ms (< 0) at:\n"
                f"{negative_rows.head(5)}."
            )
    else:
        if (proc_series <= 0).any():
            non_positive = df[proc_series <= 0][["Request_ID", "Processing_Time_ms"]]
            raise ValueError(
                f"Dataset validation failed: Found non-positive Processing_Time_ms (<= 0) at:\n"
                f"{non_positive.head(5)}."
            )

    # 6. Validate Data_Size_MB (Must be numeric and non-negative)
    size_series = pd.to_numeric(df["Data_Size_MB"], errors="coerce")
    if size_series.isnull().any() or (size_series < 0).any():
        raise ValueError(
            "Dataset validation failed: Found invalid or negative Data_Size_MB values."
        )

    # Cast to standard clean types
    validated_df = df.copy()
    validated_df["Processing_Time_ms"] = proc_series.astype(int)
    validated_df["Data_Size_MB"] = size_series.astype(float)
    validated_df["Request_ID"] = validated_df["Request_ID"].astype(str).str.strip()
    validated_df["Request_Type"] = validated_df["Request_Type"].astype(str).str.strip()
    validated_df["Arrival_Time"] = validated_df["Arrival_Time"].astype(str).str.strip()

    return validated_df


def get_dataset_summary_statistics(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute statistical profile and distributions for the loaded workload trace.
    
    Args:
        df: Validated workload DataFrame.
        
    Returns:
        Dict[str, Any]: Key statistical figures and distributions.
    """
    if df.empty:
        return {
            "total_requests": 0,
            "total_workload_ms": 0,
            "mean_processing_time_ms": 0.0,
            "median_processing_time_ms": 0.0,
            "min_processing_time_ms": 0,
            "max_processing_time_ms": 0,
            "std_processing_time_ms": 0.0,
            "request_types_distribution": {},
            "total_data_size_mb": 0.0,
        }

    proc = df["Processing_Time_ms"]
    return {
        "total_requests": len(df),
        "total_workload_ms": int(proc.sum()),
        "mean_processing_time_ms": round(float(proc.mean()), 2),
        "median_processing_time_ms": round(float(proc.median()), 2),
        "min_processing_time_ms": int(proc.min()),
        "max_processing_time_ms": int(proc.max()),
        "std_processing_time_ms": round(float(proc.std()), 2) if len(df) > 1 else 0.0,
        "request_types_distribution": df["Request_Type"].value_counts().to_dict(),
        "total_data_size_mb": round(float(df["Data_Size_MB"].sum()), 2),
    }
