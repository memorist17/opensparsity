#!/usr/bin/env python
"""Overtureカバレッジバイアスの検証: GHS-BUILT-S（衛星由来の建物被覆、Overtureの
地図書き込みと独立）と、opensparsityのdensity（Overture建物footprint被覆率）を
地点ごとに突き合わせる。

目的（ジャーナル対応の本丸）:
  「γが地域間で違う」のが実際の形態差か、単にOvertureの書き込み密度の差かを切り分ける。
  - GHS-BUILT-S built-up > 0 なのに Overture empty（failed）→ 未記載（データ欠落）
  - GHS-BUILT-S ≈ 0 で Overture empty → 本当に何も無い（正しいempty）
  層別に「未記載率」を推定し、Overtureカバレッジの怪しいサブリージョンを特定する。

必要データ（未取得、ユーザーの!curlでダウンロードが必要）:
  GHS_BUILT_S_E2025_GLOBE_R2023A_54009_1000_V1_0.zip（Mollweide 1km、全球、~200-400MB）
  URL（GHS-SMODと同じサーバー構造からの推定、404なら
  https://ghsl.jrc.ec.europa.eu/download.php で正しいリンクを確認）:
  https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E2025_GLOBE_R2023A_54009_1000/V1-0/GHS_BUILT_S_E2025_GLOBE_R2023A_54009_1000_V1_0.zip

使い方:
  .venv/bin/python experiments/exp05_degurba_breakdown/overture_bias_check.py \
      --raster ~/Downloads/ghs_built_s/GHS_BUILT_S_E2025_GLOBE_R2023A_54009_1000_V1_0.tif
"""
import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

HERE = Path(__file__).parent
ROOT = HERE.parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raster", required=True, type=Path,
                    help="GHS-BUILT-S GeoTIFF (Mollweide 1km)")
    args = ap.parse_args()

    sample = pd.read_csv(ROOT / "sampling/final_sample.csv",
                         keep_default_na=False, na_values=[""])
    con = sqlite3.connect(ROOT / "results_merged/results.db")
    db = pd.read_sql_query("SELECT lat, lon, status, density FROM locations", con)
    con.close()

    def key(lat, lon):
        return (round(float(lat), 6), round(float(lon), 6))
    db["_key"] = [key(a, b) for a, b in zip(db["lat"], db["lon"])]
    db = db.sort_values("status").drop_duplicates("_key", keep="first")
    sample["_key"] = [key(a, b) for a, b in zip(sample["lat"], sample["lon"])]
    df = sample.merge(db[["_key", "status", "density"]], on="_key", how="left")

    src = rasterio.open(args.raster)
    tr = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
    xs, ys = tr.transform(df["lon"].to_numpy(), df["lat"].to_numpy())
    # 2km観測窓に合わせ、中心セル+近傍3x3(=3km四方)の平均built-upを取る
    vals = np.full(len(df), np.nan)
    band = src.read(1)
    rows, cols = rasterio.transform.rowcol(src.transform, xs, ys)
    rows, cols = np.asarray(rows), np.asarray(cols)
    for i, (r, c) in enumerate(zip(rows, cols)):
        r0, r1 = max(r - 1, 0), min(r + 2, band.shape[0])
        c0, c1 = max(c - 1, 0), min(c + 2, band.shape[1])
        block = band[r0:r1, c0:c1].astype(float)
        block[block < 0] = np.nan  # nodata
        vals[i] = np.nanmean(block)
    df["ghs_built_m2"] = vals  # m2 of built-up per 1km cell (0-1e6)

    df["overture_empty"] = df["status"] != "done"
    # GHSが「建物あり」とみなす閾値: 1kmセルあたり1000m2 (0.1%) 以上
    df["ghs_has_building"] = df["ghs_built_m2"] >= 1000

    # 層別の未記載率: GHSに建物があるのにOvertureが空
    g = df.groupby(["subregion", "degurba_class"]).apply(
        lambda x: pd.Series({
            "n": len(x),
            "overture_empty_rate": x["overture_empty"].mean(),
            "ghs_hasbldg_rate": x["ghs_has_building"].mean(),
            "unmapped_rate": (x["overture_empty"] & x["ghs_has_building"]).mean(),
            "true_empty_rate": (x["overture_empty"] & ~x["ghs_has_building"]).mean(),
        }), include_groups=False).reset_index()
    g.to_csv(HERE / "overture_bias_by_stratum.csv", index=False)

    # doneの中での density vs GHS built-up の相関（測定の整合性）
    d = df[df["status"] == "done"].dropna(subset=["ghs_built_m2"])
    corr = np.corrcoef(np.log1p(d["density"] * 4e6), np.log1p(d["ghs_built_m2"]))[0, 1]

    print(f"=== Overtureカバレッジバイアス検証 ===")
    print(f"全体: overture_empty={df['overture_empty'].mean():.1%}, "
          f"うちGHSに建物あり(未記載疑い)={(df['overture_empty'] & df['ghs_has_building']).mean():.1%}, "
          f"GHSも空(真のempty)={(df['overture_empty'] & ~df['ghs_has_building']).mean():.1%}")
    print(f"done地点の log-density vs log-GHS built-up 相関: r={corr:.3f}")
    print("\n未記載疑い率の高い層 top10:")
    print(g.sort_values("unmapped_rate", ascending=False)
          [["subregion", "degurba_class", "overture_empty_rate", "unmapped_rate"]]
          .head(10).to_string(index=False))
    print(f"\n保存: {HERE / 'overture_bias_by_stratum.csv'}")


if __name__ == "__main__":
    main()
