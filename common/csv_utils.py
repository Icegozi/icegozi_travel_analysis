"""Quy ước đọc/ghi CSV cho toàn bộ dự án."""

from pathlib import Path

import pandas as pd


def export_csv(frame: pd.DataFrame, output_file: Path) -> None:
    """Xuất CSV dấu phẩy, UTF-8 BOM để mở đúng tiếng Việt trong Excel."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_file, index=False, sep=",", encoding="utf-8-sig")
