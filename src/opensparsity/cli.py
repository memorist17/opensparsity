"""コマンドラインインターフェース。

使い方:
    ops run --locations locations.yaml --out results/          # 実行（再開可能）
    ops run --locations locations.yaml --out results/ --start 0 --end 100
    ops status --out results/                                  # 進捗確認
    ops export --out results/ --csv metrics.csv                # CSV エクスポート
"""

import argparse
import sys
from pathlib import Path

import yaml

from .config import load_config
from .pipeline import run_batch
from .store import ResultStore


def _load_locations(path: str) -> list[dict]:
    """locations ファイルを読む。YAML（{locations: [{name, lat, lon}...]} または
    [{lat, lon}...]）と CSV（lat, lon[, name] 列）に対応。"""
    p = Path(path)
    if p.suffix.lower() == ".csv":
        import pandas as pd
        df = pd.read_csv(p)
        return df.to_dict("records")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("locations", data)
    out = []
    for item in data:
        if "coords" in item:  # 旧リポジトリの locations.yaml 形式
            out.append({"name": item.get("name"),
                        "lat": item["coords"][0], "lon": item["coords"][1]})
        else:
            out.append(item)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ops", description="Open-Sparsity pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="地点リストを処理（処理済みはスキップ）")
    p_run.add_argument("--locations", required=True, help="YAML または CSV の地点リスト")
    p_run.add_argument("--out", default="results", help="出力ディレクトリ（default: results/）")
    p_run.add_argument("--config", default=None, help="config.yaml のパス（default: リポジトリ直下）")
    p_run.add_argument("--start", type=int, default=None, help="地点リストの開始インデックス")
    p_run.add_argument("--end", type=int, default=None, help="地点リストの終了インデックス（排他）")
    p_run.add_argument("--force", action="store_true", help="処理済み地点も再計算する")
    p_run.add_argument("--cache", default=None, help="prefetch 済みキャッシュディレクトリ（あればローカル読み出し）")
    p_run.add_argument("--no-image", action="store_true", help="オーバーレイ画像を生成しない（数値のみ）")

    p_pre = sub.add_parser("prefetch", help="全地点分の Overture データを一括抽出してローカルキャッシュ化")
    p_pre.add_argument("--locations", required=True)
    p_pre.add_argument("--cache", required=True, help="キャッシュ出力ディレクトリ")
    p_pre.add_argument("--config", default=None)
    p_pre.add_argument("--mode", default="auto", choices=["auto", "static", "join"])
    p_pre.add_argument("--chunk-files", type=int, default=16)
    p_pre.add_argument("--theme", default="both", choices=["both", "buildings", "roads"])
    p_pre.add_argument("--no-finalize", action="store_true", help="loc_key ソートの最終化をスキップ")

    p_merge = sub.add_parser("merge", help="別マシンの results.db を取り込む（UPSERT）")
    p_merge.add_argument("--from", dest="src_db", required=True, help="取り込み元 results.db")
    p_merge.add_argument("--out", default="results", help="取り込み先ディレクトリ")

    p_status = sub.add_parser("status", help="results.db の進捗を表示")
    p_status.add_argument("--out", default="results")

    p_export = sub.add_parser("export", help="locations テーブルを CSV に書き出す")
    p_export.add_argument("--out", default="results")
    p_export.add_argument("--csv", required=True, help="出力 CSV パス")

    args = parser.parse_args(argv)

    if args.command == "run":
        locations = _load_locations(args.locations)
        if args.start is not None or args.end is not None:
            locations = locations[args.start or 0 : args.end]
        config = load_config(args.config)
        summary = run_batch(locations, config, args.out, force=args.force,
                            cache_dir=args.cache, no_image=args.no_image)
        print(f"完了: ok={summary['ok']} skipped={summary['skipped']} failed={summary['failed']}")
        return 0 if summary["failed"] == 0 else 1

    if args.command == "prefetch":
        import json as _json
        from .config import load_config as _lc
        from .prefetch import build_boxes, finalize_cache, prefetch_theme

        locations = _load_locations(args.locations)
        config = _lc(args.config)
        half = float(config["canvas"]["half_size_m"])
        boxes = build_boxes(locations, half)
        cache = Path(args.cache)
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "locations.json").write_text(
            _json.dumps(sorted(boxes["loc_key"].tolist())))
        themes = ["buildings", "roads"] if args.theme == "both" else [args.theme]
        for theme in themes:
            prefetch_theme(theme, boxes, cache, mode=args.mode,
                           chunk_files=args.chunk_files)
        if not args.no_finalize:
            finalize_cache(cache)
        print("prefetch 完了")
        return 0

    if args.command == "merge":
        store = ResultStore(Path(args.out) / "results.db")
        n0 = store.conn.execute("SELECT count(*) FROM locations").fetchone()[0]
        # URI形式('file:...?mode=ro')はsqliteのビルドによって使えないため、
        # プレーンなパスをパラメータバインドで渡す（書き込みはINSERTのみで src には触れない）
        store.conn.execute("ATTACH DATABASE ? AS src", (str(args.src_db),))

        # 列は必ず名前で対応させる。`SELECT *` は物理的な列順で入るため、
        # CREATE TABLE で作った DB（r_crit が中ほど）と ALTER TABLE ADD COLUMN で
        # 移行した DB（r_crit が末尾）を混ぜると、perc_dcrit〜r_crit の8列が
        # 1つずつズレたまま静かに書き込まれる（2026-08-07 に実データで発覚）。
        def common_columns(table: str) -> list[str]:
            dst = [r[1] for r in store.conn.execute(f"PRAGMA table_info({table})")]
            src = {r[1] for r in store.conn.execute(f"PRAGMA src.table_info({table})")}
            missing = [c for c in dst if c not in src]
            if missing:
                print(f"  {table}: src に無い列は NULL のまま: {', '.join(missing)}")
            return [c for c in dst if c in src]

        with store.conn:
            for table in ("locations", "curves"):
                cols = common_columns(table)
                if not cols:
                    raise SystemExit(f"{table}: 共通の列が無い（スキーマ不一致）")
                names = ", ".join(f'"{c}"' for c in cols)
                store.conn.execute(
                    f"INSERT OR REPLACE INTO {table} ({names}) "
                    f"SELECT {names} FROM src.{table}"
                )
        n1 = store.conn.execute("SELECT count(*) FROM locations").fetchone()[0]
        print(f"merged: {n0} -> {n1} rows")
        store.conn.execute("DETACH DATABASE src")
        store.close()
        return 0

    if args.command == "status":
        store = ResultStore(Path(args.out) / "results.db")
        print(store.status_summary() or "(empty)")
        store.close()
        return 0

    if args.command == "export":
        store = ResultStore(Path(args.out) / "results.db")
        df = store.to_dataframe()
        df.to_csv(args.csv, index=False)
        print(f"{len(df)} rows -> {args.csv}")
        store.close()
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
