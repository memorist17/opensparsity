#!/usr/bin/env python
"""global_v2 の保存済み曲線から論文 表1 の9次元 OS ベクトルを組み立てる。

入力（WSL から転送済み、旧リポジトリの outputs/）:
  - metrics_global_v2_batch{0..8}.csv
  - real_world_global_v2/<lat>_<lon>/{percolation.csv, mfa_spectrum.csv}
出力:
  - os_vectors.csv（このディレクトリ）
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from opensparsity.indicators.advanced import (
    compute_fractal_dimension_gap,
    compute_mfa_spectrum_skewness,
    compute_percolation_critical_slope,
    compute_percolation_transition_width,
    find_r_crit_max_slope,
)

OLD_REPO = Path("/Users/kotaronomac/dev/OS/251229_repro_apple")
DATA_DIR = OLD_REPO / "outputs" / "real_world_global_v2"
METRICS_GLOB = OLD_REPO / "outputs" / "metrics"
OUT = Path(__file__).parent / "os_vectors.csv"

# --- メトリクス読み込み ---
frames = [pd.read_csv(p) for p in sorted(METRICS_GLOB.glob("metrics_global_v2_batch[0-9].csv"))]
df = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["lat", "lon"], keep="last")
print(f"metrics rows: {len(df)}")

# --- 地点ディレクトリの索引（4桁丸めで対応付け） ---
dir_index = {}
for d in DATA_DIR.iterdir():
    if not d.is_dir():
        continue
    try:
        lat_s, lon_s = d.name.split("_", 1)
        dir_index[(round(float(lat_s), 4), round(float(lon_s), 4))] = d
    except ValueError:
        continue
print(f"location dirs: {len(dir_index)}")

rows = []
n_no_dir = n_no_perc = n_nan = 0
for rec in tqdm(df.to_dict("records"), desc="assembling"):
    key = (round(float(rec["lat"]), 4), round(float(rec["lon"]), 4))
    loc_dir = dir_index.get(key)
    if loc_dir is None:
        n_no_dir += 1
        continue

    perc_path = loc_dir / "percolation.csv"
    mfa_path = loc_dir / "mfa_spectrum.csv"
    if not perc_path.exists() or not mfa_path.exists():
        n_no_perc += 1
        continue

    try:
        perc = pd.read_csv(perc_path)
        mfa = pd.read_csv(mfa_path)
        r_crit = find_r_crit_max_slope(perc)
        gamma = compute_percolation_critical_slope(perc, r_crit=r_crit)
        w_trans = compute_percolation_transition_width(perc)
        delta_d = compute_fractal_dimension_gap(mfa)
        s_alpha = compute_mfa_spectrum_skewness(mfa)
    except Exception:
        n_no_perc += 1
        continue

    row = {
        "name": rec["name"], "lat": rec["lat"], "lon": rec["lon"],
        "quintile": rec.get("quintile"), "subregion": rec.get("subregion"),
        "country_iso": rec.get("country_iso"), "density_wsf": rec.get("density_wsf"),
        # 9次元 OS ベクトル（論文 表1）
        "density": rec["density"],
        "lacunarity_mean": rec["lacunarity_mean"],
        "lacunarity_slope": rec["lacunarity_slope"],   # = s_Λ = β
        "r_crit": r_crit,
        "mfa_alpha_width": rec["mfa_alpha_width"],
        "W_trans": w_trans,
        "gamma": gamma,
        "Delta_D": delta_d,
        "S_alpha": s_alpha,
    }
    os_cols = ["density", "lacunarity_mean", "lacunarity_slope", "r_crit",
               "mfa_alpha_width", "W_trans", "gamma", "Delta_D", "S_alpha"]
    if any(pd.isna(row[c]) for c in os_cols):
        n_nan += 1
        continue
    rows.append(row)

out_df = pd.DataFrame(rows)
out_df.to_csv(OUT, index=False)
print(f"\n完成: {len(out_df)} 地点 -> {OUT}")
print(f"除外: ディレクトリ無し={n_no_dir}, 曲線無し/読込失敗={n_no_perc}, NaN={n_nan}")
print(f"密度レンジ: {out_df['density'].min():.5f} - {out_df['density'].max():.5f}")
print(out_df.groupby("quintile").size().to_string())
