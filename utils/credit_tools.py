from typing import Dict, List, Optional, Tuple
import pandas as pd
import polars as pl
import chardet

def read_csv_with_encoding(file_path: str, **kwargs) -> pl.DataFrame:
    """
    Read a CSV file with automatic encoding detection.
    
    Args:
        file_path: Path to the CSV file
        **kwargs: Additional arguments to pass to pl.read_csv
        
    Returns:
        pl.DataFrame: The loaded dataframe
        
    Raises:
        ValueError: If the file cannot be read with any encoding
    """
    # List of encodings to try in order
    encodings = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']
    
    # First try to detect encoding
    with open(file_path, 'rb') as file:
        raw_data = file.read()
        detected = chardet.detect(raw_data)
        if detected['confidence'] > 0.8:
            encodings.insert(0, detected['encoding'])
    
    # Try each encoding
    for encoding in encodings:
        try:
            return pl.read_csv(file_path, encoding=encoding, **kwargs)
        except Exception as e:
            continue
            
    raise ValueError(f"Could not read file with any of the attempted encodings: {', '.join(encodings)}")

def calculate_credit_quality(data: pl.DataFrame, 
                           time_horizons: List[str] = ['CC02M', 'CC03M', 'CC04M', 'CC06M', 'CC12M'],
                           thresholds: Dict[str, float] = {
                               'CC02M': 0.007,
                               'CC03M': 0.014, 
                               'CC04M': 0.047,
                               'CC06M': 0.095
                           }) -> Tuple[pl.DataFrame, Dict[str, bool]]:
    """
    Calculate credit quality metrics and compare against thresholds.
    
    Args:
        data: DataFrame containing credit data
        time_horizons: List of credit quality columns to analyze
        thresholds: Dictionary of thresholds for each horizon
    
    Returns:
        Tuple containing:
        - DataFrame with credit quality metrics
        - Dictionary indicating which metrics exceed thresholds
    """
    # Validate input data has required columns
    missing_cols = [col for col in time_horizons if col not in data.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {', '.join(missing_cols)}")
        
    # Calculate credit quality metrics
    metrics = {}
    threshold_exceeded = {}
    
    for horizon in time_horizons:
        if horizon in data.columns:
            # Calculate average credit quality for this horizon
            avg_quality = data[horizon].mean()
            metrics[horizon] = avg_quality
            
            # Compare against threshold if one exists
            if horizon in thresholds:
                threshold_exceeded[horizon] = avg_quality > thresholds[horizon]
                
    return pl.DataFrame([metrics]), threshold_exceeded

def filter_portfolio(data: pl.DataFrame,
                    filters: Dict[str, List[str]]) -> pl.DataFrame:
    """
    Filter credit portfolio based on user parameters.
    
    Args:
        data: DataFrame containing credit data
        filters: Dictionary of column:values pairs to filter on
        
    Returns:
        Filtered DataFrame
    """
    filtered_data = data
    
    for column, values in filters.items():
        if column in data.columns:
            filtered_data = filtered_data.filter(
                pl.col(column).is_in(values)
            )
            
    return filtered_data

def group_and_analyze(data: pl.DataFrame,
                     group_cols: List[str],
                     metric_cols: List[str],
                     min_volume: int = 100) -> pl.DataFrame:
    """
    Group data and calculate metrics for each group.
    
    Args:
        data: DataFrame containing credit data
        group_cols: Columns to group by
        metric_cols: Metrics to calculate
        min_volume: Minimum volume threshold for groups
        
    Returns:
        DataFrame with grouped metrics
    """
    # Validate columns exist
    missing_group_cols = [col for col in group_cols if col not in data.columns]
    missing_metric_cols = [col for col in metric_cols if col not in data.columns]
    
    if missing_group_cols or missing_metric_cols:
        raise ValueError(
            f"Missing columns: {', '.join(missing_group_cols + missing_metric_cols)}"
        )
    
    # Group and aggregate
    grouped = data.groupby(group_cols).agg([
        pl.col(col).mean().alias(f"{col}_avg")
        for col in metric_cols
    ])
    
    # Add volume metric
    grouped = grouped.with_columns(
        volume=pl.len()
    )
    
    # Filter by minimum volume
    return grouped.filter(pl.col("volume") >= min_volume)

def identify_best_segments(grouped_data: pl.DataFrame,
                         volume_col: str,
                         risk_cols: List[str],
                         thresholds: Dict[str, float]) -> pl.DataFrame:
    """
    Identify segments with highest volume and acceptable risk levels.
    
    Args:
        grouped_data: Grouped DataFrame with metrics
        volume_col: Column name for volume metric
        risk_cols: Columns containing risk metrics
        thresholds: Risk thresholds for each metric
        
    Returns:
        DataFrame with best performing segments
    """
    filtered_data = grouped_data
    
    # Filter segments that meet all risk thresholds
    for col, threshold in thresholds.items():
        if col in grouped_data.columns:
            filtered_data = filtered_data.filter(
                pl.col(col) <= threshold
            )
            
    # Sort by volume descending
    return filtered_data.sort(volume_col, descending=True) 