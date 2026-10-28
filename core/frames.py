"""DataFrame comparison helpers."""
import pandas as pd


def frames_equal(first: pd.DataFrame, second: pd.DataFrame) -> bool:
    """Compare two DataFrames as text (ignoring dtypes and index labels)."""
    return (
        first.reset_index(drop=True).astype(str)
        .equals(second.reset_index(drop=True).astype(str))
    )
