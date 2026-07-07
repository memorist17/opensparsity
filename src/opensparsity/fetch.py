"""Overture Maps data fetcher using DuckDB + S3.

Based on official docs: https://docs.overturemaps.org
Uses anonymous S3 access to overturemaps-us-west-2 bucket.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb
import geopandas as gpd
from shapely import wkb
from tqdm import tqdm

# Latest release version (update as needed)
# 古いリリースはバケットから削除されるため、fetch が "No files found" で失敗したら
# release/ 配下の glob で存在するバージョンを確認して更新すること
# Updated: 2026-07-07 — 2026-04-15.0 が bucket から消えたため 2026-06-17.0 へ
OVERTURE_RELEASE = "2026-06-17.0"

OVERTURE_S3_BASE = f"s3://overturemaps-us-west-2/release/{OVERTURE_RELEASE}"


@dataclass
class OvertureFetcher:
    """Fetch buildings and roads from Overture Maps via DuckDB S3 access."""

    bbox_wgs84: tuple[float, float, float, float] | None = None  # (min_lon, min_lat, max_lon, max_lat)
    lat: float | None = None
    lon: float | None = None
    half_size_m: float = 1000.0
    road_width_fallback: dict[str, float] = field(default_factory=lambda: {
        "motorway": 20,
        "trunk": 15,
        "primary": 12,
        "secondary": 10,
        "tertiary": 8,
        "residential": 6,
        "service": 4,
        "default": 5,
    })

    def __post_init__(self) -> None:
        """Initialize DuckDB connection with spatial extensions and S3 access."""
        self.conn = self._create_connection()

    @staticmethod
    def _create_connection():
        """Create a DuckDB connection with spatial/httpfs extensions and anonymous S3 access."""
        conn = duckdb.connect()
        # Install and load required extensions
        # Note: In some environments these might need to be installed explicitly
        try:
            conn.execute("INSTALL spatial; LOAD spatial;")
            conn.execute("INSTALL httpfs; LOAD httpfs;")
        except Exception as e:
            print(f"Warning: Could not install/load DuckDB extensions: {e}")
            print("Trying to proceed, assuming they might be pre-loaded...")

        # Configure anonymous S3 access (no-sign-request equivalent)
        conn.execute("SET s3_region='us-west-2';")
        conn.execute("SET s3_access_key_id='';")
        conn.execute("SET s3_secret_access_key='';")
        return conn

    def fetch_all(self, verbose: bool = True) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """
        Fetch buildings and roads concurrently.

        建物と道路のクエリはそれぞれ S3 上の全 parquet ファイルの
        メタデータスキャンを伴い直列だと約2倍の時間がかかるため、
        別コネクションで並列実行する（DuckDB コネクションは
        同時クエリに対してスレッドセーフでないため共有しない）。

        Returns:
            (buildings_gdf, roads_gdf)
        """
        from concurrent.futures import ThreadPoolExecutor

        def _buildings():
            conn = self._create_connection()
            try:
                return self.fetch_buildings(verbose=verbose, conn=conn)
            finally:
                conn.close()

        def _roads():
            conn = self._create_connection()
            try:
                return self.fetch_roads(verbose=verbose, conn=conn)
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            f_b = pool.submit(_buildings)
            f_r = pool.submit(_roads)
            return f_b.result(), f_r.result()

    def __enter__(self) -> "OvertureFetcher":
        """Context manager enter."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    def fetch_buildings(self, verbose: bool = True, conn=None) -> gpd.GeoDataFrame:
        """Fetch building polygons within the bounding box."""
        conn = conn if conn is not None else self.conn
        bbox = self._get_bbox_wgs84()
        min_lon, min_lat, max_lon, max_lat = bbox

        if verbose:
            print(f"Fetching buildings in bbox: {bbox}")

        query = f"""
        SELECT
            id,
            names.primary AS name,
            height,
            num_floors,
            ST_AsWKB(geometry) AS geometry
        FROM read_parquet(
            '{OVERTURE_S3_BASE}/theme=buildings/type=building/*',
            filename=true,
            hive_partitioning=1
        )
        WHERE bbox.xmin >= {min_lon}
          AND bbox.xmax <= {max_lon}
          AND bbox.ymin >= {min_lat}
          AND bbox.ymax <= {max_lat}
        """

        try:
            result = conn.execute(query).fetchdf()
        except Exception as e:
            print(f"Error fetching buildings: {e}")
            return gpd.GeoDataFrame(
                columns=["id", "name", "height", "num_floors", "geometry"],
                geometry="geometry",
                crs="EPSG:4326",
            )

        gdf = buildings_gdf_from_df(result, verbose=verbose)
        if verbose:
            print(f"Fetched {len(gdf)} buildings")
        return gdf

    def fetch_roads(self, verbose: bool = True, conn=None) -> gpd.GeoDataFrame:
        """Fetch road segments within the bounding box."""
        conn = conn if conn is not None else self.conn
        bbox = self._get_bbox_wgs84()
        min_lon, min_lat, max_lon, max_lat = bbox

        if verbose:
            print(f"Fetching roads in bbox: {bbox}")

        query = f"""
        SELECT
            id,
            names.primary AS name,
            class,
            subclass,
            ST_AsWKB(geometry) AS geometry
        FROM read_parquet(
            '{OVERTURE_S3_BASE}/theme=transportation/type=segment/*',
            filename=true,
            hive_partitioning=1
        )
        WHERE (bbox.xmin <= {max_lon} AND bbox.xmax >= {min_lon})
          AND (bbox.ymin <= {max_lat} AND bbox.ymax >= {min_lat})
          AND subtype = 'road'
        """

        try:
            result = conn.execute(query).fetchdf()
        except Exception as e:
            print(f"Error fetching roads: {e}")
            return gpd.GeoDataFrame(
                columns=["id", "name", "class", "subclass", "width", "geometry"],
                geometry="geometry",
                crs="EPSG:4326",
            )

        gdf = roads_gdf_from_df(result, road_width_fallback=self.road_width_fallback,
                                verbose=verbose)
        if verbose:
            print(f"Fetched {len(gdf)} road segments")
        return gdf

    def _get_bbox_wgs84(self) -> tuple[float, float, float, float]:
        """
        Get approximate WGS84 bounding box.

        Returns:
            (min_lon, min_lat, max_lon, max_lat)
        """
        # If bbox_wgs84 is provided directly, use it
        if self.bbox_wgs84 is not None:
            return self.bbox_wgs84

        # Otherwise compute from lat/lon
        if self.lat is None or self.lon is None:
            raise ValueError("Either bbox_wgs84 or lat/lon must be provided")

        # Approximate degrees per meter at given latitude
        import math
        lat_rad = math.radians(self.lat)
        m_per_deg_lat = 111132.92 - 559.82 * math.cos(2 * lat_rad) + 1.175 * math.cos(4 * lat_rad)
        m_per_deg_lon = 111412.84 * math.cos(lat_rad) - 93.5 * math.cos(3 * lat_rad)

        delta_lat = self.half_size_m / m_per_deg_lat
        delta_lon = self.half_size_m / m_per_deg_lon

        return (
            self.lon - delta_lon,  # min_lon
            self.lat - delta_lat,  # min_lat
            self.lon + delta_lon,  # max_lon
            self.lat + delta_lat,  # max_lat
        )

    def get_width_fallback_stats(self, roads_gdf: gpd.GeoDataFrame) -> dict:
        """
        Get statistics about road width fallback usage.

        Args:
            roads_gdf: Road GeoDataFrame with 'class' and 'width' columns

        Returns:
            Dictionary with road count and class distribution
        """
        if len(roads_gdf) == 0:
            return {"count": 0, "class_distribution": {}}

        class_counts = roads_gdf["class"].value_counts().to_dict()
        return {
            "count": len(roads_gdf),
            "class_distribution": class_counts,
        }

    def close(self) -> None:
        """Close DuckDB connection."""
        try:
            self.conn.close()
        except:
            pass

