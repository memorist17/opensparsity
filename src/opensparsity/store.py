"""結果ストア: 全地点の数値を SQLite 1ファイル (results.db) に集約する。

- locations: 1地点1行。指標 + 処理ステータス。主キー (lat, lon) の UPSERT で
  再実行しても重複せず、status='done' の地点はスキップできる（再開可能）。
- curves: 指標の元になる曲線（percolation / mfa_spectrum / lacunarity）。
  後から新しい指標を追加計算するときに再フェッチ不要にするための保険。
- WAL モードなので複数バッチプロセスからの同時書き込みも安全。
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS locations (
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    name TEXT,
    status TEXT NOT NULL,              -- 'done' | 'failed'
    error TEXT,
    processed_at TEXT,
    elapsed_sec REAL,
    code_version TEXT,
    overture_release TEXT,
    n_buildings INTEGER,
    n_building_nodes INTEGER,
    -- 基本指標
    density REAL,
    lacunarity_mean REAL,
    lacunarity_slope REAL,
    mfa_alpha_width REAL,
    mfa_D0 REAL,
    perc_dcrit REAL,
    perc_gmax REAL,
    -- 追加指標
    W_trans REAL,
    Delta_D REAL,
    beta REAL,
    gamma REAL,
    S_alpha REAL,
    PRIMARY KEY (lat, lon)
);
CREATE TABLE IF NOT EXISTS curves (
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    kind TEXT NOT NULL,                -- 'percolation' | 'mfa_spectrum' | 'lacunarity'
    data TEXT NOT NULL,                -- JSON: {列名: [値, ...], ...}
    PRIMARY KEY (lat, lon, kind)
);
"""


class ResultStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=60)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.executescript(SCHEMA)

    # --- 再開サポート ---
    def done_keys(self) -> set[tuple[float, float]]:
        """処理済み (status='done') の (lat, lon) 集合。起動時のスキップ判定に使う。"""
        rows = self.conn.execute(
            "SELECT lat, lon FROM locations WHERE status = 'done'"
        ).fetchall()
        return set(rows)

    # --- 書き込み（地点単位で1トランザクション） ---
    def upsert_result(
        self,
        lat: float,
        lon: float,
        *,
        name: str | None,
        metrics: dict,
        curves: dict[str, pd.DataFrame],
        elapsed_sec: float,
        code_version: str,
        overture_release: str,
        n_buildings: int | None = None,
        n_building_nodes: int | None = None,
    ) -> None:
        cols = dict(
            lat=lat, lon=lon, name=name, status="done", error=None,
            processed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            elapsed_sec=round(elapsed_sec, 1),
            code_version=code_version, overture_release=overture_release,
            n_buildings=n_buildings, n_building_nodes=n_building_nodes,
            **{k: (None if v is None or pd.isna(v) else float(v)) for k, v in metrics.items()},
        )
        placeholders = ", ".join("?" * len(cols))
        sql = (f"INSERT OR REPLACE INTO locations ({', '.join(cols)}) "
               f"VALUES ({placeholders})")
        with self.conn:
            self.conn.execute(sql, list(cols.values()))
            for kind, df in curves.items():
                payload = json.dumps(
                    {c: df[c].round(6).tolist() for c in df.columns},
                    ensure_ascii=False,
                )
                self.conn.execute(
                    "INSERT OR REPLACE INTO curves (lat, lon, kind, data) VALUES (?, ?, ?, ?)",
                    (lat, lon, kind, payload),
                )

    def mark_failed(self, lat: float, lon: float, name: str | None, error: str,
                    code_version: str, overture_release: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO locations "
                "(lat, lon, name, status, error, processed_at, code_version, overture_release) "
                "VALUES (?, ?, ?, 'failed', ?, ?, ?, ?)",
                (lat, lon, name, error[:500],
                 datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 code_version, overture_release),
            )

    # --- 読み出し ---
    def to_dataframe(self) -> pd.DataFrame:
        return pd.read_sql("SELECT * FROM locations", self.conn)

    def load_curve(self, lat: float, lon: float, kind: str) -> pd.DataFrame | None:
        row = self.conn.execute(
            "SELECT data FROM curves WHERE lat = ? AND lon = ? AND kind = ?",
            (lat, lon, kind),
        ).fetchone()
        return pd.DataFrame(json.loads(row[0])) if row else None

    def status_summary(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) FROM locations GROUP BY status"
        ).fetchall()
        return dict(rows)

    def close(self) -> None:
        self.conn.close()
