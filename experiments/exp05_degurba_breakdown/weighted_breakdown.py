#!/usr/bin/env python
"""DEGURBA実現サンプル(16,474点)での密度崩壊分析: exp01の移動窓×LOFO感度分析を
design_weight付きで再現し、(1) exp01の結果が独立サンプルで再現するか、
(2) DEGURBAクラス層別でも成り立つか、(3) 重み付き/なしで結論が変わるか、を検証する。

exp01との違い:
  - データ: global_v2(WSF5分位×22サブリージョン)ではなく、DEGURBA class11/12の
    層化サンプル（母集団=全球の疎居住セル、国際標準定義）
  - 分離度: 重み付き平均ペアワイズ距離（ペア(i,j)の重み = w_i * w_j）。
    z-scoreも重み付き平均・標準偏差で行う
  - 感度分析の定義自体はexp01/卒論§5.4と同一（leave-one-feature-out距離減少率%）

一様基準: 9特徴が無相関なら1特徴除去で 1-sqrt(8/9) ≈ 5.72% 減少。
"""
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

# dataviz 参照パレット（light）— exp01と同じ役割割当
C_BLUE, C_AQUA, C_YELLOW = "#2a78d6", "#1baf7a", "#eda100"
C_TEXT, C_MUTED = "#0b0b0b", "#52514e"


def weighted_zscore(A: np.ndarray, w: np.ndarray) -> np.ndarray:
    wsum = w.sum()
    mu = (A * w[:, None]).sum(axis=0) / wsum
    var = ((A - mu) ** 2 * w[:, None]).sum(axis=0) / wsum
    sd = np.sqrt(var)
    sd[sd == 0] = 1.0
    return (A - mu) / sd


def weighted_contributions(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    """重み付き平均ペアワイズ距離のLOFO減少率(%)。ペア重み = w_i * w_j。"""
    d2 = np.stack([pdist(X[:, [j]], "sqeuclidean") for j in range(X.shape[1])])
    n = len(w)
    iu = np.triu_indices(n, k=1)
    pw = (w[:, None] * w[None, :])[iu]
    pw_sum = pw.sum()
    total = d2.sum(axis=0)
    full = np.sqrt(total)
    mean_full = (full * pw).sum() / pw_sum
    out = np.empty(X.shape[1])
    for j in range(X.shape[1]):
        reduced = np.sqrt(np.maximum(total - d2[j], 0.0))
        out[j] = (mean_full - (reduced * pw).sum() / pw_sum) / mean_full * 100
    return out


def window_analysis(df: pd.DataFrame, weighted: bool, label: str) -> pd.DataFrame:
    df = df.sort_values("density").reset_index(drop=True)
    rows = []
    n = len(df)
    if n < WINDOW:
        return pd.DataFrame()
    for s in range(0, n - WINDOW + 1, STEP):
        wdf = df.iloc[s:s + WINDOW]
        A = wdf[FEATURES].to_numpy(dtype=float)
        w = (wdf["design_weight"].to_numpy(dtype=float) if weighted
             else np.ones(len(wdf)))
        point = weighted_contributions(weighted_zscore(A, w), w)

        boots = np.empty((B_BOOT, K))
        for b in range(B_BOOT):
            idx = RNG.integers(0, len(wdf), len(wdf))
            boots[b] = weighted_contributions(
                weighted_zscore(A[idx], w[idx]), w[idx])
        lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)

        row = {"subset": label, "weighted": weighted,
               "d_median": float(wdf["density"].median()),
               "n": len(wdf)}
        for j, f in enumerate(FEATURES):
            row[f] = point[j]
            row[f"{f}_lo"] = lo[j]
            row[f"{f}_hi"] = hi[j]
        rows.append(row)
        print(f"  [{label} w={weighted}] window {s}: d_med={row['d_median']:.5f} "
              f"d%={point[0]:.2f} gamma%={point[FEATURES.index('gamma')]:.2f}")
    return pd.DataFrame(rows)


def overall_contributions(df: pd.DataFrame, weighted: bool) -> np.ndarray:
    A = df[FEATURES].to_numpy(dtype=float)
    w = (df["design_weight"].to_numpy(dtype=float) if weighted
         else np.ones(len(df)))
    # 全16k点のpdistはメモリ的に重い(1.4億ペア×float64×10)。無作為4,000点で近似
    if len(df) > 4000:
        idx = RNG.choice(len(df), 4000, replace=False)
        A, w = A[idx], w[idx]
    return weighted_contributions(weighted_zscore(A, w), w)