ROAD_WIDTH_FALLBACK = {
    "motorway": 20, "trunk": 15, "primary": 12, "secondary": 10,
    "tertiary": 8, "residential": 6, "service": 4, "default": 5,
}

_BUILDING_COLS = ["id", "name", "height", "num_floors", "geometry"]
_ROAD_COLS = ["id", "name", "class", "subclass", "width", "geometry"]


def buildings_gdf_from_df(result, verbose: bool = False) -> gpd.GeoDataFrame:
    """クエリ結果（WKB 列を含む DataFrame）→ 建物 GeoDataFrame。"""
    if len(result) == 0:
        return gpd.GeoDataFrame(columns=_BUILDING_COLS, geometry="geometry",
                                crs="EPSG:4326")
    geometries = [
        wkb.loads(bytes(g)) if g is not None else None
        for g in tqdm(result["geometry"], desc="Parsing buildings", disable=not verbose)
    ]
    return gpd.GeoDataFrame(result.drop(columns=["geometry"]), geometry=geometries,
                            crs="EPSG:4326")


def roads_gdf_from_df(result, road_width_fallback=None,
                      verbose: bool = False) -> gpd.GeoDataFrame:
    """クエリ結果（WKB 列を含む DataFrame）→ 道路 GeoDataFrame（width 付与込み）。"""
    fallback = road_width_fallback or ROAD_WIDTH_FALLBACK
    if len(result) == 0:
        return gpd.GeoDataFrame(columns=_ROAD_COLS, geometry="geometry",
                                crs="EPSG:4326")
    geometries = [
        wkb.loads(bytes(g)) if g is not None else None
        for g in tqdm(result["geometry"], desc="Parsing roads", disable=not verbose)
    ]
    gdf = gpd.GeoDataFrame(result.drop(columns=["geometry"]), geometry=geometries,
                           crs="EPSG:4326")
    gdf["width"] = gdf["class"].apply(
        lambda x: fallback.get(x, fallback["default"]))
    return gdf


