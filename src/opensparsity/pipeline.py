"""1地点の処理パイプライン: fetch → 投影 → ラスタ化 → ネットワーク → 指標 → 画像。

成果物は「オーバーレイ PNG 1枚」と「ResultStore への1行 + 曲線3種」だけで、
中間ファイル（npy / graphml / 地点別 CSV）は一切書かない。
"""

import time
from pathlib import Path

import geopandas as gpd
import numpy as np

from . import CODE_VERSION
from .config import (
    create_lacunarity_analyzer,
    create_mfa_analyzer,
    create_percolation_analyzer,
)
from .fetch import OVERTURE_RELEASE, OvertureFetcher
from .network import NetworkBuilder
from .project import AEQDTransformer
from .raster import Rasterizer
from .render import image_filename, render_overlay
from .indicators.advanced import compute_all_advanced_metrics
from .store import ResultStore


def process_location(
    lat: float,
    lon: float,
    config: dict,
    store: ResultStore,
    images_dir: str | Path,
    name: str | None = None,
) -> dict:
    """1地点を処理して結果を store に保存し、指標 dict を返す。失敗時は例外を送出。"""
    t0 = time.time()
    half = float(config["canvas"]["half_size_m"])
    canvas_px = int(2 * half / float(config["canvas"]["resolution_m"]))
    net_cfg = config.get("network", {})

    # 1. fetch（建物・道路を並列取得）
    bbox = OvertureFetcher(lat=lat, lon=lon, half_size_m=half)._get_bbox_wgs84()
    with OvertureFetcher(bbox_wgs84=bbox) as fetcher:
        buildings_gdf, roads_gdf = fetcher.fetch_all(verbose=False)

    # 2. 投影（AEQD, 中心原点メートル座標）
    transformer = AEQDTransformer(center_lat=lat, center_lon=lon, half_size_m=half)
    buildings = (
        transformer.transform_and_clip(buildings_gdf)
        if not buildings_gdf.empty
        else gpd.GeoDataFrame(columns=["geometry", "height"], geometry=[])
    )
    roads = (
        transformer.transform_and_clip(roads_gdf)
        if not roads_gdf.empty
        else gpd.GeoDataFrame(columns=["geometry", "width"], geometry=[])
    )

    # 3. ラスタ化
    rasterizer = Rasterizer(canvas_size=canvas_px, half_size_m=half)
    b_raster = rasterizer.rasterize_buildings(buildings, verbose=False)
    r_raster = rasterizer.rasterize_roads(roads, verbose=False)
    combined = ((b_raster > 0) | (r_raster > 0)).astype(np.uint8)
    if not combined.any():
        raise ValueError("empty area: no buildings and no roads in bbox")

    # 4. ネットワーク構築
    builder = NetworkBuilder(
        snap_tolerance=net_cfg.get("snap_tolerance", 4.0),
        connection_threshold=net_cfg.get("connection_threshold", 10.0),
        use_road_width=net_cfg.get("use_road_width", True),
    )
    graph = builder.build_network(roads, buildings, verbose=False)

    # 5. 指標計算
    lac = create_lacunarity_analyzer(config)
    lac_df, _ = lac.analyze(b_raster)

    mfa = create_mfa_analyzer(config)
    mfa_df, _, _ = mfa.analyze(combined)
    dq_df = mfa.compute_generalized_dimensions(mfa_df)

    perc = create_percolation_analyzer(config)
    perc_df, _ = perc.analyze(graph)
    d_crit = perc.find_percolation_threshold(perc_df, 0.5)

    metrics = {
        "density": float(np.mean(b_raster)),
        "lacunarity_mean": float(lac_df["lambda"].mean()),
        "lacunarity_slope": float(lac.fit_power_law(lac_df)["beta"]),
        "mfa_alpha_width": float(mfa_df["alpha"].max() - mfa_df["alpha"].min()),
        "mfa_D0": float(dq_df.loc[dq_df["q"] == 0, "D_q"].values[0]),
        "perc_dcrit": d_crit,
        "perc_gmax": float(perc_df["giant_fraction"].max()),
    }
    metrics.update(
        compute_all_advanced_metrics(perc_df, mfa_df, lac_df, r_crit=d_crit)
    )

    # 6. オーバーレイ画像（唯一のファイル成果物）
    img_path = Path(images_dir) / image_filename(lat, lon)
    render_overlay(
        b_raster, r_raster, graph, img_path,
        half_size_m=half,
        metadata={
            "lat": lat, "lon": lon,
            "overture_release": OVERTURE_RELEASE,
            "code_version": CODE_VERSION,
            **{k: f"{v:.6g}" for k, v in metrics.items() if v is not None},
        },
    )

    # 7. 保存（db が真実源。画像を書いた後にコミット）
    n_building_nodes = sum(
        1 for _, a in graph.nodes(data=True) if a.get("type") == "building"
    )
    store.upsert_result(
        lat, lon, name=name, metrics=metrics,
        curves={
            "percolation": perc_df[["d", "giant_fraction", "n_clusters"]],
            "mfa_spectrum": mfa_df,
            "lacunarity": lac_df,
        },
        elapsed_sec=time.time() - t0,
        code_version=CODE_VERSION,
        overture_release=OVERTURE_RELEASE,
        n_buildings=len(buildings),
        n_building_nodes=n_building_nodes,
    )
    return metrics


def run_batch(
    locations: list[dict],
    config: dict,
    out_dir: str | Path,
    *,
    force: bool = False,
    log=print,
) -> dict[str, int]:
    """複数地点を順に処理する。処理済み地点はスキップ（再開可能）。

    Args:
        locations: [{"lat": float, "lon": float, "name": str?}, ...]
        out_dir: 出力ディレクトリ（results.db と images/ を作る）
        force: True なら処理済みでも再計算
    """
    out_dir = Path(out_dir)
    store = ResultStore(out_dir / "results.db")
    images_dir = out_dir / "images"

    done = set() if force else store.done_keys()
    n_skip = n_ok = n_fail = 0
    try:
        for i, loc in enumerate(locations, 1):
            lat, lon = float(loc["lat"]), float(loc["lon"])
            name = loc.get("name")
            if (lat, lon) in done:
                n_skip += 1
                continue
            label = name or f"{lat:.4f},{lon:.4f}"
            try:
                t0 = time.time()
                m = process_location(lat, lon, config, store, images_dir, name=name)
                n_ok += 1
                log(f"[{i}/{len(locations)}] OK {label}: {time.time()-t0:.0f}s "
                    f"density={m['density']:.4f} r_crit={m['perc_dcrit']}")
            except Exception as e:  # noqa: BLE001 — バッチは1地点の失敗で止めない
                store.mark_failed(lat, lon, name, f"{type(e).__name__}: {e}",
                                  CODE_VERSION, OVERTURE_RELEASE)
                n_fail += 1
                log(f"[{i}/{len(locations)}] FAIL {label}: {type(e).__name__}: {e}")
    finally:
        store.close()
    return {"ok": n_ok, "skipped": n_skip, "failed": n_fail}
