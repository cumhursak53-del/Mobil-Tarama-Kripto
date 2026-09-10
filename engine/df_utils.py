"""DataFrame secimi — pandas truthiness hatasini onler."""
from __future__ import annotations

from typing import Optional

import pandas as pd


def pick_frame(frames: dict[str, pd.DataFrame], *keys: str) -> Optional[pd.DataFrame]:
    """Ilk dolu (None degil, bos degil) frame'i dondur."""
    for key in keys:
        df = frames.get(key)
        if df is not None and not df.empty:
            return df
    return None


def is_usable_df(df: pd.DataFrame | None, min_rows: int = 1) -> bool:
    return df is not None and not df.empty and len(df) >= min_rows
