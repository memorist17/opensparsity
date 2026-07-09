#!/usr/bin/env python
"""exp01の既存10,050地点がDEGURBAのどのクラスに属するかを集計する。

「B1センサス」の母集団定義をWSF自己流の閾値からDEGURBA（国際標準、人口密度ベース）
に切り替えるための下調べ。GHS-SMODラスタ（GeoTIFF, World Mollweide EPSG:54009, 1km）
に対して、os_vectors.csvの(lat, lon)をWGS84→Mollweideへ変換してサンプリングする。

DEGURBA L2 コード（GHS-SMOD legend, https://human-settlement.emergency.copernicus.eu/ghs_smod2023.php）:
    30: URBAN CENTRE GRID CELL
    23: DENSE URBAN CLUSTER GRID CELL
    22: SEMI-DENSE URBAN CLUSTER GRID CELL
    21: SUBURBAN OR PERI-URBAN GRID CELL
    13: RURAL CLUSTER GRID CELL
    12: LOW DENSITY RURAL GRID CELL       <- 対象（サンプリング母集団の一部）
    11: VERY LOW DENSITY RURAL GRID CELL  <- 対象（サンプリング母集団の一部）
    10: WATER GRID CELL
    NoData: -200

使い方:
    .venv/bin/python experiments/exp04_degurba_census/analyze_existing_degurba.py \
        --raster /path/to/GHS_SMOD_E2025_GLOBE_R2023A_54009_1000_V2_0.tif
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

HERE = Path(__file__).parent
OS_VECTORS = HERE.parent / "exp01_density_breakdown" / "os_vectors.csv"

DEGURBA_LABELS = {
    30: "urban_centre",
    23: "dense_urban_cluster",
    22: "semi_dense_urban_cluster",
    21: "suburban_periurban",
    13: "rural_cluster",
    12: "low_density_rural",
    11: "very_low_density_rural",
    10: "water",
    -200: "nodata",
}
TARGET_CLASSES = {11, 12}  # Low density rural / Very low density rural


def sample_degurba(raster_path: Path, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """WGS84の(lat, lon)配列に対応するDEGURBAコードを返す。"""
    with rasterio.open(raster_path) as src:
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        xs, ys = transformer.transform(lons, lats)
        rows_cols = [src.index(x, y) for x, y in zip(xs, ys)]
        band = src.read(1)
        codes = np.array([
            band[r, c] if 0 <= r < band.shape[0] and 0 <= c < band.shape[1] else -200
            for r, c in rows_cols
        ])
    return codes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raster", required=True, type=Path,
                     help="GHS-SMOD GeoTIFF（World Mollweide, 1km）へのパス")
    args = ap.parse_args()

    df = pd.read_csv(OS_VECTORS)
    print(f"exp01 os_vectors: {len(df)} 地点")

    codes = sample_degurba(args.raster, df["lat"].to_numpy(), df["lon"].to_numpy())
    df["degurba_code"] = codes
    df["degurba_class"] = df["degurba_code"].map(DEGURBA_LABELS).fillna("unknown")

    print("\n=== DEGURBAクラス分布（exp01の既存10,050地点） ===")
    print(df["degurba_class"].value_counts().to_string())

    target = df[df["degurba_code"].isin(TARGET_CLASSES)]
    print(f"\n対象2クラス（low/very-low density rural）合計: {len(target)} "
          f"({len(target) / len(df):.1%})")
    print("\nサブリージョン別（対象2クラスのみ）:")
    print(target["subregion"].value_counts().sort_index().to_string())

    out = HERE / "os_vectors_with_degurba.csv"
    df.to_csv(out, index=False)
    print(f"\n保存: {out}")


if __name__ == "__main__":
    main()