def main():
    df = pd.read_csv(HERE / "realized_sample.csv")
    df = df.dropna(subset=FEATURES).reset_index(drop=True)
    print(f"分析対象: {len(df):,} 点")

    # --- 全体サマリ（重み付き/なし、クラス別） ---
    summary = []
    for label, sub in [("all", df),
                       ("low_density_rural", df[df["degurba_class"] == "low_density_rural"]),
                       ("very_low_density_rural", df[df["degurba_class"] == "very_low_density_rural"])]:
        for weighted in [True, False]:
            c = overall_contributions(sub, weighted)
            summary.append({"subset": label, "weighted": weighted, "n": len(sub),
                            **{f: c[j] for j, f in enumerate(FEATURES)}})
            print(f"[overall {label} w={weighted}] " +
                  " ".join(f"{f}={c[j]:.2f}" for j, f in enumerate(FEATURES)))
    pd.DataFrame(summary).to_csv(HERE / "overall_contributions.csv", index=False)

    # --- 移動窓（全体・重み付き＋重みなし、クラス別・重み付き） ---
    parts = []
    parts.append(window_analysis(df, True, "all"))
    parts.append(window_analysis(df, False, "all"))
    parts.append(window_analysis(
        df[df["degurba_class"] == "low_density_rural"], True, "low"))
    parts.append(window_analysis(
        df[df["degurba_class"] == "very_low_density_rural"], True, "very_low"))
    win = pd.concat([p for p in parts if len(p)], ignore_index=True)
    win.to_csv(HERE / "window_contributions.csv", index=False)

    # --- 図1: 密度寄与 vs ダイナミクス寄与（全体・重み付き） ---
    w_all = win[(win["subset"] == "all") & win["weighted"]]
    dyn = (w_all["gamma"] + w_all["W_trans"]) / 2
    dyn_lo = (w_all["gamma_lo"] + w_all["W_trans_lo"]) / 2
    dyn_hi = (w_all["gamma_hi"] + w_all["W_trans_hi"]) / 2

    fig, ax = plt.subplots(figsize=(8, 5))
    x = w_all["d_median"]
    ax.fill_between(x, w_all["density_lo"], w_all["density_hi"],
                    color=C_BLUE, alpha=0.15, lw=0)
    ax.plot(x, w_all["density"], color=C_BLUE, lw=2, label="density $d$")
    ax.fill_between(x, dyn_lo, dyn_hi, color=C_AQUA, alpha=0.15, lw=0)
    ax.plot(x, dyn, color=C_AQUA, lw=2,
            label=r"dynamics mean($\gamma$, $W_{trans}$)")
    ax.axhline(BASELINE, color=C_MUTED, ls="--", lw=1,
               label=f"uniform baseline {BASELINE:.2f}%")
    ax.set_xscale("log")
    ax.set_xlabel("window median density $d$ (log)", color=C_TEXT)
    ax.set_ylabel("LOFO distance reduction (%)", color=C_TEXT)
    ax.set_title("Density vs transition-dynamics contribution\n"
                 "(DEGURBA rural sample, N=16,474, design-weighted)",
                 color=C_TEXT, fontsize=11)
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=0.25, lw=0.5)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(HERE / "breakdown_curve.png", dpi=150)
    plt.close(fig)

    # --- 図2: 9特徴すべて（全体・重み付き） ---
    fig, axes = plt.subplots(3, 3, figsize=(11, 8), sharex=True, sharey=True)
    for j, f in enumerate(FEATURES):
        ax = axes[j // 3][j % 3]
        ax.fill_between(x, w_all[f"{f}_lo"], w_all[f"{f}_hi"],
                        color=C_BLUE, alpha=0.15, lw=0)
        ax.plot(x, w_all[f], color=C_BLUE, lw=1.8)
        ax.axhline(BASELINE, color=C_MUTED, ls="--", lw=0.8)
        ax.set_xscale("log")
        ax.set_title(LABELS[f], color=C_TEXT, fontsize=11)
        ax.grid(alpha=0.25, lw=0.5)
        for s in ["top", "right"]:
            ax.spines[s].set_visible(False)
    fig.supxlabel("window median density $d$ (log)", color=C_TEXT, fontsize=10)
    fig.supylabel("LOFO distance reduction (%)", color=C_TEXT, fontsize=10)
    fig.suptitle("All-feature contribution curves (design-weighted)",
                 color=C_TEXT, fontsize=12)
    fig.tight_layout()
    fig.savefig(HERE / "contribution_all_features.png", dpi=150)
    plt.close(fig)

    # --- 図3: 重み付き vs 重みなし（密度・γのみ、頑健性） ---
    u_all = win[(win["subset"] == "all") & (~win["weighted"])]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(w_all["d_median"], w_all["density"], color=C_BLUE, lw=2,
            label="$d$ (weighted)")
    ax.plot(u_all["d_median"], u_all["density"], color=C_BLUE, lw=1.5, ls=":",
            label="$d$ (unweighted)")
    ax.plot(w_all["d_median"], w_all["gamma"], color=C_YELLOW, lw=2,
            label=r"$\gamma$ (weighted)")
    ax.plot(u_all["d_median"], u_all["gamma"], color=C_YELLOW, lw=1.5, ls=":",
            label=r"$\gamma$ (unweighted)")
    ax.axhline(BASELINE, color=C_MUTED, ls="--", lw=1)
    ax.set_xscale("log")
    ax.set_xlabel("window median density $d$ (log)", color=C_TEXT)
    ax.set_ylabel("LOFO distance reduction (%)", color=C_TEXT)
    ax.set_title("Design weighting robustness check", color=C_TEXT, fontsize=11)
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=0.25, lw=0.5)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(HERE / "weighting_robustness.png", dpi=150)
    plt.close(fig)

    print("\n完了: window_contributions.csv / overall_contributions.csv / 図3枚")


if __name__ == "__main__":
    main()