class CacheFetcher:
    """prefetch 済みローカルキャッシュからの読み出し（S3 フェッチと同一の GDF を返す）。

    cache_dir には finalize_cache() 後の buildings.parquet / roads.parquet
    （無ければ <theme>/chunk_*.parquet 群）が必要。
    """

    def __init__(self, cache_dir):
        import json as _json
        from pathlib import Path as _P
        self.cache_dir = _P(cache_dir)
        self.conn = duckdb.connect()
        self._sources = {}
        for theme in ("buildings", "roads"):
            final = self.cache_dir / f"{theme}.parquet"
            chunks = self.cache_dir / theme
            if final.exists():
                self._sources[theme] = str(final)
            elif chunks.exists() and any(chunks.glob("chunk_*.parquet")):
                self._sources[theme] = str(chunks / "chunk_*.parquet")
            else:
                self._sources[theme] = None
        # prefetch 対象の地点キー集合（無い地点は S3 フォールバックさせる）
        keys_path = self.cache_dir / "locations.json"
        self._keys = set(_json.loads(keys_path.read_text())) if keys_path.exists() else None

    def _read(self, theme: str, key: str):
        src = self._sources[theme]
        if src is None:
            raise FileNotFoundError(f"cache not found for theme={theme} in {self.cache_dir}")
        return self.conn.execute(
            f"SELECT * EXCLUDE (loc_key) FROM read_parquet('{src}') WHERE loc_key = ?",
            [key],
        ).fetchdf()

    def has(self, key: str) -> bool:
        """この地点がキャッシュ対象か（対象外は S3 フォールバック）。

        「行が無い」は正当な空地点でありうるため、存在判定は
        prefetch 時に記録された locations.json のキー集合で行う。
        """
        if any(self._sources[t] is None for t in ("buildings", "roads")):
            return False
        return True if self._keys is None else key in self._keys

    def fetch_all(self, key: str, verbose: bool = False):
        b = buildings_gdf_from_df(self._read("buildings", key), verbose=verbose)
        r = roads_gdf_from_df(self._read("roads", key), verbose=verbose)
        return b, r

    def close(self):
        self.conn.close()
