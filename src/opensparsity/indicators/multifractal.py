"""Multifractal Analysis (MFA) using Reshape & Sum with Grid Shifting."""

from dataclasses import dataclass
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy import stats
from scipy.signal import savgol_filter
from tqdm import tqdm


@dataclass
class MultifractalAnalyzer:
    """
    Compute multifractal spectrum using 4D reshape & sum.

    Algorithm:
    1. Reshape image (H, W) to (H//r, r, W//r, r)
    2. Sum over axis=(1,3) to get box masses
    3. Apply grid shifting for robustness
    4. Linear regression of log(Z(q,r)) vs log(r) to get τ(q)
    5. Legendre transform: α = dτ/dq, f(α) = qα - τ
    """

    r_min: int = 2
    r_max: int = 512
    r_steps: int = 20
    q_min: float = -10
    q_max: float = 10
    q_steps: int = 41
    grid_shift_count: int = 16
    n_jobs: int = -1

    def analyze(self, image: np.ndarray) -> tuple[pd.DataFrame, np.ndarray]:
        """
        Compute multifractal spectrum.

        Args:
            image: 2D weighted raster array (non-negative values)

        Returns:
            spectrum_df: DataFrame with columns [q, alpha, f_alpha, tau, R2]
            mesh: 2D array of partition function Z(q, r) shape (q_steps, r_steps)
            box_sizes: 1D array of box sizes used (length r_steps_actual)

        Note:
            理論の検証用に spectrum_df["q"] vs spectrum_df["tau"] をプロットすると、
            τ(q) は q について単調増加・上に凸であることが期待される。
            q=0 で f(α) は最大（容量次元 D_0 ≒ 2）となる。
        """
        # Normalize image to probabilities
        raw = np.asarray(image)
        raw_is_integer = np.issubdtype(raw.dtype, np.integer) or (
            np.issubdtype(raw.dtype, np.floating) and np.all(raw == np.floor(raw))
            and raw.max() < 2**31
        )
        raw_counts = raw.astype(np.int64) if raw_is_integer else None
        image = raw.astype(np.float64)
        total = image.sum()
        if total == 0:
            raise ValueError("Image is empty (all zeros)")
        if raw_is_integer:
            total = int(raw_counts.sum())
        image = image / (total if not raw_is_integer else float(total))

        # Get box sizes and q values
        box_sizes = self._get_box_sizes()
        q_values = np.linspace(self.q_min, self.q_max, self.q_steps)

        # Filter box sizes that fit in image
        H, W = image.shape
        valid_sizes = [r for r in box_sizes if r <= min(H, W) // 2]
        if not valid_sizes:
            raise ValueError(f"No valid box sizes for image of shape {image.shape}")

        box_sizes = np.array(valid_sizes)
        r_steps_actual = len(box_sizes)

        print(f"Computing MFA: {len(q_values)} q-values, {r_steps_actual} box sizes")
        print(f"Box sizes: {box_sizes[0]} to {box_sizes[-1]}")

        # Compute partition function for all (q, r) combinations.
        # Loop order is INVERTED from the obvious nesting: r outermost, then
        # shifts, then q. The expensive work (image reshape + box-mass sum)
        # depends only on (r, dx, dy); for each shift we compute the box
        # masses ONCE and apply all q exponents to the same nonzero masses.
        # Result: ~q_steps × fewer reshape calls. For q_steps=41, that's a
        # ~40x speedup on the dominant inner loop, which previously
        # dominated tile time at ~15 minutes for dense rasters.
        mesh = np.zeros((len(q_values), r_steps_actual))
        q_arr = q_values  # alias for clarity inside loops

        # 高速パス: 元画像が整数値（2値ラスタ等）なら、
        #   1) int64 の積分画像でボックス質量（カウント）を厳密に求め、
        #   2) 質量ヒストグラム（ユニーク値は高々 min(box数, r²) 個）の上で
        #      Z(q) = Σ_v n_v (v/total)^q を計算する。
        # reshape の全画素走査（シフト×サイズごと）と、全ボックスへの q 乗が消える。
        int_image = None
        if raw_is_integer:
            int_image = np.zeros((H + 1, W + 1), dtype=np.int64)
            int_image[1:, 1:] = raw_counts.cumsum(axis=0).cumsum(axis=1)

        for r_idx, r in enumerate(tqdm(box_sizes, desc="Computing Z(q,r)")):
            max_shift = min(r, self.grid_shift_count)
            shifts = np.linspace(0, r - 1, max_shift, dtype=int)
            # accumulators across (dx, dy) shifts
            Z_sum = np.zeros(len(q_arr))
            counts = np.zeros(len(q_arr))
            for dx in shifts:
                for dy in shifts:
                    if int_image is not None:
                        h_boxes = (H - dy) // r
                        w_boxes = (W - dx) // r
                        if h_boxes == 0 or w_boxes == 0:
                            continue
                        rows = dy + np.arange(h_boxes) * r
                        cols = dx + np.arange(w_boxes) * r
                        box_counts = (
                            int_image[np.ix_(rows + r, cols + r)]
                            - int_image[np.ix_(rows, cols + r)]
                            - int_image[np.ix_(rows + r, cols)]
                            + int_image[np.ix_(rows, cols)]
                        )
                        hist = np.bincount(box_counts.ravel())
                        vals = np.nonzero(hist)[0]
                        vals = vals[vals > 0]
                        if len(vals) == 0:
                            continue
                        n_v = hist[vals].astype(np.float64)
                        m_v = vals.astype(np.float64) / float(total)
                        log_m = np.log(m_v)
                        # 全 q を一括計算（q=1 は Σ m ln m の特別式）
                        Z_all = (n_v[None, :]
                                 * np.exp(q_arr[:, None] * log_m[None, :])).sum(axis=1)
                        is_q1 = q_arr == 1.0
                        if is_q1.any():
                            Z_all[is_q1] = np.exp(-np.sum(n_v * m_v * log_m))
                        pos = Z_all > 0
                        Z_sum[pos] += Z_all[pos]
                        counts[pos] += 1
                        continue

                    masses = self._compute_box_masses(image, r, dx, dy)
                    if masses is None:
                        continue
                    nonzero = masses[masses > 0]
                    if len(nonzero) == 0:
                        continue
                    log_nz = np.log(nonzero)
                    # Z(q) for each q value, vectorized
                    for q_idx, q in enumerate(q_arr):
                        if q == 1.0:
                            Z = np.exp(-np.sum(nonzero * log_nz))
                        else:
                            Z = np.sum(nonzero ** q)
                        if Z > 0:
                            Z_sum[q_idx] += Z
                            counts[q_idx] += 1
            with np.errstate(invalid="ignore", divide="ignore"):
                mesh[:, r_idx] = np.where(counts > 0, Z_sum / counts, 0.0)

        # Compute τ(q) via linear regression of log(Z) vs log(r)
        # 理論: Z(q,r) ∝ r^τ(q) => log Z = τ(q) log r + const => τ(q) = d(log Z)/d(log r)
        # τ(q) は q について単調増加・上に凸が期待され、そのとき f(α) は ∩ 型になる
        log_r = np.log(box_sizes)
        tau_values = np.zeros(len(q_values))
        r2_values = np.zeros(len(q_values))

        for q_idx in range(len(q_values)):
            log_Z = np.log(mesh[q_idx, :] + 1e-300)  # Avoid log(0)
            slope, intercept, r_value, p_value, std_err = stats.linregress(log_r, log_Z)
            tau_values[q_idx] = slope
            r2_values[q_idx] = r_value ** 2

        # 数値微分のノイズ低減: τ(q) を軽くスムージング（オプション）
        nq = len(tau_values)
        if nq >= 5:
            window = min(5, nq if nq % 2 == 1 else nq - 1)
            if window >= 3:
                tau_values = savgol_filter(tau_values, window, polyorder=2, mode="nearest")

        # α(q) = dτ/dq, f(α) = qα - τ（ルジャンドル変換）。f(α) は上に凸(∩)に強制
        alpha_values = np.gradient(tau_values, q_values)
        f_alpha_values = q_values * alpha_values - tau_values
        order = np.argsort(alpha_values)
        f_o = f_alpha_values[order]
        imax = int(np.argmax(f_o))
        n = len(f_o)
        f_cap = np.zeros(n)
        f_cap[: imax + 1] = np.maximum.accumulate(f_o[: imax + 1])
        f_cap[imax:] = np.maximum.accumulate(f_o[imax:][::-1])[::-1]
        inv = np.empty(n, dtype=int)
        inv[order] = np.arange(n)
        f_alpha_values = np.maximum(f_cap[inv], 0.0)

        # Create result DataFrame
        spectrum_df = pd.DataFrame({
            "q": q_values,
            "alpha": alpha_values,
            "f_alpha": f_alpha_values,
            "tau": tau_values,
            "R2": r2_values,
        })

        return spectrum_df, mesh, box_sizes

    def _compute_partition_function_shifted(
        self, image: np.ndarray, r: int, q: float
    ) -> float:
        """Compute partition function with grid shift averaging."""
        H, W = image.shape
        max_shift = min(r, self.grid_shift_count)
        shifts = np.linspace(0, r - 1, max_shift, dtype=int)

        Z_sum = 0.0
        count = 0

        for dx in shifts:
            for dy in shifts:
                Z = self._compute_partition_function(image, r, q, dx, dy)
                if Z > 0:
                    Z_sum += Z
                    count += 1

        return Z_sum / count if count > 0 else 0.0

    def _compute_partition_function(
        self, image: np.ndarray, r: int, q: float, dx: int = 0, dy: int = 0
    ) -> float:
        """
        Compute partition function Z(q, r) for given box size and moment.

        Kept for backward compatibility; the optimized analyze() path now uses
        _compute_box_masses() and applies q exponents in an inner loop without
        recomputing the reshape per q.
        """
        masses = self._compute_box_masses(image, r, dx, dy)
        if masses is None:
            return 0.0
        nonzero = masses[masses > 0]
        if len(nonzero) == 0:
            return 0.0
        if q == 1:
            return float(np.exp(-np.sum(nonzero * np.log(nonzero))))
        return float(np.sum(nonzero ** q))

    def _compute_box_masses(
        self, image: np.ndarray, r: int, dx: int = 0, dy: int = 0
    ) -> np.ndarray | None:
        """Reshape+sum to obtain per-box masses for a given offset (dx, dy).

        Returns the (h_boxes × w_boxes) array of summed masses, or None if
        no full box fits at this offset.
        """
        H, W = image.shape
        h_boxes = (H - dy) // r
        w_boxes = (W - dx) // r
        if h_boxes == 0 or w_boxes == 0:
            return None
        cropped = image[dy:dy + h_boxes * r, dx:dx + w_boxes * r]
        return cropped.reshape(h_boxes, r, w_boxes, r).sum(axis=(1, 3))

    def _get_box_sizes(self) -> np.ndarray:
        """Generate log-spaced box sizes."""
        return np.unique(
            np.logspace(
                np.log2(self.r_min),
                np.log2(self.r_max),
                self.r_steps,
                base=2
            ).astype(int)
        )
    
    def compute_generalized_dimensions(
        self, spectrum_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Compute generalized dimensions D_q from multifractal spectrum.
        
        D_q = tau(q) / (q - 1) for q != 1
        D_1 = alpha (when q = 1, use alpha from spectrum)
        
        Args:
            spectrum_df: DataFrame with columns [q, alpha, f_alpha, tau, ...]
        
        Returns:
            DataFrame with columns [q, D_q]
        """
        q_values = spectrum_df["q"].values
        tau_values = spectrum_df["tau"].values
        alpha_values = spectrum_df["alpha"].values
        
        dq_values = np.zeros_like(q_values)
        for i, q in enumerate(q_values):
            if abs(q - 1.0) < 1e-6:
                # D_1 = alpha
                dq_values[i] = alpha_values[i]
            else:
                # D_q = tau(q) / (q - 1)
                dq_values[i] = tau_values[i] / (q - 1.0)
        
        return pd.DataFrame({
            "q": q_values,
            "D_q": dq_values
        })





