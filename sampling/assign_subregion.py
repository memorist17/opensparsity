#!/usr/bin/env python
"""候補点(lat, lon)にOverture divisionsの国境界で国コードを割り当て、UN Mサブリージョンに変換する。

国境界データは新規ダウンロードせず、既存パイプラインと同じOverture Maps（S3上のparquet、
DuckDB spatial拡張でST_Containsのポイント内判定）を再利用する。
（Natural Earth等の別データセットを持ち込まない設計判断。理由はsampling/README.md参照）

使い方:
    .venv/bin/python sampling/assign_subregion.py \
        --candidates sampling/candidates_raw.csv \
        --out sampling/candidates_with_subregion.csv
"""
import argparse
from pathlib import Path

import duckdb
import pandas as pd

from un_subregions import ISO2_TO_SUBREGION

OVERTURE_RELEASE = "2026-06-17.0"
DIVISIONS_PATH = (
    f"s3://overturemaps-us-west-2/release/{OVERTURE_RELEASE}"
    "/theme=divisions/type=division_area/*"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    df = pd.read_csv(args.candidates)
    print(f"入力候補点: {len(df):,} 件")

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    con.execute("SET s3_region='us-west-2';")
    con.register("candidates", df)

    # 国ポリゴン（陸地のみ）。ST_Union_Aggによる国単位の結合は複雑な海岸線で非常に重いため
    # 行わない——1国が複数行（島嶼国等）でも、点は高々1行にしか属さないのでそのまま結合できる
    con.execute(f"""
        CREATE TEMP TABLE countries AS
        SELECT country, CAST(geometry AS GEOMETRY) AS geom
        FROM read_parquet('{DIVISIONS_PATH}')
        WHERE subtype = 'country' AND is_land = true AND country IS NOT NULL
    """)
    n_countries = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT country) FROM countries"
    ).fetchone()
    print(f"国ポリゴン行: {n_countries[0]} 件（{n_countries[1]} 国）取得")

    print("空間インデックス作成中...")
    con.execute("CREATE INDEX country_geom_idx ON countries USING RTREE (geom)")

    print("空間結合中（候補点 in 国ポリゴン、RTreeインデックス使用）...")
    joined = con.execute("""
        SELECT c.*, co.country
        FROM candidates c
        LEFT JOIN countries co
          ON ST_Contains(co.geom, ST_Point(c.lon, c.lat))
        QUALIFY ROW_NUMBER() OVER (PARTITION BY c.lat, c.lon ORDER BY co.country) = 1
    """).fetchdf()

    n_matched = joined["country"].notna().sum()
    print(f"国コード判定: {n_matched:,}/{len(joined):,} 件マッチ "
          f"({n_matched/len(joined):.1%})")

    joined["subregion"] = joined["country"].map(ISO2_TO_SUBREGION)
    n_subregion = joined["subregion"].notna().sum()
    print(f"サブリージョン割当: {n_subregion:,}/{len(joined):,} 件 "
          f"({n_subregion/len(joined):.1%})")

    unmatched_countries = (
        joined.loc[joined["country"].notna() & joined["subregion"].isna(), "country"]
        .value_counts()
    )
    if len(unmatched_countries):
        print("\n未収録の国コード（un_subregions.pyへの追加を検討）:")
        print(unmatched_countries.to_string())

    out_df = joined.dropna(subset=["subregion"]).copy()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.out, index=False)
    print(f"\n保存: {args.out} ({len(out_df):,} 行)")
    print("\nサブリージョン×クラス 件数:")
    print(out_df.groupby(["subregion", "degurba_class"]).size().unstack(fill_value=0))


if __name__ == "__main__":
    main()
