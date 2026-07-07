#!/usr/bin/env python
"""密度の情報崩壊点の推定: 移動窓 × leave-one-feature-out 感度分析。

分離度の定義は卒業論文 §感度分析と同一:
  9次元 z-score 空間の平均ペアワイズ距離。特徴 f の寄与 = f 除去時の距離減少率(%)。
無相関基準: 9特徴が独立なら任意の1特徴除去で 1-sqrt(8/9) ≈ 5.72% 減少する。
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist

HERE = Path(__file__).parent
FEATURES = ["density", "lacunarity_mean", "lacunarity_slope", "r_crit",
            "mfa_alpha_width", "W_trans", "gamma", "Delta_D", "S_alpha"]
LABELS = {"density": "$d$", "lacunarity_mean": r"$\bar{\Lambda}$",
          "lacunarity_slope": r"$s_\Lambda$", "r_crit": "$r_{crit}$",
          "mfa_alpha_width": r"$\Delta\alpha$", "W_trans": "$W_{trans}$",
          "gamma": r"$\gamma$", "Delta_D": r"$\Delta D$", "S_alpha": r"$S_\alpha$"}
K = len(FEATURES)
BASELINE = (1 - np.sqrt((K - 1) / K)) * 100  # 5.72%

WINDOW = 800
STEP = 250
B_BOOT = 100
RNG = np.random.default_rng(42)

# dataviz 参照パレット（light）
C_BLUE, C_AQUA, C_YELLOW = "#2a78d6", "#1baf7a", "#eda100"
C_TEXT, C_MUTED = "#0b0b0b", "#52514e"


def contributions(X: np.ndarray) -> np.ndarray:
    """z-score済み X (n×K) の各特徴 leave-one-out 距離減少率(%)。

    ペア二乗距離は特徴ごとに分解できるので、特徴別 pdist を1回ずつ計算して合成する。
    """
    d2 = np.stack([pdist(X[:, [j]], "sqeuclidean") for j in range(X.shape[1])])
    full = np.sqrt(d2.sum(axis=0))
    mean_full = full.mean()
    out = np.empty(X.shape[1])
    total = d2.sum(axis=0)
    for j in range(X.shape[1]):
        reduced = np.sqrt(np.maximum(total - d2[j], 0.0))
        out[j] = (mean_full - reduced.mean()) / mean_full * 100
    return out


def zscore(A: np.ndarray) -> np.ndarray:
    mu = A.mean(axis=0)
    sd = A.std(axis=0)
    sd[sd == 0] = 1.0
    return (A - mu) / sd


def window_analysis(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("density").reset_index(drop=True)
    rows = []
    starts = range(0, len(df) - WINDOW + 1, STEP)
    for s in starts:
        w = df.iloc[s:s + WINDOW]
        A = w[FEATURES].to_numpy(dtype=float)
        point = contributions(zscore(A))

        # 窓内ブートストラップ（地点再抽出）
        boots = np.empty((B_BOOT, K))
        for b in range(B_BOOT):
            idx = RNG.integers(0, len(w), len(w))
            boots[b] = contributions(zscore(A[idx]))
        lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)

        # サブリージョン・ブロックブートストラップ（空間自己相関の頑健性）
        groups = w.groupby("subregion").indices
        keys = list(groups)
        blk = np.empty((B_BOOT, K))
        for b in range(B_BOOT):
            pick = RNG.choice(len(keys), len(keys), replace=True)
            idx = np.concatenate([groups[keys[i]] for i in pick])
            blk[b] = contributions(zscore(A[idx]))
        blo, bhi = np.percentile(blk, [2.5, 97.5], axis=0)

        row = {"d_median": float(w["density"].median()),
               "d_lo": float(w["density"].min()), "d_hi": float(w["density"].max()),
               "n": len(w)}
        for j, f in enumerate(FEATURES):
            row[f] = point[j]
            row[f + "_lo"], row[f + "_hi"] = lo[j], hi[j]
            row[f + "_blo"], row[f + "_bhi"] = blo[j], bhi[j]
        rows.append(row)
    return pd.DataFrame(rows)


def find_crossings(res: pd.DataFrame) -> dict:
    """d* の推定（両極端のレジーム境界）。

    - d_star_sparse: 疎側で (γ+W_trans)/2 の寄与が密度の寄与を上回る境界
    - d_star_dense:  密側で密度の寄与が一様基準を割り込む境界
    """
    x = res["d_median"].values
    dens = res["density"].values
    dyn = (res["gamma"].values + res["W_trans"].values) / 2

    def crossing(diff, i, j):
        f = (0 - diff[i]) / (diff[j] - diff[i])
        return float(x[i] + f * (x[j] - x[i]))

    d_star_sparse = None
    diff = dens - dyn
    for i in range(len(x) - 1):
        if diff[i] < 0 <= diff[i + 1]:      # 疎→密方向で密度が優位に転じる点
            d_star_sparse = crossing(diff, i, i + 1)
            break

    d_star_dense = None
    diffb = dens - BASELINE
    for i in range(len(x) - 1, 0, -1):
        if diffb[i] < 0 <= diffb[i - 1]:    # 密側で基準を割り込む点
            d_star_dense = crossing(diffb, i, i - 1)
            break

    return {"d_star_sparse": d_star_sparse,
            "d_star_dense": d_star_dense,
            "baseline_percent": BASELINE}


def style_axis(ax):
    ax.grid(True, alpha=0.25, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=C_MUTED, labelsize=9)
    for sp in ax.spines.values():
        sp.set_color(C_MUTED)


def plot_breakdown(res: pd.DataFrame, stars: dict, out: Path):
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=200)
    x = res["d_median"]

    for f, color, label in [("density", C_BLUE, "$d$ (density)"),
                            ("gamma", C_AQUA, r"$\gamma$ (critical slope)"),
                            ("W_trans", C_YELLOW, "$W_{trans}$ (transition width)")]:
        ax.plot(x, res[f], color=color, linewidth=2, label=label)
        ax.fill_between(x, res[f + "_lo"], res[f + "_hi"], color=color, alpha=0.15,
                        linewidth=0)
        ax.annotate(label, (x.iloc[-1], res[f].iloc[-1]),
                    xytext=(8, 0), textcoords="offset points",
                    color=color, fontsize=10, va="center")

    ax.axhline(BASELINE, color=C_MUTED, linestyle="--", linewidth=1)
    ax.annotate(f"uniform baseline ({BASELINE:.2f}%)", (x.iloc[0], BASELINE),
                xytext=(0, 5), textcoords="offset points", color=C_MUTED, fontsize=9)

    for key, label in [("d_star_sparse", "$d^*_{sparse}$"),
                       ("d_star_dense", "$d^*_{dense}$")]:
        if stars.get(key):
            ax.axvline(stars[key], color=C_MUTED, linewidth=1, alpha=0.6)
            ax.annotate(f"{label} = {stars[key]:.4f}",
                        (stars[key], ax.get_ylim()[1] * 0.97),
                        xytext=(6, 0), textcoords="offset points",
                        color=C_TEXT, fontsize=10)

    ax.set_xscale("log")
    ax.set_xlabel("Building density $d$ (window median, log scale)", color=C_TEXT)
    ax.set_ylabel("Leave-one-out contribution (%)", color=C_TEXT)
    ax.set_title("Unique contribution of OS features across the density axis:\n"
                 "percolation dynamics dominate at the sparse extreme; "
                 "density saturates at the dense extreme\n"
                 f"(global sample, {res['n'].iloc[0]}-point moving windows, 95% bootstrap CI)",
                 color=C_TEXT, fontsize=10.5)
    style_axis(ax)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def plot_all_features(res: pd.DataFrame, out: Path):
    fig, axes = plt.subplots(3, 3, figsize=(11, 8), dpi=200, sharex=True, sharey=True)
    x = res["d_median"]
    for ax, f in zip(axes.flat, FEATURES):
        ax.fill_between(x, res[f + "_lo"], res[f + "_hi"], color=C_BLUE, alpha=0.15,
                        linewidth=0)
        ax.plot(x, res[f], color=C_BLUE, linewidth=2)
        ax.axhline(BASELINE, color=C_MUTED, linestyle="--", linewidth=0.8)
        ax.set_xscale("log")
        ax.set_title(f"{LABELS[f]}  ({f})", fontsize=10, color=C_TEXT)
        style_axis(ax)
    fig.supxlabel("Building density $d$ (log scale)", color=C_TEXT, fontsize=10)
    fig.supylabel("Contribution (%)", color=C_TEXT, fontsize=10)
    fig.suptitle("Leave-one-out contribution of all 9 OS features vs density "
                 "(dashed: uniform baseline)", color=C_TEXT, fontsize=11)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def main():
    df = pd.read_csv(HERE / "os_vectors.csv")
    n0 = len(df)
    df = df[df["density"] > 1e-5].copy()
    print(f"locations: {n0} -> {len(df)} (density <= 1e-5 を {n0 - len(df)} 件除外)")

    cache = HERE / "window_contributions.csv"
    if cache.exists():
        res = pd.read_csv(cache)
        print(f"cached windows を再利用: {cache.name} ({len(res)} windows)")
    else:
        res = window_analysis(df)
        res.to_csv(cache, index=False)

    stars = find_crossings(res)
    (HERE / "d_star.json").write_text(json.dumps(stars, indent=2))
    print("d* 推定:", stars)

    plot_breakdown(res, stars, HERE / "breakdown_curve.png")
    plot_all_features(res, HERE / "contribution_all_features.png")

    # サマリ: 最疎窓・最密窓の寄与比較
    for tag, row in [("最疎窓", res.iloc[0]), ("最密窓", res.iloc[-1])]:
        vals = ", ".join(f"{f}={row[f]:.1f}%" for f in
                         ["density", "gamma", "W_trans", "lacunarity_mean"])
        print(f"{tag} (d~{row['d_median']:.4f}): {vals}")


if __name__ == "__main__":
    main()
