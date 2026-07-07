"""一括プリフェッチ: 全地点分の Overture データを少数回の S3 スキャンでローカルに落とす。

地点ごとに全球 parquet をスキャンし直す従来方式（1地点 ≈ 100秒）の代わりに、
全地点の bbox をまとめて突き合わせて一括抽出する。

2つの抽出モード（出力は同一形式）:
- static: 全 bbox の OR 述語を直接 WHERE に置く。parquet の row-group pruning が
  効くため高速だが、述語が巨大になるので地点数 ~200 まで（検証・小規模用）
- join:   地点 bbox を 1° グリッドセルへ展開したテーブルと equi-join する。
  述語プッシュダウンは効かず対象ファイルの全走査になるが、地点数に依らず
  1パスで済む（大規模用）。リモートファイルをチャンクに分けて処理し、
  manifest.json で完了チャンクを記録するため中断・再開可能

finalize_cache() でチャンク群を loc_key ソート済み parquet に書き直すと、
地点単位の読み出しが row-group pruning で高速になる。
"""

import json
import math
import time
from pathlib import Path

import duckdb
import pandas as pd

from .fetch import OVERTURE_S3_BASE

THEMES = {
    "buildings": {
        "s3_glob": f"{OVERTURE_S3_BASE}/theme=buildings/type=building/*",
        "select": ("id, names.primary AS name, height, num_floors, "
                   "ST_AsWKB(geometry) AS geometry"),
        # 元 fetcher と同じ「bbox 完全内包」条件
        "condition": ("t.bbox.xmin >= b.min_lon AND t.bbox.xmax <= b.max_lon AND "
                      "t.bbox.ymin >= b.min_lat AND t.bbox.ymax <= b.max_lat"),
        "extra_where": "",
    },
    "roads": {
        "s3_glob": f"{OVERTURE_S3_BASE}/theme=transportation/type=segment/*",
        "select": ("id, names.primary AS name, class, subclass, "
                   "ST_AsWKB(geometry) AS geometry"),
        # 元 fetcher と同じ「bbox 交差」条件
        "condition": ("t.bbox.xmin <= b.max_lon AND t.bbox.xmax >= b.min_lon AND "
                      "t.bbox.ymin <= b.max_lat AND t.bbox.ymax >= b.min_lat"),
        "extra_where": "AND t.subtype = 'road'",
    },
}

STATIC_MODE_MAX_BOXES = 200


def _connect() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect()
    conn.execute("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs;")
    conn.execute("SET s3_region='us-west-2';")
    conn.execute("SET s3_access_key_id=''; SET s3_secret_access_key='';")
    return conn


def loc_key(lat: float, lon: float) -> str:
    """キャッシュと画像で共通の地点キー（{lat:.4f}_{lon:.4f}）。"""
    return f"{lat:.4f}_{lon:.4f}"


def build_boxes(locations: list[dict], half_size_m: float) -> pd.DataFrame:
    """地点リスト → bbox テーブル（fetch.OvertureFetcher と同一の近似式）。"""
    rows = []
    for loc in locations:
        lat, lon = float(loc["lat"]), float(loc["lon"])
        lat_rad = math.radians(lat)
        m_per_deg_lat = (111132.92 - 559.82 * math.cos(2 * lat_rad)
                         + 1.175 * math.cos(4 * lat_rad))
        m_per_deg_lon = 111412.84 * math.cos(lat_rad) - 93.5 * math.cos(3 * lat_rad)
        dlat = half_size_m / m_per_deg_lat
        dlon = half_size_m / m_per_deg_lon
        rows.append({
            "loc_key": loc_key(lat, lon),
            "min_lon": lon - dlon, "min_lat": lat - dlat,
            "max_lon": lon + dlon, "max_lat": lat + dlat,
        })
    return pd.DataFrame(rows)


def _expand_box_cells(boxes: pd.DataFrame) -> pd.DataFrame:
    """各 bbox を 1° セル（±1 のハロー付き）に展開する。

    ハローは「エンティティ側のセルキーを bbox 中心で取る」ことに対する保険で、
    中心が最大 1° 離れたエンティティ（≈110km 級のセグメント）まで取りこぼさない。
    """
    rows = []
    for r in boxes.itertuples(index=False):
        for cx in range(math.floor(r.min_lon) - 1, math.floor(r.max_lon) + 2):
            for cy in range(math.floor(r.min_lat) - 1, math.floor(r.max_lat) + 2):
                rows.append((r.loc_key, cx, cy,
                             r.min_lon, r.min_lat, r.max_lon, r.max_lat))
    return pd.DataFrame(rows, columns=["loc_key", "cell_x", "cell_y",
                                       "min_lon", "min_lat", "max_lon", "max_lat"])


