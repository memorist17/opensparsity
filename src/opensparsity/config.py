"""設定ロードと分析器ファクトリ。

設定はリポジトリ直下の config.yaml 1ファイルのみ。
分析器の生成をここに集約し、他モジュールはコンストラクタ引数に依存しない。
"""

from pathlib import Path
from typing import Any

import yaml

from .indicators import LacunarityAnalyzer, MultifractalAnalyzer, PercolationAnalyzer

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """config.yaml を読み込んで dict を返す。"""
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_lacunarity_analyzer(config: dict) -> LacunarityAnalyzer:
    ac = config.get("analysis", {})
    return LacunarityAnalyzer(
        r_min=ac.get("r_min", 2),
        r_max=ac.get("r_max", 2000),
        r_steps=ac.get("r_steps", 20),
        full_scan=ac.get("lacunarity", {}).get("full_scan", True),
        n_jobs=ac.get("n_jobs", -1),
    )


def create_mfa_analyzer(config: dict) -> MultifractalAnalyzer:
    ac = config.get("analysis", {})
    mfa = ac.get("mfa", {})
    return MultifractalAnalyzer(
        r_min=ac.get("r_min", 2),
        r_max=ac.get("r_max", 2000),
        r_steps=ac.get("r_steps", 20),
        q_min=mfa.get("q_min", -10),
        q_max=mfa.get("q_max", 10),
        q_steps=mfa.get("q_steps", 41),
        grid_shift_count=mfa.get("grid_shift_count", 16),
        n_jobs=ac.get("n_jobs", -1),
    )


def create_percolation_analyzer(config: dict) -> PercolationAnalyzer:
    perc = config.get("analysis", {}).get("percolation", {})
    return PercolationAnalyzer(
        d_min=perc.get("d_min", 1),
        d_max=perc.get("d_max", 2000),
        d_steps=perc.get("d_steps", 100),
        distance_type=perc.get("distance_type", "shortest_path"),
        node_filter=perc.get("node_filter", "building"),
    )
