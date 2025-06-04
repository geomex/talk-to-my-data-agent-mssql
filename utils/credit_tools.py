from typing import Dict, List, Optional, Tuple
import pandas as pd
import polars as pl
import chardet
from utils.logging_helper import get_logger

logger = get_logger()

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
            logger.info(f"Detected encoding {detected['encoding']} with confidence {detected['confidence']}")
    
    # Try each encoding
    last_error = None
    for encoding in encodings:
        try:
            logger.info(f"Attempting to read CSV with encoding: {encoding}")
            
            # Read the CSV file
            df = pl.read_csv(file_path, encoding=encoding, **kwargs)
            logger.info(f"Successfully read CSV with {len(df.columns)} columns and {df.height} rows")
            
            # Ensure all column names are strings
            df = df.rename({col: str(col) for col in df.columns})
            
            # Convert any period columns to string
            for col in df.columns:
                if 'period' in str(df[col].dtype).lower():
                    df = df.with_columns(pl.col(col).cast(pl.Utf8))
                    logger.info(f"Converted period column {col} to string")
            
            # Ensure the DataFrame is not empty
            if df.height == 0:
                raise ValueError("The CSV file is empty")
            
            # Verify data can be converted to records
            try:
                records = df.to_dicts()
                logger.info(f"Successfully converted DataFrame to {len(records)} records")
                return df
            except Exception as e:
                last_error = ValueError(f"Failed to convert DataFrame to records: {str(e)}")
                logger.error(f"Failed to convert DataFrame to records: {str(e)}")
                continue
                
        except Exception as e:
            last_error = e
            logger.error(f"Failed to read CSV with encoding {encoding}: {str(e)}")
            continue
            
    if last_error:
        error_msg = f"Could not read file with any of the attempted encodings ({', '.join(encodings)}): {str(last_error)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    else:
        error_msg = f"Could not read file with any of the attempted encodings: {', '.join(encodings)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

def calculate_credit_quality(data: pl.DataFrame, 
                           time_horizons: List[str] = ['CC02M', 'CC03M', 'CC04M', 'CC05M', 'CC06M', 'CC09M', 'CC12M'],
                           thresholds: Dict[str, float] = {
                               'CC02M': 0.007,
                               'CC03M': 0.014, 
                               'CC04M': 0.047,
                               'CC05M': 0.071,  # Interpolated value between CC04M and CC06M
                               'CC06M': 0.095,
                               'CC09M': 0.143   # Interpolated value between CC06M and CC12M
                           }) -> Tuple[pl.DataFrame, Dict[str, bool]]:
    """
    Calculate credit quality metrics and compare against thresholds.
    
    Args:
        data: DataFrame containing credit data
        time_horizons: List of credit quality columns to analyze
        thresholds: Dictionary of thresholds for each horizon. Default values:
            - CC02M: 0.7%
            - CC03M: 1.4%
            - CC04M: 4.7%
            - CC05M: 7.1% (interpolated)
            - CC06M: 9.5%
            - CC09M: 14.3% (interpolated)
    
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
            # Convert to float and handle any potential NaN values
            horizon_data = data[horizon].astype(float)
            # Calculate quality as sum/count (mean)
            quality = horizon_data.sum() / len(data)
            metrics[horizon] = quality
            
            # Compare against threshold if one exists
            if horizon in thresholds:
                threshold_exceeded[horizon] = quality > thresholds[horizon]
                
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
                         volume_cols: List[str],
                         risk_cols: List[str],
                         thresholds: Dict[str, float]) -> pl.DataFrame:
    """
    Identify segments with highest volume and acceptable risk levels.
    
    Args:
        grouped_data: Grouped DataFrame with metrics
        volume_cols: List of volume columns to consider
        risk_cols: Columns containing risk metrics
        thresholds: Risk thresholds for each metric
        
    Returns:
        DataFrame with best performing segments
    """
    filtered_data = grouped_data
    
    # Filter segments that meet all risk thresholds
    for risk_col in risk_cols:
        if risk_col in thresholds:
            filtered_data = filtered_data.filter(
                pl.col(risk_col) <= thresholds[risk_col]
            )
    
    # Filter segments that meet volume threshold
    for vol_col in volume_cols:
        if vol_col in grouped_data.columns:
            filtered_data = filtered_data.filter(
                pl.col(vol_col) >= 100
            )
    
    return filtered_data

def analyze_data(dfs):
    import polars as pl
    import pandas as pd

    # Access the DataAgente dataframe
    df = dfs['DataAgente']

    # Convert to pandas for easier manipulation
    df = df.to_pandas()

    # Define all time horizons for calculation
    time_horizons = ['CC02M', 'CC03M', 'CC04M', 'CC05M', 'CC06M', 'CC12M']
    
    # Define only the thresholds we need to check against appetite
    thresholds = {
        'CC02M': 0.007,  # 0.7%
        'CC03M': 0.014,  # 1.4%
        'CC04M': 0.047,  # 4.7%
        'CC06M': 0.095   # 9.5%
    }

    def calculate_credit_quality(data, time_horizons):
        """
        Calculate credit quality metrics for all horizons.
        Returns both the metrics and a validation against thresholds where applicable.
        """
        metrics = {}
        total_records = len(data)
        
        # Calculate quality metrics for all horizons
        for horizon in time_horizons:
            if horizon in data.columns:
                # Convert to float and handle any potential NaN values
                horizon_data = data[horizon].astype(float)
                # Calculate quality as sum/count (mean)
                quality = horizon_data.sum() / total_records
                metrics[horizon] = quality
            else:
                logger.warning(f"Column {horizon} not found in data")
        
        # Check against appetite thresholds where applicable
        exceeds_thresholds = {
            horizon: metrics.get(horizon, 0) > threshold
            for horizon, threshold in thresholds.items()
            if horizon in metrics
        }
        
        return pd.DataFrame([metrics]), exceeds_thresholds

    # Calculate overall credit quality
    credit_quality_df, exceeds_thresholds = calculate_credit_quality(df, time_horizons)

    # If NROSCOREPREMIUM exists, create ranges and analyze by groups
    result_df = credit_quality_df
    if 'NROSCOREPREMIUM' in df.columns:
        # Create score ranges (you might want to adjust these ranges)
        df['SCORE_RANGE'] = pd.qcut(df['NROSCOREPREMIUM'], q=5, labels=['Very Low', 'Low', 'Medium', 'High', 'Very High'])
        
        # Group by score range and calculate metrics
        grouped_results = []
        for score_range in df['SCORE_RANGE'].unique():
            group_data = df[df['SCORE_RANGE'] == score_range]
            group_metrics, group_exceeds = calculate_credit_quality(group_data, time_horizons)
            
            # Add score range and count information
            group_metrics['SCORE_RANGE'] = score_range
            group_metrics['COUNT'] = len(group_data)
            
            grouped_results.append(group_metrics)
        
        if grouped_results:
            result_df = pd.concat(grouped_results, ignore_index=True)
            # Sort by CC02M (as per workflow) and count
            result_df = result_df.sort_values(['CC02M', 'COUNT'], ascending=[True, False])

    return {'data': result_df} 