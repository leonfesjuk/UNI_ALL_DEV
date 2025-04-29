import json
import pandas as pd
import numpy as np

def table_to_json(result):
    """
    Convert various data types to a JSON string representation of a table.
    
    Parameters:
    result : pandas DataFrame, numpy array, list, or dict
        The data to be converted to JSON.
    
    Returns:
    str : A JSON string representing the table data.
    
    Raises:
    ValueError : If the input data type is not supported.
    """
    
    if isinstance(result, pd.DataFrame):
        # Reset index to make sure it's not included in the data
        result = result.reset_index(drop=True)
        # If the result is a DataFrame
        # Convert Timestamp columns to strings
        for col in result.select_dtypes(include=['datetime64']).columns:
            result[col] = result[col].astype(str)
        
        # Convert DataFrame to a dictionary
        table_dict = {
            "columns": result.columns.tolist(),
            "data": result.to_dict(orient='records')
        }
        
    elif isinstance(result, np.ndarray):
        # If the result is a numpy array, convert it to a DataFrame
        df = pd.DataFrame(result)
        # Convert Timestamp columns to strings
        for col in df.select_dtypes(include=['datetime64']).columns:
            df[col] = df[col].astype(str)
        table_dict = {
            "columns": df.columns.tolist(),
            "data": df.values.tolist()
        }
    elif isinstance(result, list):
        # If the result is a list, try to convert it to a DataFrame
        df = pd.DataFrame(result)
        # Convert Timestamp columns to strings
        for col in df.select_dtypes(include=['datetime64']).columns:
            df[col] = df[col].astype(str)
        table_dict = {
            "columns": df.columns.tolist(),
            "data": df.values.tolist()
        }
    elif isinstance(result, dict):
        # If the result is a dictionary, convert it to a DataFrame
        df = pd.DataFrame.from_dict(result, orient='index').transpose()
        # Convert Timestamp columns to strings
        for col in df.select_dtypes(include=['datetime64']).columns:
            df[col] = df[col].astype(str)
        table_dict = {
            "columns": df.columns.tolist(),
            "data": df.values.tolist()
        }
    else:
        # Raise an error if the input type is not supported
        raise ValueError(f"Unsupported data type: {type(result)}")

    # Convert the dictionary to a JSON string
    return json.dumps(table_dict, default=str)