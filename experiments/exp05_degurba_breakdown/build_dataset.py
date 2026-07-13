#!/usr/bin/env python
"""実現サンプルの構築: 統合DBの結果と final_sample.csv の層情報を結合し、
実現サンプルへの design_weight を再計算する。

結合キー: (round(lat,6), round(lon,6))
  remainingリスト経由の地点はCSV再書き出しで座標が15桁に丸まっており
  ビット一致では結合できないため（2026-07-13に実測）。1e-6度 ≈ 0.1m で十分一意。

重みの考え方（cos(lat)バグ修正後、Mollweide等積格子）:
  - 層 h の推定全体セル数 M_h = 層内候補数 / クラス別抽出率（stratum_reportから）
  - 選抜確率は層内一様なので、選抜点の重み = M_h / n_attempted_h
  - 「done のみ」で形態分析する場合、empty(failed)は無作為欠測ではなく
    『Overtureに何も無いセル』という構造的カテゴリ。母集団を
    「Overtureに内容のあるセル」と再定義すると、その推定総数は
    M_h × (n_done_h / n_attempted_h)、doneの重みは M_h / n_attempted_h（層内一定）。
  - empty率そのものは層別に empty_h = n_failed_h / n_attempted_h で推定する。

出力:
  realized_sample.csv   done地点の全指標 + 層 + design_weight
  stratum_realized.csv  層別: attempted/done/failed/empty率/重み
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
ROOT = HERE.parent.parent

def key(lat, lon):
    return (round(float(lat), 6), round(float(lon), 6))

def main():
    sample = pd.read_csv(ROOT / "sampling/final_sample.csv",
                         keep_default_na=False, na_values=[""])
    report = pd.read_csv(ROOT / "sampling/final_sample_stratum_report.csv")

    con = sqlite3.connect(ROOT / "results_merged/results.db")
    db = pd.read_sql_query("SELECT * FROM locations", con)
    con.close()

    # 同一地点がビット違い座標で複数行あり得るため、丸めキーで dedup（done優先）
    db["_key"] = [key(a, b) for a, b in zip(db["lat"], db["lon"])]
    db = db.sort_values("status")  # 'done' < 'failed' なので done が先
    db = db.drop_duplicates("_key", keep="first")

    sample["_key"] = [key(a, b) for a, b in zip(sample["lat"], sample["lon"])]
    merged = sample.merge(
        db.drop(columns=["lat", "lon", "name"]), on="_key", how="left",
        validate="one_to_one",
    )
    n_missing = merged["status"].isna().sum()
    print(f"final_sample {len(sample):,} 件中 DB未マッチ {n_missing} 件")
    assert n_missing == 0, "カバレッジ欠落あり"

    # 層別の実現状況と重み
    strat = merged.groupby(["subregion", "degurba_class"]).agg(
        n_attempted=("status", "size"),
        n_done=("status", lambda s: (s == "done").sum()),
    ).reset_index()
    strat["n_failed"] = strat["n_attempted"] - strat["n_done"]
    strat["empty_rate"] = strat["n_failed"] / strat["n_attempted"]

    report = report.rename(columns={"n_sampled": "n_planned"})
    strat = strat.merge(
        report[["subregion", "degurba_class", "est_total_cells", "pool_exhausted"]],
        on=["subregion", "degurba_class"], validate="one_to_one",
    )
    # 選抜点の重み（層内一定）。doneのみの分析でも同じ値を使う（母集団を
    # 「内容のあるセル」に再定義した場合の重みと一致する。docstring参照）
    strat["design_weight"] = strat["est_total_cells"] / strat["n_attempted"]
    strat["est_nonempty_cells"] = (
        strat["est_total_cells"] * strat["n_done"] / strat["n_attempted"]
    ).round().astype(int)

    merged = merged.drop(columns=["design_weight"])  # 旧cos(lat)入り列を破棄
    merged = merged.merge(
        strat[["subregion", "degurba_class", "design_weight"]],
        on=["subregion", "degurba_class"], validate="many_to_one",
    )

    done = merged[merged["status"] == "done"].drop(columns=["_key", "status", "error"])
    done.to_csv(HERE / "realized_sample.csv", index=False)
    strat.to_csv(HERE / "stratum_realized.csv", index=False)

    print(f"realized_sample.csv: {len(done):,} 行（done のみ）")
    print(f"stratum_realized.csv: {len(strat)} 層")
    print("\n=== 全体 ===")
    print(f"attempted {len(merged):,} / done {len(done):,} "
          f"({len(done)/len(merged):.1%}) / empty {1-len(done)/len(merged):.1%}")

if __name__ == "__main__":
    main()
