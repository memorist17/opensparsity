#!/usr/bin/env python
"""results.dbで未着手（done/failedいずれでもない）の地点だけを抽出した残りリストを作る。

バッチ再起動時にfailed地点の再試行やdoneスキャンで時間を浪費しないための補助。
--lo/--hi で元CSVのインデックス範囲（このマシンの担当分）に絞れる。

使い方:
    .venv/bin/python sampling/export_remaining.py \
        --locations sampling/final_sample.csv --db results/results.db \
        --lo 0 --hi 27710 --out sampling/remaining.csv
"""
import argparse
import sqlite3
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--locations", required=True, type=Path)
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--lo", type=int, default=0)
    ap.add_argument("--hi", type=int, default=None)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    df = pd.read_csv(args.locations, keep_default_na=False, na_values=[""])
    hi = args.hi if args.hi is not None else len(df)
    df = df.iloc[args.lo:hi]

    con = sqlite3.connect(args.db)
    attempted = set(con.execute("SELECT lat, lon FROM locations").fetchall())
    con.close()

    mask = [((lat, lon) not in attempted) for lat, lon in zip(df["lat"], df["lon"])]
    remaining = df[mask]
    remaining.to_csv(args.out, index=False)
    print(f"担当範囲 [{args.lo}, {hi}): {len(df):,} 件中 "
          f"処理済み {len(df) - len(remaining):,} / 残り {len(remaining):,}")
    print(f"保存: {args.out}")


if __name__ == "__main__":
    main()
