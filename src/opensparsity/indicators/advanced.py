"""Advanced OS Metrics: W_trans, ΔD, β, γ, S_α

全指標リストに基づく追加指標の計算モジュール。
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.interpolate import interp1d
from typing import Optional


def compute_percolation_transition_width(
    percolation_df: pd.DataFrame,
    g_target_low: float = 0.1,
    g_target_high: float = 0.9
) -> float:
    """
    パーコレーション転移幅 (Percolation Transition Width: W_trans) を計算。
    
    W_trans = r(G=0.9) - r(G=0.1)
    
    ネットワーク形成の「粘り」を測る。狭いほど一気に繋がる（核型）、
    広いほどダラダラと繋がる（分散型）。
    
    Args:
        percolation_df: パーコレーション結果のDataFrame
            columns: [d, giant_fraction, ...]
        g_target_low: 低い巨大クラスター割合の閾値（デフォルト: 0.1）
        g_target_high: 高い巨大クラスター割合の閾値（デフォルト: 0.9）
    
    Returns:
        W_trans: 転移幅（距離単位）
    """
    d = percolation_df["d"].values
    gf = percolation_df["giant_fraction"].values
    
    # 閾値を超える点を探す
    r_low = _find_threshold_distance(d, gf, g_target_low)
    r_high = _find_threshold_distance(d, gf, g_target_high)
    
    if r_low is None or r_high is None:
        return np.nan
    
    return float(r_high - r_low)


def find_r_crit_max_slope(percolation_df: pd.DataFrame) -> Optional[float]:
    """
    G(d) の傾き dG/dr が最大となる距離を返す（理論的に自然な臨界点の定義）。
    """
    d = percolation_df["d"].values
    gf = percolation_df["giant_fraction"].values
    if len(d) < 2:
        return float(d[0]) if len(d) == 1 else None
    slopes = (gf[1:] - gf[:-1]) / (d[1:] - d[:-1] + 1e-20)
    d_mid = (d[1:] + d[:-1]) * 0.5
    idx = np.argmax(slopes)
    return float(d_mid[idx])


def _find_threshold_distance(
    distances: np.ndarray,
    values: np.ndarray,
    target: float
) -> Optional[float]:
    """閾値を超える距離を線形補間で求める。"""
    if len(distances) == 0 or len(values) == 0:
        return None
    
    # 閾値を超える最初の点を探す
    above = np.where(values >= target)[0]
    if len(above) == 0:
        # 閾値に達していない場合は最大距離を返す
        return float(distances[-1])
    
    idx = above[0]
    if idx == 0:
        return float(distances[0])
    
    # 線形補間
    t = (target - values[idx - 1]) / (values[idx] - values[idx - 1])
    return float(distances[idx - 1] + t * (distances[idx] - distances[idx - 1]))


def compute_fractal_dimension_gap(
    mfa_spectrum_df: pd.DataFrame
) -> float:
    """
    フラクタル次元ギャップ (Generalized Dimensions Gap: ΔD) を計算。
    
    ΔD = D_0 - D_2
    
    密度の「集中強度」を測る。大: 点としての集中が激しい（Lourmarin）、
    中: 適度なクラスター感（Ibiza）、小: 均質・ランダム。
    
    Args:
        mfa_spectrum_df: MFAスペクトルのDataFrame
            columns: [q, alpha, f_alpha, tau, ...]
    
    Returns:
        ΔD: フラクタル次元ギャップ
    """
    q_values = mfa_spectrum_df["q"].values
    tau_values = mfa_spectrum_df["tau"].values
    
    # D_q = tau(q) / (q - 1) for q != 1
    # q=0とq=2のインデックスを探す
    idx_0 = np.argmin(np.abs(q_values - 0.0))
    idx_2 = np.argmin(np.abs(q_values - 2.0))
    
    q_0 = q_values[idx_0]
    q_2 = q_values[idx_2]
    tau_0 = tau_values[idx_0]
    tau_2 = tau_values[idx_2]
    
    # D_0 = tau(0) / (0 - 1) = -tau(0)
    # D_2 = tau(2) / (2 - 1) = tau(2)
    if abs(q_0) < 1e-6:
        D_0 = -tau_0
    else:
        D_0 = tau_0 / (q_0 - 1.0)
    
    if abs(q_2 - 2.0) < 1e-6:
        D_2 = tau_2 / (q_2 - 1.0)
    else:
        D_2 = tau_2 / (q_2 - 1.0)
    
    return float(D_0 - D_2)


def compute_lacunarity_decay_rate(
    lacunarity_df: pd.DataFrame
) -> float:
    """
    ラクナリティ減衰率 (Lacunarity Decay Rate: β) を計算。
    
    Λ(r) ~ r^(-β) の両対数グラフにおける傾き。
    β = -d ln(Λ) / d ln(r)
    
    空間の「自己相似性（フラクタル性）」を測る。
    急: ズームアウトするとすぐ均質になる（ただのランダムな過疎）。
    緩: どのスケールで見ても「ムラ」がある（デザインされたOpen Sparsity）。
    
    Args:
        lacunarity_df: ラクナリティ結果のDataFrame
            columns: [r, lambda, ...]
    
    Returns:
        β: ラクナリティ減衰率（正の値）
    """
    r = lacunarity_df["r"].values
    lambda_vals = lacunarity_df["lambda"].values
    
    # ゼロや負の値を除外
    valid = (r > 0) & (lambda_vals > 0)
    if np.sum(valid) < 2:
        return np.nan
    
    log_r = np.log(r[valid])
    log_lambda = np.log(lambda_vals[valid])
    
    # 線形回帰で傾きを求める
    slope, intercept, r_value, p_value, std_err = stats.linregress(log_r, log_lambda)
    
    # β = -slope (Λがrに対して減少するため)
    return float(-slope)


def compute_percolation_critical_slope(
    percolation_df: pd.DataFrame,
    r_crit: Optional[float] = None
) -> float:
    """
    パーコレーション臨界勾配 (Critical Slope: γ) を計算。
    
    γ = dG(r)/dr |_{r=r_crit}
    
    ネットワーク接続の「爆発力」を測る。
    高: ある距離で「相転移」が起きる（グリッド都市、核型集落）。
    低: 転移がマイルド（有機的な分散配置）。
    
    Args:
        percolation_df: パーコレーション結果のDataFrame
            columns: [d, giant_fraction, ...]
        r_crit: 臨界距離（Noneの場合は0.5の閾値を使用）。
            傾き最大の点を使う場合は find_r_crit_max_slope(percolation_df) を渡す。
    
    Returns:
        γ: 臨界勾配
    """
    d = percolation_df["d"].values
    gf = percolation_df["giant_fraction"].values
    
    if r_crit is None:
        # 0.5の閾値で臨界距離を求める
        r_crit = _find_threshold_distance(d, gf, 0.5)
        if r_crit is None:
            return np.nan
    
    # r_critに最も近い点を探す
    idx = np.argmin(np.abs(d - r_crit))
    
    # 前後の点を使って勾配を計算
    if idx == 0:
        # 最初の点: 前進差分
        if len(d) > 1:
            gamma = (gf[1] - gf[0]) / (d[1] - d[0])
        else:
            return np.nan
    elif idx == len(d) - 1:
        # 最後の点: 後退差分
        gamma = (gf[idx] - gf[idx - 1]) / (d[idx] - d[idx - 1])
    else:
        # 中央差分
        gamma = (gf[idx + 1] - gf[idx - 1]) / (d[idx + 1] - d[idx - 1])
    
    return float(gamma)


def compute_mfa_spectrum_skewness(
    mfa_spectrum_df: pd.DataFrame
) -> float:
    """
    MFAスペクトル歪度 (MFA Spectrum Skewness: S_α) を計算。
    
    f(α)の左右非対称性を測る。
    左裾が広い (q>0 dominant): 高密度部分が複雑さの源泉（Siena, Lourmarin）。
    右裾が広い (q<0 dominant): 低密度部分が複雑さの源泉（Ibiza）。
    Open Sparsityは右裾が広いことが理想。
    
    Args:
        mfa_spectrum_df: MFAスペクトルのDataFrame
            columns: [q, alpha, f_alpha, ...]
    
    Returns:
        S_α: スペクトル歪度（正: 右裾、負: 左裾）
    """
    alpha = mfa_spectrum_df["alpha"].values
    f_alpha = mfa_spectrum_df["f_alpha"].values
    
    # f(α) > 0 の範囲のみを使用
    valid = f_alpha > 0
    if np.sum(valid) < 3:
        return np.nan
    
    alpha_valid = alpha[valid]
    f_alpha_valid = f_alpha[valid]
    
    # 重み付き平均と標準偏差を計算
    # f(α)を重みとして使用
    mean_alpha = np.average(alpha_valid, weights=f_alpha_valid)
    
    # 重み付き分散
    variance = np.average((alpha_valid - mean_alpha) ** 2, weights=f_alpha_valid)
    std_alpha = np.sqrt(variance)
    
    if std_alpha == 0:
        return 0.0
    
    # 3次モーメント（歪度）
    skewness = np.average(
        ((alpha_valid - mean_alpha) / std_alpha) ** 3,
        weights=f_alpha_valid
    )
    
    return float(skewness)


def compute_all_advanced_metrics(
    percolation_df: pd.DataFrame,
    mfa_spectrum_df: pd.DataFrame,
    lacunarity_df: pd.DataFrame,
    r_crit: Optional[float] = None
) -> dict[str, float]:
    """
    全追加指標を一度に計算。
    
    Args:
        percolation_df: パーコレーション結果
        mfa_spectrum_df: MFAスペクトル結果
        lacunarity_df: ラクナリティ結果
        r_crit: 臨界距離（Noneの場合は自動計算）
    
    Returns:
        指標名をキー、値を値とする辞書
    """
    metrics = {}
    
    # W_trans: パーコレーション転移幅
    metrics["W_trans"] = compute_percolation_transition_width(percolation_df)
    
    # ΔD: フラクタル次元ギャップ
    metrics["Delta_D"] = compute_fractal_dimension_gap(mfa_spectrum_df)
    
    # β: ラクナリティ減衰率
    metrics["beta"] = compute_lacunarity_decay_rate(lacunarity_df)
    
    # γ: パーコレーション臨界勾配
    metrics["gamma"] = compute_percolation_critical_slope(percolation_df, r_crit)
    
    # S_α: MFAスペクトル歪度
    metrics["S_alpha"] = compute_mfa_spectrum_skewness(mfa_spectrum_df)
    
    return metrics