def list_remote_files(theme: str) -> list[str]:
    conn = _connect()
    files = [r[0] for r in conn.execute(
        f"SELECT file FROM glob('{THEMES[theme]['s3_glob']}') ORDER BY file"
    ).fetchall()]
    conn.close()
    return files


def _query_static(conn, theme: str, files: list[str], boxes: pd.DataFrame):
    spec = THEMES[theme]
    preds = " OR ".join(
        f"({spec['condition'].replace('b.', '')})"
        .replace("min_lon", repr(r.min_lon)).replace("max_lon", repr(r.max_lon))
        .replace("min_lat", repr(r.min_lat)).replace("max_lat", repr(r.max_lat))
        for r in boxes.itertuples(index=False)
    )
    file_list = ", ".join(f"'{f}'" for f in files)
    # マッチ行に loc_key を割り当てるため boxes と residual join
    conn.register("boxes", boxes)
    return conn.execute(f"""
        SELECT b.loc_key, {spec['select']}
        FROM read_parquet([{file_list}]) t
        JOIN boxes b ON {spec['condition']}
        WHERE ({preds}) {spec['extra_where']}
    """).fetchdf()


def _query_join(conn, theme: str, files: list[str], box_cells: pd.DataFrame):
    spec = THEMES[theme]
    file_list = ", ".join(f"'{f}'" for f in files)
    conn.register("box_cells", box_cells)
    return conn.execute(f"""
        SELECT b.loc_key, {spec['select']}
        FROM read_parquet([{file_list}]) t
        JOIN box_cells b
          ON CAST(floor((t.bbox.xmin + t.bbox.xmax) / 2) AS INTEGER) = b.cell_x
         AND CAST(floor((t.bbox.ymin + t.bbox.ymax) / 2) AS INTEGER) = b.cell_y
         AND {spec['condition']}
        WHERE 1=1 {spec['extra_where']}
    """).fetchdf()


def prefetch_theme(
    theme: str,
    boxes: pd.DataFrame,
    cache_dir: str | Path,
    *,
    mode: str = "auto",
    chunk_files: int = 16,
    files: list[str] | None = None,
    log=print,
) -> None:
    """1テーマ分を一括抽出して cache_dir/<theme>/chunk_*.parquet に書く（再開可能）。"""
    out_dir = Path(cache_dir) / theme
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
        "done_chunks": [], "mode": None, "n_boxes": len(boxes)}

    if files is None:
        files = list_remote_files(theme)
    if mode == "auto":
        mode = "static" if len(boxes) <= STATIC_MODE_MAX_BOXES else "join"
    manifest["mode"] = mode
    box_cells = _expand_box_cells(boxes) if mode == "join" else None

    chunks = [files[i:i + chunk_files] for i in range(0, len(files), chunk_files)]
    log(f"[{theme}] mode={mode} files={len(files)} chunks={len(chunks)} "
        f"boxes={len(boxes)} (done: {len(manifest['done_chunks'])})")

    conn = _connect()
    for ci, chunk in enumerate(chunks):
        if ci in manifest["done_chunks"]:
            continue
        t0 = time.time()
        if mode == "static":
            df = _query_static(conn, theme, chunk, boxes)
        else:
            df = _query_join(conn, theme, chunk, box_cells)
        df.to_parquet(out_dir / f"chunk_{ci:04d}.parquet", index=False)
        manifest["done_chunks"].append(ci)
        manifest_path.write_text(json.dumps(manifest))
        log(f"[{theme}] chunk {ci + 1}/{len(chunks)}: {len(df)} rows, "
            f"{time.time() - t0:.0f}s")
    conn.close()


def finalize_cache(cache_dir: str | Path, log=print) -> None:
    """チャンク群を loc_key ソート済みの単一 parquet へ書き直す。

    ソートにより地点単位の読み出しで row-group pruning が効く。
    """
    conn = duckdb.connect()
    for theme in THEMES:
        src = Path(cache_dir) / theme
        chunks = sorted(src.glob("chunk_*.parquet"))
        if not chunks:
            continue
        out = Path(cache_dir) / f"{theme}.parquet"
        t0 = time.time()
        file_list = ", ".join(f"'{c}'" for c in chunks)
        conn.execute(f"""
            COPY (SELECT * FROM read_parquet([{file_list}]) ORDER BY loc_key)
            TO '{out}' (FORMAT parquet, ROW_GROUP_SIZE 65536)
        """)
        n = conn.execute(f"SELECT count(*) FROM '{out}'").fetchone()[0]
        log(f"[{theme}] finalized: {n} rows -> {out.name} "
            f"({out.stat().st_size / 1e6:.0f}MB, {time.time() - t0:.0f}s)")
    conn.close()
