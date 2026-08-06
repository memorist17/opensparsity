"""README 用の図を results.db から生成する。

    .venv/bin/python docs/make_figures.py --db results/results.db --out docs/assets

生成物（すべて docs/assets/):
  sample_{dense,sparse}.png    パイプラインが出力したオーバーレイ PNG の縮小版
  curves_{light,dark}.png      3指標の曲線（percolation / lacunarity / MFA）の対比
  corpus_{light,dark}.png      コーパス全体での density vs 相転移指標の散布図
  outliers_{light,dark}.png    指標空間のはずれ値5地点 + オーバーレイの色凡例

light / dark の2枚組は GitHub の `<picture>` によるテーマ切り替え用。
図中のラベルは数式記号＋英語のみ（README.md / README.ja.md で共用するため）。
指標値は図に焼き込まず README 側の表に置く（言語ごとにローカライズするため）。

はずれ値5地点は select_outliers() で導出したものを OUTLIERS に固定してある
（README の表と図をずれさせないため）。ランキングを引き直すには:

    .venv/bin/python docs/make_figures.py --reselect
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

# 指標空間のはずれ値5地点。select_outliers() の出力から、はずれ理由が重複しない
# ものを選んで固定した。地名は Nominatim の逆ジオコーディング。
# (lat, lon, 地名, 支配的な特徴, 一言)
OUTLIERS = [
    (35.2468, -106.7578, "Sandoval County, New Mexico, US",
     "$S_\\alpha$ = −3.6 sd", "platted road grid, almost no houses"),
    (51.3828, 30.1297, "Nahirtsi, Kyiv Oblast, UA",
     "$\\Delta\\alpha$ = +3.5 sd", "industrial plant inside the exclusion zone"),
    (43.2698, 141.9659, "Ikushunbetsu, Mikasa, Hokkaido, JP",
     "$\\gamma$ = +3.2 sd", "shrunken ex-coal town, one tight core"),
    (49.9048, -119.5471, "West Kelowna Estates, BC, CA",
     "$r_{crit}$ = +2.6 sd", "houses strung along contour roads"),
    (52.6052, 19.0713, "Pińczata, gmina Włocławek, PL",
     "$\\bar\\Lambda$ = +2.0 sd", "single linear village in open fields"),
]

# render.py のレイヤ色（凡例セル用。render.COL_* と一致させること）
LAYERS = [
    ((105, 105, 105), "building raster"),
    ((208, 208, 208), "road raster"),
    ((0, 90, 230), "road edge"),
    ((120, 190, 255), "virtual edge (building → road)"),
    ((230, 30, 30), "building node"),
]

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


# ---------------------------------------------------------------- outliers

# 表1の9次元。裾が重いものは log を取ってから z-score にする
OS_FEATS = {
    "density": "log", "lacunarity_mean": "log", "lacunarity_slope": None,
    "r_crit": "log", "mfa_alpha_width": None, "W_trans": None,
    "gamma": None, "Delta_D": None, "S_alpha": None,
}
COL_VIRT = (120, 190, 255)
COL_ROAD_EDGE = (0, 90, 230)
FAN_THRESH = 0.35


def virtual_edge_ratio(images_dir: Path, lat: float, lon: float) -> float:
    """仮想エッジ画素 / 道路エッジ画素。スター（扇状）の検出に使う。

    render.py は ImageDraw で塗るのでアンチエイリアスが無く、レイヤ色が厳密に
    一致する。建物が最近傍の道路1点へ束で snap すると扇状になり、この比が跳ねる。
    """
    a = np.asarray(Image.open(images_dir / f"{lat:.4f}_{lon:.4f}.png").convert("RGB"))
    virt = int(np.all(a == COL_VIRT, axis=-1).sum())
    road = int(np.all(a == COL_ROAD_EDGE, axis=-1).sum())
    return virt / max(road, 1)


def select_outliers(conn, images_dir: Path, n: int = 8, probe: int = 120) -> pd.DataFrame:
    """指標空間のはずれ値をランキングする（OUTLIERS の導出に使った手続き）。

    1. 極端な密度・道路データ欠損・観測窓内で完了しない転移を除外
    2. 9次元 z-score 空間のマハラノビス距離で降順に並べる
    3. 上位 probe 件の画像を見てスター（仮想エッジ比 >= FAN_THRESH）を落とす
    4. 相互 400km 以上離れるものを貪欲に選ぶ（隣接タイルの重複回避）
    """
    df = pd.read_sql("SELECT * FROM locations WHERE status='done'", conn)
    pool = df[
        df["density"].between(0.003, 0.05)      # 極端な低密度・高密度を除外
        & (df["road_length_density"] > 1.0)      # 道路が実際にある [km/km2]
        & (df["n_buildings"] >= 120)             # 指標が意味を持つ建物数
        & (df["W_trans"] < 1999)                 # 転移が 2km の観測窓内で完了
    ].dropna(subset=list(OS_FEATS)).copy()

    X = []
    for f, tr in OS_FEATS.items():
        v = pool[f].to_numpy(float)
        if tr == "log":
            v = np.log10(np.clip(v, 1e-12, None))
        X.append((v - v.mean()) / v.std())
    X = np.column_stack(X)
    inv = np.linalg.pinv(np.cov(X, rowvar=False))
    pool["maha"] = np.sqrt(np.einsum("ij,jk,ik->i", X, inv, X))
    pool["drivers"] = [
        ", ".join(f"{k}={v:+.1f}sd" for k, v in
                  sorted(zip(OS_FEATS, row), key=lambda kv: -abs(kv[1]))[:3])
        for row in X
    ]
    print(f"  eligible pool: {len(pool)} / {len(df)}")

    ranked = pool.sort_values("maha", ascending=False).head(probe).copy()
    ranked["fan"] = [virtual_edge_ratio(images_dir, r.lat, r.lon)
                     for r in ranked.itertuples()]
    keep = ranked[ranked["fan"] < FAN_THRESH]
    print(f"  fan-rejected: {len(ranked) - len(keep)} / {len(ranked)} "
          f"(median ratio {ranked['fan'].median():.2f})")

    picked = []
    for r in keep.itertuples():
        far = all(
            6371 * 2 * np.arcsin(np.sqrt(
                np.sin(np.radians(p.lat - r.lat) / 2) ** 2
                + np.cos(np.radians(r.lat)) * np.cos(np.radians(p.lat))
                * np.sin(np.radians(p.lon - r.lon) / 2) ** 2)) > 400
            for p in picked
        )
        if far:
            picked.append(r)
        if len(picked) == n:
            break
    return pd.DataFrame(picked)


def make_outliers(conn, images_dir: Path, out: Path, mode: str) -> None:
    t = THEMES[mode]
    apply_theme(t)
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 9.9))
    flat = axes.ravel()

    for ax, (lat, lon, place, driver, note) in zip(flat, OUTLIERS):
        src = images_dir / f"{lat:.4f}_{lon:.4f}.png"
        if not src.exists():
            ax.axis("off")
            continue
        im = Image.open(src).convert("RGB").resize((680, 680), Image.LANCZOS)
        ax.imshow(im)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(True)
            s.set_edgecolor(t["axis"])
        ax.set_title(f"{place}\n{driver}", fontsize=11, color=t["ink"],
                     loc="left", linespacing=1.6, pad=7)
        ax.set_xlabel(note, fontsize=9.5, color=t["ink2"], loc="left", labelpad=7)

    # 6枚目はオーバーレイの色凡例
    ax = flat[5]
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.02, 0.93, "overlay layers", fontsize=11, color=t["ink"])
    for i, (rgb, label) in enumerate(LAYERS):
        y = 0.80 - i * 0.105
        ax.add_patch(plt.Rectangle((0.03, y - 0.022), 0.075, 0.045,
                                   facecolor="#%02x%02x%02x" % rgb,
                                   edgecolor=t["axis"], linewidth=0.8))
        ax.text(0.13, y, label, fontsize=9.5, color=t["ink2"], va="center")
    ax.text(0.02, 0.20,
            "north is up · 2 km × 2 km · 1 m/px\nmetrics for each panel are in the "
            "table below",
            fontsize=9.5, color=t["muted"], va="top", linespacing=1.7)

    fig.suptitle(
        "Metric-space outliers  —  mid-density band (0.003 ≤ d ≤ 0.05), real road "
        "data, virtual-edge fans rejected",
        fontsize=12.5, color=t["ink"], x=0.028, ha="left", y=0.985)
    fig.subplots_adjust(left=0.015, right=0.985, top=0.905, bottom=0.03,
                        wspace=0.07, hspace=0.26)
    path = out / f"outliers_{mode}.png"
    fig.savefig(path, dpi=118)
    plt.close(fig)
    print(f"  {path.name}  ({path.stat().st_size // 1024} KB)")


def print_outlier_table(conn) -> None:
    """README の表に貼る値を出す。"""
    print("\n| place | driver | d | r_crit | W_trans | gamma | Lbar | beta | da | Sa | n |")
    for lat, lon, place, driver, _ in OUTLIERS:
        m = pd.read_sql(
            "SELECT * FROM locations WHERE abs(lat-?)<1e-3 AND abs(lon-?)<1e-3",
            conn, params=(lat, lon)).iloc[0]
        print(f"| {place} | {driver} | {m.density:.4f} | {m.r_crit:.0f} | "
              f"{m.W_trans:.0f} | {m.gamma:.4f} | {m.lacunarity_mean:.1f} | "
              f"{m.lacunarity_slope:.2f} | {m.mfa_alpha_width:.2f} | "
              f"{m.S_alpha:+.2f} | {m.n_buildings} |")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="results/results.db")
    ap.add_argument("--images", default=None, help="default: <db の親>/images")
    ap.add_argument("--out", default="docs/assets")
    ap.add_argument("--reselect", action="store_true",
                    help="はずれ値のランキングを引き直して表示する（図は作らない）")
    args = ap.parse_args()

    db = Path(args.db)
    images_dir = Path(args.images) if args.images else db.parent / "images"
    out = Path(args.out)

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        if args.reselect:
            picked = select_outliers(conn, images_dir)
            print("\n=== ranking (OUTLIERS はここから選んで固定してある) ===")
            for i, r in enumerate(picked.itertuples(), 1):
                print(f"{i}. maha={r.maha:.2f} fan={r.fan:.3f}  "
                      f"{r.lat:.4f},{r.lon:.4f}  d={r.density:.4f}  {r.drivers}")
            return

        out.mkdir(parents=True, exist_ok=True)
        make_samples(images_dir, out)
        for mode in ("light", "dark"):
            make_curves(conn, out, mode)
            make_corpus(conn, out, mode)
            make_outliers(conn, images_dir, out, mode)
        print_outlier_table(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
