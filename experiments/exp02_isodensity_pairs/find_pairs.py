#!/usr/bin/env python
"""同一密度・異形態ペアの抽出（ストーリー案1の主図の素材）。

「密度がほぼ同じでも OS 空間上の距離は大きく変わりうる」ことを示すため、
密度が近い地点対の中から OS 距離が最大／最小のペアを取り出す。
OS 距離への各特徴の寄与も内訳表示し、γ・W_trans が距離を駆動していることを見る。
"""
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
VECS = Path(__file__).parents[1] / "exp01_density_breakdown" / "os_vectors.csv"
FEATURES = ["density", "lacunarity_mean", "lacunarity_slope", "r_crit",
            "mfa_alpha_width", "W_trans", "gamma", "Delta_D", "S_alpha"]
DYN = ["W_trans", "gamma"]

df = pd.read_csv(VECS)
# 実質的な集落のみ（WSF B1 下限 0.005 相当以上の建物密度）に限定。
# 極小密度のノイズ地点を「同一密度ペア」に選ばないため
df = df[df["density"] >= 0.003].reset_index(drop=True)

# 全体で z-score（OS 空間の定義に合わせる）
Z = df[FEATURES].to_numpy(float)
mu, sd = Z.mean(0), Z.std(0)
sd[sd == 0] = 1
Zn = (Z - mu) / sd
dens = df["density"].to_numpy()

# 密度が近い（相対差 <= 2%）ペアのみを候補にする
REL = 0.02
results = []
order = np.argsort(dens)
# 近傍だけ見れば十分（ソート順で前後 window 内）
WINDOW = 60
for ii in range(len(order)):
    i = order[ii]
    for jj in range(ii + 1, min(ii + WINDOW, len(order))):
        j = order[jj]
        di, dj = dens[i], dens[j]
        if abs(di - dj) / ((di + dj) / 2) > REL:
            continue
        diff = Zn[i] - Zn[j]
        dist = float(np.sqrt((diff ** 2).sum()))
        dyn_share = float((diff[[FEATURES.index(f) for f in DYN]] ** 2).sum()
                          / (diff ** 2).sum()) if dist > 0 else 0.0
        dens_share = float(diff[0] ** 2 / (diff ** 2).sum()) if dist > 0 else 0.0
        results.append({
            "i": i, "j": j, "name_i": df.name[i], "name_j": df.name[j],
            "lat_i": df.lat[i], "lon_i": df.lon[i],
            "lat_j": df.lat[j], "lon_j": df.lon[j],
            "density_i": di, "density_j": dj, "os_dist": dist,
            "dyn_share": dyn_share, "dens_share": dens_share,
            "quintile_i": df.quintile[i], "quintile_j": df.quintile[j],
        })

pairs = pd.DataFrame(results)
print(f"密度近接ペア候補: {len(pairs)}（相対密度差 <= {REL:.0%}）", flush=True)

# 密度帯ごと（低・中・高）に「OS距離最大かつダイナミクス主導」なペアを提示
def band(d):
    if d < 0.0135:   # Q1-Q2 相当
        return "sparse"
    if d < 0.061:    # Q3-Q4 相当
        return "mid"
    return "dense"

pairs["band"] = pairs[["density_i", "density_j"]].mean(1).apply(band)

out_rows = []
for b in ["sparse", "mid", "dense"]:
    sub = pairs[pairs.band == b]
    if len(sub) == 0:
        continue
    # ダイナミクス主導ペア: os_dist が上位25%かつ dyn_share 最大
    thr = sub.os_dist.quantile(0.75)
    cand = sub[sub.os_dist >= thr]
    far = cand.loc[cand.dyn_share.idxmax()]
    near = sub.loc[sub.os_dist.idxmin()]
    print(f"\n=== {b} 帯 ===", flush=True)
    print(f"  ダイナミクス主導・遠ペア: {far.name_i}({far.density_i:.4f}) vs {far.name_j}"
          f"({far.density_j:.4f}) OS距離={far.os_dist:.2f} "
          f"γ+W_trans寄与={far.dyn_share:.0%} 密度寄与={far.dens_share:.0%}", flush=True)
    print(f"    lat/lon: ({far.lat_i},{far.lon_i}) / ({far.lat_j},{far.lon_j})", flush=True)
    print(f"  最近ペア: {near.name_i} vs {near.name_j} OS距離={near.os_dist:.2f}", flush=True)
    for tag, row in [("far", far), ("near", near)]:
        r = row.to_dict(); r["pair_type"] = tag
        out_rows.append(r)

pd.DataFrame(out_rows).to_csv(HERE / "isodensity_pairs.csv", index=False)
print(f"\n保存: {HERE/'isodensity_pairs.csv'}", flush=True)
