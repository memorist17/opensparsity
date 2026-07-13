#!/usr/bin/env python
"""バルククラスタ(cluster 0)内部のK=6サブ類型 + 全代表点リストの生成。

cluster_analysis.py の K=3 は「バルク(96%) + 超疎斑点形態 + 長距離転移形態」という
外れ形態の分離だったため、バルク内部を K=6 でサブクラスタリングして類型を出す
（exp03のK=6カタログとの比較可能性も兼ねる）。
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

HERE = Path(__file__).parent
FEATURES = ["density", "lacunarity_mean", "lacunarity_slope", "r_crit",
            "mfa_alpha_width", "W_trans", "gamma", "Delta_D", "S_alpha"]
RNG = 42
K_SUB = 6

df = pd.read_csv(HERE / "cluster_result.csv")
X_all = df[FEATURES].to_numpy(float)
mu, sd = X_all.mean(0), X_all.std(0)

bulk = df[df["cluster"] == 0].copy()
Xz = (bulk[FEATURES].to_numpy(float) - mu) / sd
km = KMeans(n_clusters=K_SUB, random_state=RNG, n_init=10).fit(
    Xz, sample_weight=bulk["design_weight"].to_numpy(float))
bulk["subcluster"] = km.labels_
sizes = bulk.groupby("subcluster")["design_weight"].sum().sort_values(ascending=False)
remap = {old: new for new, old in enumerate(sizes.index)}
bulk["subcluster"] = bulk["subcluster"].map(remap)

df["subcluster"] = -1
df.loc[bulk.index, "subcluster"] = bulk["subcluster"]
df.to_csv(HERE / "cluster_result.csv", index=False)

out = {"k_sub": K_SUB, "subclusters": []}
for c in range(K_SUB):
    g = bulk[bulk["subcluster"] == c]
    gz = (g[FEATURES].to_numpy(float) - mu) / sd
    center = gz.mean(0)
    d = np.linalg.norm(gz - center, axis=1)
    reps = g.iloc[np.argsort(d)[:8]][["name", "lat", "lon", "country", "subregion",
                                       "density"]].to_dict("records")
    cls = g.groupby("degurba_class")["design_weight"].sum()
    cls = (cls / cls.sum()).round(3).to_dict()
    sr = g.groupby("subregion")["design_weight"].sum()
    sr = (sr / sr.sum()).sort_values(ascending=False).head(4).round(3).to_dict()
    out["subclusters"].append({
        "id": int(c), "n": int(len(g)),
        "weight_share_of_bulk": float(g["design_weight"].sum()
                                      / bulk["design_weight"].sum()),
        "profile_z": {f: round(float(center[j]), 3) for j, f in enumerate(FEATURES)},
        "profile_median": {f: float(g[f].median()) for f in FEATURES},
        "class_share": cls, "top_subregions": sr,
        "representatives": reps,
    })
(HERE / "subcluster_summary.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1))
for c in out["subclusters"]:
    tz = sorted(c["profile_z"].items(), key=lambda kv: -abs(kv[1]))[:3]
    print(f"sub{c['id']}: n={c['n']} share={c['weight_share_of_bulk']:.1%} "
          f"d_med={c['profile_median']['density']:.5f} distinctive={dict(tz)}")
print("saved: subcluster_summary.json")
