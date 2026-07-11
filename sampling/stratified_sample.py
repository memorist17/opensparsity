#!/usr/bin/env python
"""サブリージョン×DEGURBAクラスの44層から層化抽出し、design_weightを計算する。

- 層: 22サブリージョン × 2 DEGURBAクラス（very_low_density_rural / low_density_rural）= 44層
- 層あたり目標点数: N_PER_STRATUM（既定700）。候補が届かない層はある分だけ全部使う
  （global_v2の`n_strata_all_pop`と同じ扱い、configs/global_v2_N100_clean.yaml参照）
- design_weight: Horvitz-Thompson型。
    層の2km格子全体セル数（推定） = 層内の候補点数 / 全体抽出率（extract_candidates.pyで
    記録したsample_fraction、クラスごとに一定）
    design_weight = 層の推定全体セル数 / 層から実際に抽出した点数
  【2026-07-12修正】当初はglobal_v2に倣い cos(lat) を掛けていたが誤り。cos(lat)補正は
  経緯度グリッド（緯度で1マスの実面積が縮む）用で、GHS-SMODはMollweide等積図法
  （ESRI:54009、全セル等面積）なので不要。掛けると高緯度の点を不当に軽くする歪みが
  逆に入る。層内の包含確率は一様なので重みは層内一定が正しい。
  （2026-07-10生成のfinal_sample.csvのdesign_weight列は旧式=cos(lat)入りの非推奨値。
   本番実行後に実現サンプルへ重みを再計算するため、分析ではそちらを使うこと）

使い方:
    .venv/bin/python sampling/stratified_sample.py \
        --candidates sampling/candidates_with_subregion.csv \
        --out sampling/final_sample.csv \
        --n-per-stratum 700 --seed 42
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--n-per-stratum", type=int, default=700)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    # keep_default_na=False: pandasのデフォルトNA判定はNamibiaのISO2コード"NA"を
    # 欠損値と誤認するため、countryを含むCSVでは無効化する（実際に2026-07-10に踏んだ）
    df = pd.read_csv(args.candidates, keep_default_na=False, na_values=[""])
    print(f"入力（国・サブリージョン割当済み候補点）: {len(df):,} 件")

    # クラスごとの全体抽出率（extract_candidates.pyでクラス単位一定のはず）
    sample_fraction_by_class = df.groupby("degurba_class")["sample_fraction"].first()
    print("\nクラスごとの抽出率:")
    print(sample_fraction_by_class.to_string())

    picked_rows = []
    stratum_report = []
    for (subregion, cls), g in df.groupby(["subregion", "degurba_class"]):
        n_available = len(g)
        n_target = min(args.n_per_stratum, n_available)
        idx = rng.choice(n_available, size=n_target, replace=False)
        picked = g.iloc[idx].copy()

        frac = sample_fraction_by_class.loc[cls]
        # 層の推定全体セル数(2km格子) = 層内候補点数 / 全体抽出率
        est_total_cells_in_stratum = n_available / frac
        # Mollweide等積格子なので層内の包含確率は一様 → 重みは層内一定（cos(lat)不要）
        picked["design_weight"] = est_total_cells_in_stratum / n_target
        picked_rows.append(picked)

        stratum_report.append({
            "subregion": subregion, "degurba_class": cls,
            "n_candidates_in_subsample": n_available,
            "est_total_cells": round(est_total_cells_in_stratum),
            "n_sampled": n_target,
            "pool_exhausted": n_available < args.n_per_stratum,
        })

    final = pd.concat(picked_rows, ignore_index=True)
    report = pd.DataFrame(stratum_report).sort_values(["degurba_class", "subregion"])

    # ops run --locations で使うためのname列（読みやすさ用、一意性を担保）
    class_short = {"very_low_density_rural": "vlow", "low_density_rural": "low"}
    subregion_slug = final["subregion"].str.lower().str.replace(r"[^a-z]+", "_", regex=True)
    final = final.reset_index(drop=True)
    final.insert(0, "name", [
        f"degurba_{subregion_slug.iloc[i]}_{class_short[final['degurba_class'].iloc[i]]}_{i}"
        for i in range(len(final))
    ])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(args.out, index=False)
    report_path = args.out.parent / f"{args.out.stem}_stratum_report.csv"
    report.to_csv(report_path, index=False)

    print(f"\n=== 層別レポート（44層） ===")
    print(report.to_string(index=False))

    n_exhausted = report["pool_exhausted"].sum()
    print(f"\n候補プール不足で目標{args.n_per_stratum}点に届かなかった層: "
          f"{n_exhausted}/{len(report)}")
    print(f"総サンプル数: {len(final):,}")
    print(f"\n保存: {args.out}")
    print(f"保存: {report_path}")


if __name__ == "__main__":
    main()
