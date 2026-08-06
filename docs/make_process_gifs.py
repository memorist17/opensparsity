#!/usr/bin/env python3
"""README 用の「計算過程」GIF を3本作る。

    .venv/bin/python docs/make_process_gifs.py

- percolation_{light,dark}.gif : 接続半径 r を伸ばしたとき建物ノードと道路が
  どう繋がっていくか。実装と同じ「距離行列の最小全域森を r でフィルタする」方式。
- lacunarity_{light,dark}.gif  : gliding box のサイズ r を変えたときの Λ(r) = 1 + σ²/μ²。
- multifractal_{light,dark}.gif: 次数 q を振ったとき、どの箱に重みが乗るか（μ^q）。

対象地点はチェルニーヒウ州（独立した4つの村。窓内で1つに繋がりきらないので、
percolation の途中経過が一番よく見える）。フェッチ結果は .cache_gif.npz に置いて
再実行を速くする。
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
from matplotlib.collections import LineCollection
from PIL import Image

from make_figures import THEMES, apply_theme  # noqa: E402  同じ配色を共有する

# チェルニーヒウ州, UA — README 冒頭の6地点のひとつ
LAT, LON = 50.68964379968809, 31.14663778761328
PLACE = "Chernihiv Oblast, UA"
HALF_M = 1000.0


# ---------------------------------------------------------------- inputs

def build_inputs(cache: Path) -> dict:
    """fetch → 投影 → ラスタ → ネットワーク → 距離行列の MST。結果を npz に残す。"""
    if cache.exists():
        z = np.load(cache)
        print(f"  reusing {cache.name}")
        return {k: z[k] for k in z.files}

    import geopandas as gpd
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra, minimum_spanning_tree

    from opensparsity.fetch import OvertureFetcher
    from opensparsity.network import NetworkBuilder
    from opensparsity.project import AEQDTransformer
    from opensparsity.raster import Rasterizer

    print("  fetching Overture (about 100 s)…")
    bbox = OvertureFetcher(lat=LAT, lon=LON, half_size_m=HALF_M)._get_bbox_wgs84()
    with OvertureFetcher(bbox_wgs84=bbox) as f:
        b_gdf, r_gdf = f.fetch_all(verbose=False)

    tr = AEQDTransformer(center_lat=LAT, center_lon=LON, half_size_m=HALF_M)
    buildings = tr.transform_and_clip(b_gdf)
    roads = tr.transform_and_clip(r_gdf)

    rast = Rasterizer(canvas_size=int(2 * HALF_M), half_size_m=HALF_M)
    b_raster = rast.rasterize_buildings(buildings, verbose=False)
    r_raster = rast.rasterize_roads(roads, verbose=False)
    combined = ((b_raster > 0) | (r_raster > 0)).astype(np.uint8)

    print("  building the network…")
    graph = NetworkBuilder(snap_tolerance=4.0, connection_threshold=10.0,
                           use_road_width=True).build_network(roads, buildings,
                                                              verbose=False)
    nodes = list(graph.nodes())
    idx = {n: i for i, n in enumerate(nodes)}
    bnodes = [n for n, d in graph.nodes(data=True) if d.get("type") == "building"]
    print(f"  {len(bnodes)} building nodes / {len(nodes)} total")

    rows, cols, vals = [], [], []
    for u, v, a in graph.edges(data=True):
        rows.append(idx[u]); cols.append(idx[v])
        vals.append(max(float(a.get("length", 1.0)), 1e-12))
    adj = coo_matrix((vals + vals, (rows + cols, cols + rows)),
                     shape=(len(nodes), len(nodes))).tocsr()

    print("  pairwise shortest paths…")
    src = np.array([idx[n] for n in bnodes])
    dm = dijkstra(adj, directed=False, indices=src)[:, src]
    np.fill_diagonal(dm, 0.0)

    # 実装と同じ: 単連結クラスタリング = 距離グラフの最小全域森を r でフィルタ
    finite = np.where(np.isfinite(dm), dm, 0.0)
    mst = minimum_spanning_tree(np.triu(finite, 1)).tocoo()
    ok = mst.data > 0
    mst_i, mst_j, mst_w = mst.row[ok], mst.col[ok], mst.data[ok]

    pos = np.array([[graph.nodes[n]["x"], graph.nodes[n]["y"]] for n in bnodes])
    road_seg = []
    for u, v, a in graph.edges(data=True):
        if a.get("type") == "virtual":
            continue
        road_seg.append([[graph.nodes[u]["x"], graph.nodes[u]["y"]],
                         [graph.nodes[v]["x"], graph.nodes[v]["y"]]])

    out = dict(b_raster=b_raster, combined=combined, pos=pos,
               mst_i=mst_i, mst_j=mst_j, mst_w=mst_w,
               road_seg=np.array(road_seg, dtype=float))
    np.savez_compressed(cache, **out)
    print(f"  cached -> {cache.name}")
    return out


def save_gif(frames: list[Image.Image], path: Path, ms: int) -> None:
    frames = [f.convert("RGB").quantize(colors=64, method=Image.MEDIANCUT,
                                        dither=Image.NONE) for f in frames]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=ms,
                   loop=0, optimize=True, disposal=2)
    print(f"  {path.name}  ({path.stat().st_size // 1024} KB, {len(frames)} frames)")


def render(fig) -> Image.Image:
    fig.canvas.draw()
    return Image.frombytes("RGBA", fig.canvas.get_width_height(),
                           fig.canvas.buffer_rgba().tobytes())


# ---------------------------------------------------------------- percolation

def gif_percolation(d: dict, out: Path, mode: str, n_frames: int = 30) -> None:
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    t = THEMES[mode]
    apply_theme(t)
    pos, wi, wj, ww = d["pos"], d["mst_i"], d["mst_j"], d["mst_w"]
    n = len(pos)
    radii = np.unique(np.round(np.geomspace(8, 2000, n_frames)).astype(int))

    Gs = []
    for r in radii:
        m = ww <= r
        g = coo_matrix((np.ones(m.sum()), (wi[m], wj[m])), shape=(n, n))
        ncomp, lab = connected_components(g, directed=False)
        Gs.append(np.bincount(lab).max() / n if n else 0.0)

    frames = []
    for k, r in enumerate(radii):
        fig, (ax, axc) = plt.subplots(
            1, 2, figsize=(9.4, 5.0), gridspec_kw=dict(width_ratios=[1.28, 1]))
        ax.add_collection(LineCollection(d["road_seg"], colors=t["grid"],
                                         linewidths=0.8, zorder=1))
        m = ww <= r
        if m.any():
            seg = np.stack([pos[wi[m]], pos[wj[m]]], axis=1)
            ax.add_collection(LineCollection(seg, colors=t["cats"][5],
                                             linewidths=1.3, alpha=0.85, zorder=3))
        g = coo_matrix((np.ones(m.sum()), (wi[m], wj[m])), shape=(n, n))
        _, lab = connected_components(g, directed=False)
        giant = lab == np.bincount(lab).argmax()
        ax.scatter(pos[~giant, 0], pos[~giant, 1], s=3.5, c=t["muted"],
                   linewidths=0, zorder=4)
        ax.scatter(pos[giant, 0], pos[giant, 1], s=5.0, c=t["cats"][5],
                   linewidths=0, zorder=5)
        ax.set_xlim(-HALF_M, HALF_M); ax.set_ylim(-HALF_M, HALF_M)
        ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(True); s.set_edgecolor(t["axis"])
        ax.set_title(f"connection radius  $r$ = {r:,} m", color=t["ink"], loc="left")

        axc.plot(radii, Gs, color=t["axis"], lw=1.6, zorder=2)
        axc.plot(radii[:k + 1], Gs[:k + 1], color=t["cats"][5], lw=2.6, zorder=3)
        axc.plot([r], [Gs[k]], "o", ms=8, color=t["cats"][5],
                 mec=t["surface"], mew=2, zorder=4)
        axc.set_xscale("log"); axc.set_ylim(-0.04, 1.06)
        axc.set_xlabel("$r$  [m]")
        axc.set_ylabel("giant component fraction  $G(r)$")
        axc.set_title(f"$G(r)$ = {Gs[k]:.2f}", color=t["ink"], loc="left")

        fig.suptitle(
            "Percolation  —  two buildings are linked when the shortest path "
            "along the road network between them is ≤ r",
            color=t["ink"], fontsize=11.5, x=0.012, ha="left", y=0.985)
        fig.tight_layout(rect=(0, 0, 1, 0.92))
        frames.append(render(fig))
        plt.close(fig)

    frames += [frames[-1]] * 6
    save_gif(frames, out / f"percolation_{mode}.gif", 190)


# ---------------------------------------------------------------- lacunarity

def gif_lacunarity(d: dict, out: Path, mode: str) -> None:
    t = THEMES[mode]
    apply_theme(t)
    img = d["b_raster"].astype(np.float64)
    ii = np.pad(img, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    sizes = np.unique(np.round(np.geomspace(4, 1000, 22)).astype(int))
    disp = np.array(Image.fromarray((d["b_raster"] > 0).astype(np.uint8) * 255)
                    .resize((520, 520), Image.BILINEAR))

    lam = []
    for r in sizes:
        s = (ii[r:, r:] - ii[:-r, r:] - ii[r:, :-r] + ii[:-r, :-r])[::max(r // 4, 1),
                                                                   ::max(r // 4, 1)]
        mu = s.mean()
        lam.append(1.0 + (s.var() / mu ** 2) if mu > 0 else 1.0)

    frames = []
    for k, r in enumerate(sizes):
        fig, (ax, axc) = plt.subplots(
            1, 2, figsize=(9.4, 5.0), gridspec_kw=dict(width_ratios=[1.28, 1]))
        ax.imshow(255 - disp, cmap="gray", vmin=0, vmax=255, zorder=1)
        step = r * 520 / 2000
        if step >= 3.5:                       # 細かすぎる格子は描かない
            g = np.arange(0, 521, step)
            ax.vlines(g, 0, 520, colors=t["cats"][0], lw=0.6, alpha=0.75, zorder=2)
            ax.hlines(g, 0, 520, colors=t["cats"][0], lw=0.6, alpha=0.75, zorder=2)
        else:
            ax.text(0.5, 0.5, "boxes smaller than a pixel here",
                    transform=ax.transAxes, ha="center", color=t["cats"][0],
                    fontsize=10)
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(True); s.set_edgecolor(t["axis"])
        ax.set_title(f"gliding box  $r$ = {r:,} m", color=t["ink"], loc="left")

        axc.plot(sizes, lam, color=t["axis"], lw=1.6, zorder=2)
        axc.plot(sizes[:k + 1], lam[:k + 1], color=t["cats"][0], lw=2.6, zorder=3)
        axc.plot([r], [lam[k]], "o", ms=8, color=t["cats"][0],
                 mec=t["surface"], mew=2, zorder=4)
        axc.set_xscale("log"); axc.set_yscale("log")
        axc.set_xlabel("box size  $r$  [m]")
        axc.set_ylabel(r"lacunarity  $\Lambda(r)$")
        axc.set_title(rf"$\Lambda$ = {lam[k]:.2f}", color=t["ink"], loc="left")

        fig.suptitle(
            r"Lacunarity  —  slide a box of size $r$ over the building raster: "
            r"$\Lambda(r) = 1 + \sigma^2/\mu^2$  of the box masses",
            color=t["ink"], fontsize=11.5, x=0.012, ha="left", y=0.985)
        fig.tight_layout(rect=(0, 0, 1, 0.92))
        frames.append(render(fig))
        plt.close(fig)

    frames += [frames[-1]] * 5
    save_gif(frames, out / f"lacunarity_{mode}.gif", 230)


# ---------------------------------------------------------------- multifractal

def gif_multifractal(d: dict, db: Path, out: Path, mode: str) -> None:
    t = THEMES[mode]
    apply_theme(t)
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    row = conn.execute("SELECT data FROM curves WHERE abs(lat-?)<1e-6 AND "
                       "abs(lon-?)<1e-6 AND kind='mfa_spectrum'", (LAT, LON)).fetchone()
    conn.close()
    if row is None:
        print("  skip multifractal: mfa_spectrum curve not in db")
        return
    spec = json.loads(row[0])
    qs_all = np.asarray(spec["q"], float)
    tau_all = np.asarray(spec["tau"], float)
    order = np.argsort(qs_all)
    qs_all, tau_all = qs_all[order], tau_all[order]

    # 箱の質量 μ_i（建物 ∪ 道路、箱サイズ 50 m）
    box = 50
    img = d["combined"].astype(np.float64)
    nb = img.shape[0] // box
    mass = img[:nb * box, :nb * box].reshape(nb, box, nb, box).sum(axis=(1, 3))
    occ = mass > 0
    p = np.zeros_like(mass)
    p[occ] = mass[occ] / mass[occ].sum()

    qs = np.round(np.linspace(-10, 10, 25), 2)
    frames = []
    for q in qs:
        with np.errstate(divide="ignore", invalid="ignore"):
            w = np.where(occ, p ** q, 0.0)
        w = w / w.sum() if w.sum() > 0 else w
        shown = np.where(occ, w, np.nan)

        fig, (ax, axc) = plt.subplots(
            1, 2, figsize=(9.4, 5.0), gridspec_kw=dict(width_ratios=[1.28, 1]))
        ax.imshow(np.where(occ, 0.12, np.nan), cmap="Greys", vmin=0, vmax=1,
                  interpolation="nearest", zorder=1)
        ax.imshow(shown, cmap="inferno" if mode == "dark" else "YlOrRd",
                  interpolation="nearest", zorder=2,
                  norm=matplotlib.colors.PowerNorm(0.45))
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(True); s.set_edgecolor(t["axis"])
        emph = "emptiest boxes" if q < -0.5 else (
            "densest boxes" if q > 0.5 else "all boxes equal")
        ax.set_title(f"$q$ = {q:+.1f}   —   {emph}", color=t["ink"], loc="left")

        axc.plot(qs_all, tau_all, color=t["axis"], lw=1.6, zorder=2)
        m = qs_all <= q
        axc.plot(qs_all[m], tau_all[m], color=t["cats"][3], lw=2.6, zorder=3)
        tq = float(np.interp(q, qs_all, tau_all))
        axc.plot([q], [tq], "o", ms=8, color=t["cats"][3],
                 mec=t["surface"], mew=2, zorder=4)
        axc.set_xlabel("moment order  $q$")
        axc.set_ylabel(r"mass exponent  $\tau(q)$")
        axc.set_title(rf"$\tau(q)$ = {tq:+.2f}", color=t["ink"], loc="left")

        fig.suptitle(
            r"Multifractal  —  weight each box by $\mu_i^{\,q}$ and watch which part "
            r"of the settlement the exponent is listening to",
            color=t["ink"], fontsize=11.5, x=0.012, ha="left", y=0.985)
        fig.tight_layout(rect=(0, 0, 1, 0.92))
        frames.append(render(fig))
        plt.close(fig)

    frames += [frames[-1]] * 5
    save_gif(frames, out / f"multifractal_{mode}.gif", 170)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="results/results.db")
    ap.add_argument("--out", default="docs/assets")
    ap.add_argument("--only", choices=["percolation", "lacunarity", "multifractal"])
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    d = build_inputs(out / ".cache_gif.npz")

    for mode in ("light", "dark"):
        if args.only in (None, "percolation"):
            gif_percolation(d, out, mode)
        if args.only in (None, "lacunarity"):
            gif_lacunarity(d, out, mode)
        if args.only in (None, "multifractal"):
            gif_multifractal(d, Path(args.db), out, mode)


if __name__ == "__main__":
    main()
