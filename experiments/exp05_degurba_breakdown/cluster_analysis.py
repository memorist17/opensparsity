#!/usr/bin/env python
"""DEGURBA実現サンプル16,474点のOS特徴空間クラスタリング。

- 9特徴z-score → KMeans（design_weightをsample_weightに使用）
- K選択: K=3..10 のシルエット係数（重みなし・2万点未満なので全点）
- 出力: cluster_result.csv（点別クラスタ+PCA座標）、cluster_summary.json
  （K選択スコア・クラスタ別プロファイル・地域分布・代表点）
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

HERE = Path(__file__).parent
FEATURES = ["density", "lacunarity_mean", "lacunarity_slope", "r_crit",
            "mfa_alpha_width", "W_trans", "gamma", "Delta_D", "S_alpha"]
RNG = 42

df = pd.read_csv(HERE / "realized_sample.csv").dropna(subset=FEATURES).reset_index(drop=True)
X = df[FEATURES].to_numpy(float)
w = df["design_weight"].to_numpy(float)
Xz = (X - X.mean(0)) / X.std(0)

# --- K選択 ---
sil = {}
for k in range(3, 11):
    km = KMeans(n_clusters=k, random_state=RNG, n_init=10).fit(Xz, sample_weight=w)
    # silhouetteは重み非対応なので無作為5000点で評価
    idx = np.random.default_rng(RNG).choice(len(Xz), 5000, replace=False)
    sil[k] = float(silhouette_score(Xz[idx], km.labels_[idx]))
    print(f"K={k}: silhouette={sil[k]:.4f} inertia={km.inertia_:.0f}")

best_k = max(sil, key=sil.get)
print(f"best K by silhouette: {best_k}")

# exp03(K=6)との比較しやすさとシルエットの両方を報告し、採用Kはシルエット最大
K = best_k
km = KMeans(n_clusters=K, random_state=RNG, n_init=10).fit(Xz, sample_weight=w)
df["cluster"] = km.labels_

# クラスタ番号を「加重サイズ降順」で振り直す（表示安定のため）
sizes = df.groupby("cluster")["design_weight"].sum().sort_values(ascending=False)
remap = {old: new for new, old in enumerate(sizes.index)}
df["cluster"] = df["cluster"].map(remap)

# --- PCA（可視化用） ---
pca = PCA(n_components=2, random_state=RNG)
P = pca.fit_transform(Xz)
df["pc1"], df["pc2"] = P[:, 0], P[:, 1]

# --- プロファイル（クラスタ別 z-score平均 / 生値中央値） ---
prof_z = df.groupby("cluster").apply(
    lambda g: pd.Series(
        ((g[FEATURES].to_numpy(float) - X.mean(0)) / X.std(0)).mean(0), index=FEATURES),
    include_groups=False)
prof_raw = df.groupby("cluster")[FEATURES].median()

# --- 地域・クラス分布 ---
def dist(col):
    t = df.groupby(["cluster", col])["design_weight"].sum().unstack(fill_value=0)
    return (t.div(t.sum(1), axis=0)).round(4)

summary = {
    "n": int(len(df)),
    "silhouette_by_k": sil,
    "chosen_k": int(K),
    "pca_variance": [float(v) for v in pca.explained_variance_ratio_],
    "pca_loadings": {f: [float(pca.components_[0][j]), float(pca.components_[1][j])]
                     for j, f in enumerate(FEATURES)},
    "clusters": [],
}
for c in range(K):
    g = df[df["cluster"] == c]
    # 代表点: 重心に最も近い6点
    cz = ((g[FEATURES].to_numpy(float) - X.mean(0)) / X.std(0))
    center = cz.mean(0)
    d = np.linalg.norm(cz - center, axis=1)
    reps = g.iloc[np.argsort(d)[:6]][["name", "lat", "lon", "country", "subregion",
                                       "density"]].to_dict("records")
    summary["clusters"].append({
        "id": int(c),
        "n": int(len(g)),
        "weight_share": float(g["design_weight"].sum() / df["design_weight"].sum()),
        "profile_z": {f: round(float(prof_z.loc[c, f]), 3) for f in FEATURES},
        "profile_median": {f: float(prof_raw.loc[c, f]) for f in FEATURES},
        "class_share": dist("degurba_class").loc[c].to_dict(),
        "top_subregions": dist("subregion").loc[c].sort_values(ascending=False)
                          .head(5).to_dict(),
        "representatives": reps,
    })

df[["name", "lat", "lon", "country", "subregion", "degurba_class",
    "design_weight", "cluster", "pc1", "pc2"] + FEATURES].to_csv(
    HERE / "cluster_result.csv", index=False)
(HERE / "cluster_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
print(f"saved: cluster_result.csv ({len(df)} rows), cluster_summary.json")
