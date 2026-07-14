#!/usr/bin/env python
"""指標の冗長性ジオメトリ: 「ダイヤルを回すとbandがどっち向きに動くか」の定量化。

3パネル:
  (a) UMAP勾配コンパス — 各指標のrank相関(U1,U2)を矢印で。同じ向き=冗長、直交=独立。
      これは可視化（UMAPの歪みと絡む）。
  (b) 特徴量空間のSpearman相関ブロック — 冗長性の"真"の裏付け。階層クラスタで並べ替え。
  (c) 有効次元数 — 相関行列の固有値スペクトルと参加率(participation ratio)。
      「12指標が実質何本の独立軸か」。

島(長距離転移形態)分離力も併記: 平均冗長でも離散構造検出には唯一効く指標を示す
（exp05 LOFO結果の視覚版）。
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.stats import spearmanr

HERE = Path(__file__).parent
FEAT = ["density", "lacunarity_mean", "lacunarity_slope", "r_crit", "mfa_alpha_width",
        "W_trans", "gamma", "Delta_D", "S_alpha",
        "building_count_density", "building_footprint_mean_m2", "road_length_density"]
LAB = {"density": "d", "lacunarity_mean": "Λ̄", "lacunarity_slope": "s_Λ",
       "r_crit": "r_crit", "mfa_alpha_width": "Δα", "W_trans": "W_tr", "gamma": "γ",
       "Delta_D": "ΔD", "S_alpha": "S_α", "building_count_density": "N_b",
       "building_footprint_mean_m2": "Ā_b", "road_length_density": "L_r"}
# 家族色（dataviz参照パレット）
FAM = {"density": 0, "building_count_density": 0, "building_footprint_mean_m2": 0,
       "road_length_density": 0, "mfa_alpha_width": 0,          # 量・被覆
       "gamma": 1, "lacunarity_slope": 1, "lacunarity_mean": 1,  # 疎・鋭さ
       "r_crit": 2, "W_trans": 2, "Delta_D": 2, "S_alpha": 2}    # 独立/島検出
FAM_COL = ["#2a78d6", "#eda100", "#4a3aa7"]
FAM_NAME = ["amount/coverage", "sparseness/sharpness", "independent/island"]
C_TEXT, C_MUTED = "#1c1b18", "#5b594f"

df = pd.read_csv(HERE / "cluster_result.csv", keep_default_na=False, na_values=[""])
extra = pd.read_csv(HERE / "realized_sample.csv", keep_default_na=False, na_values=[""],
                    usecols=["name", "building_count_density",
                             "building_footprint_mean_m2", "road_length_density"])
df = df.merge(extra, on="name", validate="one_to_one")

R = df[FEAT].rank().to_numpy()  # rank変換（裾が重い）
# --- (a) UMAP勾配 ---
u1 = df["umap1"].rank().to_numpy(); u2 = df["umap2"].rank().to_numpy()
grad = {f: (np.corrcoef(R[:, j], u1)[0, 1], np.corrcoef(R[:, j], u2)[0, 1])
        for j, f in enumerate(FEAT)}

# --- (b) Spearman相関行列 + 階層順 ---
rho, _ = spearmanr(df[FEAT].to_numpy())
dist = 1 - np.abs(rho)
Z = linkage(dist[np.triu_indices(len(FEAT), 1)], method="average")
order = leaves_list(Z)

# --- (c) 有効次元数 ---
eig = np.sort(np.linalg.eigvalsh(rho))[::-1]
pr = eig.sum() ** 2 / (eig ** 2).sum()          # participation ratio
cum = np.cumsum(eig) / eig.sum()
n90 = int(np.searchsorted(cum, 0.90) + 1)

# --- 島分離力 ---
isl = (df["cluster"] == 2).to_numpy()
sep = {f: (R[isl, j].mean() - R[:, j].mean()) / len(df)
       for j, f in enumerate(FEAT)}

# ===== 描画 =====
fig = plt.figure(figsize=(15, 5.2))
gs = fig.add_gridspec(1, 3, width_ratios=[1.05, 1.15, 0.9], wspace=0.32)

# (a) コンパス
axA = fig.add_subplot(gs[0])
axA.axhline(0, color=C_MUTED, lw=0.6, alpha=0.5)
axA.axvline(0, color=C_MUTED, lw=0.6, alpha=0.5)
th = np.linspace(0, 2 * np.pi, 100)
for rr in (0.3, 0.6, 0.9):
    axA.plot(rr * np.cos(th), rr * np.sin(th), color=C_MUTED, lw=0.4, alpha=0.3)
for f in FEAT:
    c1, c2 = grad[f]
    col = FAM_COL[FAM[f]]
    axA.annotate("", xy=(c1, c2), xytext=(0, 0),
                 arrowprops=dict(arrowstyle="-|>", color=col, lw=1.8, alpha=0.85))
    axA.text(c1 * 1.13, c2 * 1.13, LAB[f], color=col, fontsize=10,
             ha="center", va="center", fontweight="bold")
axA.set_xlim(-1.05, 1.05); axA.set_ylim(-1.05, 1.05)
axA.set_aspect("equal")
axA.set_xlabel("rank-corr with UMAP1", color=C_TEXT, fontsize=9)
axA.set_ylabel("rank-corr with UMAP2", color=C_TEXT, fontsize=9)
axA.set_title("(a) dial-gradient compass\nparallel arrows = redundant, orthogonal = independent",
              color=C_TEXT, fontsize=10.5)
for s in ["top", "right", "bottom", "left"]:
    axA.spines[s].set_visible(False)

# (b) 相関ブロック
axB = fig.add_subplot(gs[1])
M = rho[np.ix_(order, order)]
im = axB.imshow(M, cmap="RdBu_r", vmin=-1, vmax=1, aspect="equal")
labs = [LAB[FEAT[i]] for i in order]
cols = [FAM_COL[FAM[FEAT[i]]] for i in order]
axB.set_xticks(range(len(FEAT))); axB.set_yticks(range(len(FEAT)))
axB.set_xticklabels(labs, fontsize=9); axB.set_yticklabels(labs, fontsize=9)
for t, c in zip(axB.get_xticklabels(), cols): t.set_color(c)
for t, c in zip(axB.get_yticklabels(), cols): t.set_color(c)
axB.set_title("(b) Spearman correlation (clustered)\ndeep blue/red blocks = redundant families",
              color=C_TEXT, fontsize=10.5)
cb = fig.colorbar(im, ax=axB, fraction=0.046, pad=0.04)
cb.ax.tick_params(labelsize=8)

# (c) 有効次元
axC = fig.add_subplot(gs[2])
x = np.arange(1, len(eig) + 1)
axC.bar(x, eig, color="#2a78d6", alpha=0.75, width=0.7)
axC.axhline(1.0, color=C_MUTED, ls="--", lw=0.9)
axC.text(len(eig), 1.05, "eigenvalue = 1", color=C_MUTED, fontsize=8, ha="right")
axC2 = axC.twinx()
axC2.plot(x, cum, color="#eda100", lw=2, marker="o", ms=3)
axC2.axhline(0.90, color="#eda100", ls=":", lw=1)
axC2.set_ylim(0, 1.02); axC2.set_ylabel("cumulative variance", color="#c98500", fontsize=9)
axC2.axvline(n90, color="#c98500", ls=":", lw=1)
axC.set_xlabel("principal component", color=C_TEXT, fontsize=9)
axC.set_ylabel("eigenvalue", color="#2a78d6", fontsize=9)
axC.set_title(f"(c) effective dimensionality\nparticipation ratio PR={pr:.1f} / {n90} axes reach 90%",
              color=C_TEXT, fontsize=10.5)
for s in ["top"]:
    axC.spines[s].set_visible(False)

fig.suptitle("Metric redundancy geometry (DEGURBA rural, N=16,474, 12 metrics)",
             color=C_TEXT, fontsize=13, y=1.02)
fig.savefig(HERE / "redundancy_geometry.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# ===== 数値エクスポート =====
out = pd.DataFrame({
    "metric": [LAB[f] for f in FEAT],
    "family": [FAM_NAME[FAM[f]] for f in FEAT],
    "grad_U1": [grad[f][0] for f in FEAT],
    "grad_U2": [grad[f][1] for f in FEAT],
    "grad_angle_deg": [np.degrees(np.arctan2(*grad[f][::-1])) for f in FEAT],
    "grad_len": [np.hypot(*grad[f]) for f in FEAT],
    "island_separation": [sep[f] for f in FEAT],
})
out.to_csv(HERE / "redundancy_metrics.csv", index=False)
pd.DataFrame(rho, index=[LAB[f] for f in FEAT],
             columns=[LAB[f] for f in FEAT]).to_csv(HERE / "spearman_matrix.csv")

print(f"参加率(有効次元) PR = {pr:.2f}")
print(f"90%累積に必要な軸数 = {n90}")
print(f"固有値 > 1 の主成分数 = {(eig > 1).sum()}")
print("\n島(長距離転移形態)分離力 |sep|>0.4 の指標（＝離散構造の検出器）:")
for f in sorted(FEAT, key=lambda f: -abs(sep[f])):
    if abs(sep[f]) > 0.4:
        print(f"  {LAB[f]:<6}{sep[f]:+.2f}  (家族: {FAM_NAME[FAM[f]]})")
print("\n保存: redundancy_geometry.png / redundancy_metrics.csv / spearman_matrix.csv")
