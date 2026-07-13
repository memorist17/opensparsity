#!/usr/bin/env python
"""t-SNE / UMAP 埋め込みの計算（PCAの分散カバー63.7%が不足との判断による非線形版）。

- 入力: cluster_result.csv（16,474点、9特徴z-score + cluster/subcluster済み）
- t-SNE: sklearn、PCA初期化、perplexity=50
- UMAP: n_neighbors=30, min_dist=0.1
- 出力: cluster_result.csv に tsne1/tsne2/umap1/umap2 列を追記
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.manifold import TSNE
import umap

HERE = Path(__file__).parent
FEATURES = ["density", "lacunarity_mean", "lacunarity_slope", "r_crit",
            "mfa_alpha_width", "W_trans", "gamma", "Delta_D", "S_alpha"]

df = pd.read_csv(HERE / "cluster_result.csv")
X = df[FEATURES].to_numpy(float)
Xz = (X - X.mean(0)) / X.std(0)
print(f"embedding {len(df):,} points...")

ts = TSNE(n_components=2, perplexity=50, init="pca", random_state=42,
          max_iter=1000, verbose=1).fit_transform(Xz)
df["tsne1"], df["tsne2"] = ts[:, 0], ts[:, 1]
print("t-SNE done")

um = umap.UMAP(n_components=2, n_neighbors=30, min_dist=0.1,
               random_state=42, verbose=True).fit_transform(Xz)
df["umap1"], df["umap2"] = um[:, 0], um[:, 1]
print("UMAP done")

df.to_csv(HERE / "cluster_result.csv", index=False)
print("saved: cluster_result.csv (+tsne/umap columns)")
