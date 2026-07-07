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
        summary = run_batch(locations, config, args.out, force=args.force)
        print(f"完了: ok={summary['ok']} skipped={summary['skipped']} failed={summary['failed']}")
        return 0 if summary["failed"] == 0 else 1

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
