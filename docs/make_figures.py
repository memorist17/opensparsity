"""README 用の図を results.db から生成する。

    .venv/bin/python docs/make_figures.py --db results/results.db --out docs/assets

生成物（すべて docs/assets/):
  sample_{dense,sparse}.png    パイプラインが出力したオーバーレイ PNG の縮小版
  curves_{light,dark}.png      3指標の曲線（percolation / lacunarity / MFA）の対比
  corpus_{light,dark}.png      コーパス全体での density vs 相転移指標の散布図

light / dark の2枚組は GitHub の `<picture>` によるテーマ切り替え用。
軸ラベルは数式記号＋英語のみ（README.md / README.ja.md で共用するため）。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

# 対比に使う2地点（密: 都市中心 / 疎: 山間集落）
DENSE = ("Yokohama", 35.4437, 139.6380)
SPARSE = ("Shirakawa-go", 36.2578, 136.9061)

# dataviz palette: categorical slot 1 (blue) / slot 2 (orange)
THEMES = {
    "light": dict(
        surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
        grid="#e1e0d9", axis="#c3c2b7", s1="#2a78d6", s2="#eb6834",
    ),
    "dark": dict(
        surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#898781",
        grid="#2c2c2a", axis="#383835", s1="#3987e5", s2="#d95926",
    ),
}


def apply_theme(t: dict) -> None:
    plt.rcParams.update({
        "figure.facecolor": t["surface"], "axes.facecolor": t["surface"],
        "savefig.facecolor": t["surface"], "text.color": t["ink"],
        "axes.labelcolor": t["ink2"], "axes.edgecolor": t["axis"],
        "xtick.color": t["muted"], "ytick.color": t["muted"],
        "xtick.labelcolor": t["ink2"], "ytick.labelcolor": t["ink2"],
        "grid.color": t["grid"], "grid.linewidth": 0.8,
        "axes.grid": True, "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False,
        "font.size": 11, "axes.titlesize": 12, "legend.frameon": False,
        "font.family": ["DejaVu Sans"], "lines.linewidth": 2.0,
    })


def curve(conn: sqlite3.Connection, lat: float, lon: float, kind: str) -> pd.DataFrame:
    row = conn.execute(
        "SELECT data FROM curves WHERE lat=? AND lon=? AND kind=?", (lat, lon, kind)
    ).fetchone()
    if row is None:
        raise SystemExit(f"curve not found: {lat},{lon} {kind}")
    return pd.DataFrame(json.loads(row[0]))


def metrics(conn: sqlite3.Connection, lat: float, lon: float) -> pd.Series:
    df = pd.read_sql(
        "SELECT * FROM locations WHERE lat=? AND lon=?", conn, params=(lat, lon)
    )
    if df.empty:
        raise SystemExit(f"location not found: {lat},{lon}")
    return df.iloc[0]


# ---------------------------------------------------------------- samples

def make_samples(images_dir: Path, out: Path, size: int = 900) -> None:
    for tag, (_, lat, lon) in (("dense", DENSE), ("sparse", SPARSE)):
        src = images_dir / f"{lat:.4f}_{lon:.4f}.png"
        if not src.exists():
            print(f"  skip sample_{tag}: {src} not found")
            continue
        # 元画像は 2000x2000。縮小後に 64色パレット化してリポジトリ内サイズを抑える
        # （レイヤは 6 色しか使っていないので、増えるのは縮小の中間色だけ）
        im = Image.open(src).convert("RGB").resize((size, size), Image.LANCZOS)
        im = im.quantize(colors=64, method=Image.MEDIANCUT, dither=Image.NONE)
        dst = out / f"sample_{tag}.png"
        im.save(dst, optimize=True)
        print(f"  sample_{tag}.png  <- {src.name}  ({dst.stat().st_size // 1024} KB)")


# ---------------------------------------------------------------- curves

def make_curves(conn: sqlite3.Connection, out: Path, mode: str) -> None:
    t = THEMES[mode]
    apply_theme(t)
    series = []
    for (name, lat, lon), color in ((DENSE, t["s1"]), (SPARSE, t["s2"])):
        m = metrics(conn, lat, lon)
        series.append(dict(
            label=f"{name}  (d = {m['density']:.3f})", color=color, m=m,
            perc=curve(conn, lat, lon, "percolation"),
            lac=curve(conn, lat, lon, "lacunarity"),
            mfa=curve(conn, lat, lon, "mfa_spectrum"),
        ))

    fig, axes = plt.subplots(1, 3, figsize=(14.4, 4.6))
    ax1, ax2, ax3 = axes

    # (1) percolation G(r) — r_crit = argmax dG/dr（表1定義）
    for s, dy in zip(series, (14, -20)):
        p = s["perc"]
        ax1.plot(p["d"], p["giant_fraction"], color=s["color"], label=s["label"])
        rc = float(s["m"]["r_crit"])
        g = float(np.interp(rc, p["d"], p["giant_fraction"]))
        ax1.plot([rc], [g], "o", ms=8, color=s["color"],
                 mec=t["surface"], mew=2, zorder=5)
        ax1.annotate(f"$r_{{crit}}$ = {rc:.0f} m", (rc, g), color=t["ink"],
                     textcoords="offset points", xytext=(12, dy), fontsize=10)
    ax1.set_xscale("log")
    ax1.set_xlabel("connection radius $r$  [m]")
    ax1.set_ylabel("giant component fraction  $G(r)$")
    ax1.set_title("Percolation  —  $r_{crit}$, $W_{trans}$, $\\gamma$",
                  color=t["ink"], loc="left")
    ax1.set_ylim(-0.04, 1.10)

    # (2) lacunarity Λ(r) log-log。傾き = lacunarity_slope (β)
    for s in series:
        lc = s["lac"]
        ax2.plot(lc["r"], lc["lambda"], color=s["color"], label=s["label"])
    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xlabel("box size $r$  [m]")
    ax2.set_ylabel(r"lacunarity  $\Lambda(r)$")
    ax2.set_title(r"Lacunarity  —  $\bar\Lambda$, $\beta$ (slope)",
                  color=t["ink"], loc="left")

    # (3) MFA 質量指数 tau(q)。D_q = tau(q)/(q-1)、alpha = dtau/dq、
    # f(alpha) = q*alpha - tau はすべてこの曲線の導出量なので、
    # README では微分で増幅されない tau(q) そのものを見せる。
    for s in series:
        mf = s["mfa"].sort_values("q")
        ax3.plot(mf["q"], mf["tau"], color=s["color"], label=s["label"])
    ax3.set_xlabel("moment order  $q$")
    ax3.set_ylabel(r"mass exponent  $\tau(q)$")
    ax3.set_title(r"Multifractal  —  $D_0$, $\Delta\alpha$, $\Delta D$, $S_\alpha$",
                  color=t["ink"], loc="left")

    handles, labels = ax1.get_legend_handles_labels()
    fig.suptitle(
        "One `ops run` per location stores three curves in results.db",
        color=t["ink"], fontsize=12, x=0.038, ha="left", y=0.978,
    )
    fig.legend(handles, labels, loc="upper left", ncol=2, labelcolor=t["ink"],
               bbox_to_anchor=(0.032, 0.945), fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.895))
    path = out / f"curves_{mode}.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    print(f"  {path.name}")


# ---------------------------------------------------------------- corpus

def make_corpus(conn: sqlite3.Connection, out: Path, mode: str) -> None:
    t = THEMES[mode]
    apply_theme(t)
    df = pd.read_sql(
        "SELECT name, lat, lon, density, r_crit, W_trans, gamma FROM locations "
        "WHERE status='done' AND density > 0 AND r_crit IS NOT NULL", conn
    )
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.4))
    panels = [
        (axes[0], "r_crit", "critical radius  $r_{crit}$  [m]", True),
        (axes[1], "W_trans", "transition width  $W_{trans}$  [m]", False),
    ]
    for ax, col, ylabel, logy in panels:
        sub = df.dropna(subset=[col])
        ax.scatter(sub["density"], sub[col], s=6, c=t["muted"], alpha=0.30,
                   linewidths=0, zorder=2)
        for ((name, lat, lon), color, off) in (
            (DENSE, t["s1"], (10, 12)), (SPARSE, t["s2"], (-10, 14))
        ):
            row = sub[(sub["lat"] == lat) & (sub["lon"] == lon)]
            if row.empty:
                continue
            ax.plot(row["density"], row[col], "o", ms=10, color=color,
                    mec=t["surface"], mew=2, zorder=5)
            ax.annotate(name, (row["density"].iloc[0], row[col].iloc[0]),
                        color=t["ink"], textcoords="offset points", xytext=off,
                        ha="left" if off[0] > 0 else "right", fontsize=10,
                        zorder=6)
        ax.set_xscale("log")
        if logy:
            ax.set_yscale("log")
        ax.set_xlabel("building density  $d$")
        ax.set_ylabel(ylabel)
    fig.suptitle(
        f"{len(df):,} locations in results.db  —  at a fixed density, "
        "percolation behaviour still spans an order of magnitude",
        color=t["ink"], fontsize=12, x=0.045, ha="left", y=0.972,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.925))
    path = out / f"corpus_{mode}.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    print(f"  {path.name}  (n={len(df)})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="results/results.db")
    ap.add_argument("--images", default=None, help="default: <db の親>/images")
    ap.add_argument("--out", default="docs/assets")
    args = ap.parse_args()

    db = Path(args.db)
    images_dir = Path(args.images) if args.images else db.parent / "images"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        make_samples(images_dir, out)
        for mode in ("light", "dark"):
            make_curves(conn, out, mode)
            make_corpus(conn, out, mode)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
