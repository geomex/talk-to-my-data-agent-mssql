from typing import Dict, List, Optional, Tuple
import pandas as pd
import polars as pl

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
        - DataFrame with quality metrics
        - Dictionary indicating if each horizon meets threshold
    """
    quality_metrics = {}
    threshold_met = {}
    
    # Calculate quality for each horizon
    for horizon in time_horizons:
        if horizon in data.columns:
            quality = data[horizon].mean()
            quality_metrics[horizon] = quality
            
            # Compare against threshold if available
            if horizon in thresholds:
                threshold_met[horizon] = quality <= thresholds[horizon]
    
    return pd.DataFrame([quality_metrics]), threshold_met

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
    filtered_df = data.clone()
    
    for col, values in filters.items():
        if col in filtered_df.columns:
            filtered_df = filtered_df.filter(pl.col(col).is_in(values))
            
    return filtered_df

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
    # Ensure all group columns exist
    valid_group_cols = [col for col in group_cols if col in data.columns]
    
    # Group and aggregate
    grouped = data.groupby(valid_group_cols).agg([
        pl.col(metric).mean().alias(f"{metric}_AVG")
        for metric in metric_cols if metric in data.columns
    ] + [
        pl.count().alias("VOLUME")
    ])
    
    # Filter for minimum volume
    return grouped.filter(pl.col("VOLUME") >= min_volume)

def identify_best_segments(grouped_data: pl.DataFrame,
                         volume_col: str = "VOLUME",
                         risk_cols: List[str] = ['CC02M_AVG', 'CC03M_AVG', 'CC04M_AVG', 'CC06M_AVG'],
                         thresholds: Dict[str, float] = {
                             'CC02M_AVG': 0.007,
                             'CC03M_AVG': 0.014,
                             'CC04M_AVG': 0.047,
                             'CC06M_AVG': 0.095
                         }) -> pl.DataFrame:
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
    # Filter for segments meeting all thresholds
    mask = pl.lit(True)
    for col, threshold in thresholds.items():
        if col in grouped_data.columns:
            mask = mask & (pl.col(col) <= threshold)
    
    compliant_segments = grouped_data.filter(mask)
    
    # Sort by volume descending
    return compliant_segments.sort(volume_col, descending=True) 