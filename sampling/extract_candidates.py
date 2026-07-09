#!/usr/bin/env python
"""GHS-SMODラスタからDEGURBA最疎2クラス(11,12)の候補点を無作為抽出する。

設計方針（2026-07-10、opensparsity/experiments/exp04_degurba_census/README.md参照）:
- ラスタは1km解像度だが、OSパイプラインの分析窓は2km四方（config.yaml canvas.half_size_m=1000）。
  窓が重ならないよう、集約（多数決等）はせず**単純間引き band[::2, ::2] で2km格子に落とす**
  （集約はクラスごとに情報損失率が大きく異なるため採用しない、README参照）。
- 2km格子上のclass 11/12セルは合計約3,550万セル（11: 3,390万 / 12: 154万）ある。
  最終的な層化抽出（44層×600〜800点=約3万点）に対して十分すぎるため、
  国・サブリージョン判定コストを抑えるために先に無作為に一部だけ抜き出す
  （SAMPLE_PER_CLASS件、既定30万件/クラス=合計60万件。最終抽出数の20倍以上の余裕）。
- design_weight算出のため、抜き出した件数と2km格子上の全体件数（全数, 抽出前）を保存し、
  後段のstratified_sample.pyで「サブリージョン内の推定全体セル数 = 観測件数/抽出率」を計算する
  （Horvitz-Thompson型推定。抽出が完全無作為である前提が必要）。

使い方:
    .venv/bin/python sampling/extract_candidates.py \
        --raster ~/Downloads/ghs_smod_2025/GHS_SMOD_E2025_GLOBE_R2023A_54009_1000_V2_0.tif \
        --out sampling/candidates_raw.csv \
        --n-per-class 300000 --seed 42
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

TARGET_CLASSES = {11: "very_low_density_rural", 12: "low_density_rural"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raster", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--n-per-class", type=int, default=300_000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    with rasterio.open(args.raster) as src:
        band = src.read(1)
        transform = src.transform
        crs = src.crs

    # 2km格子化（単純間引き。集約なし、詳細はモジュールdocstring参照）
    band_2km = band[::2, ::2]
    print(f"元ラスタ(1km): {band.shape}  ->  2km格子: {band_2km.shape}")

    rows_out, cols_out, cls_out, is_subsample_out = [], [], [], []
    class_total_2km = {}

    for code, name in TARGET_CLASSES.items():
        rr, cc = np.where(band_2km == code)
        n_total = len(rr)
        class_total_2km[code] = n_total
        n_take = min(args.n_per_class, n_total)
        idx = rng.choice(n_total, size=n_take, replace=False)
        rows_out.append(rr[idx])
        cols_out.append(cc[idx])
        cls_out.append(np.full(n_take, code))
        print(f"  class {code} ({name}): 2km格子全体 {n_total:,} 件 -> "
              f"無作為抽出 {n_take:,} 件（抽出率 {n_take/n_total:.4%}）")

    rows = np.concatenate(rows_out)
    cols = np.concatenate(cols_out)
    codes = np.concatenate(cls_out)

    # 2km格子のrow/col -> 元ラスタのrow/col（間引きは2倍のスケール）-> Mollweide xy -> WGS84 lat/lon
    orig_rows = rows * 2
    orig_cols = cols * 2
    xs, ys = rasterio.transform.xy(transform, orig_rows, orig_cols)
    xs, ys = np.asarray(xs), np.asarray(ys)

    to_wgs84 = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    lons, lats = to_wgs84.transform(xs, ys)

    df = pd.DataFrame({
        "lat": lats, "lon": lons, "degurba_code": codes,
        "class_total_2km_cells": [class_total_2km[c] for c in codes],
        "class_n_sampled": [
            min(args.n_per_class, class_total_2km[c]) for c in codes
        ],
    })
    df["degurba_class"] = df["degurba_code"].map(TARGET_CLASSES)
    df["sample_fraction"] = df["class_n_sampled"] / df["class_total_2km_cells"]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)  # pyarrow非依存方針のためparquetではなくCSV
    print(f"\n保存: {args.out}  ({len(df):,} 行)")
    print(df["degurba_class"].value_counts().to_string())


if __name__ == "__main__":
    main()
