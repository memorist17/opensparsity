"""ネットワーク不要の単体テスト（合成データで指標計算と保存の往復を検証）。

実行: .venv/bin/python -m pytest tests/ -q
"""

import numpy as np
import pandas as pd
import pytest

from opensparsity.config import (
    create_lacunarity_analyzer,
    create_mfa_analyzer,
    create_percolation_analyzer,
    load_config,
)
from opensparsity.render import image_filename, render_overlay
from opensparsity.store import ResultStore


@pytest.fixture
def config():
    cfg = load_config()
    # テスト用に小さく
    cfg["analysis"]["r_max"] = 128
    cfg["analysis"]["percolation"]["d_max"] = 200
    cfg["analysis"]["percolation"]["d_steps"] = 20
    return cfg


def synth_raster(n=128, density=0.05, seed=42):
    rng = np.random.default_rng(seed)
    return (rng.random((n, n)) < density).astype(np.uint8)


def test_lacunarity_and_mfa(config):
    raster = synth_raster()
    lac = create_lacunarity_analyzer(config)
    lac_df, _ = lac.analyze(raster)
    assert (lac_df["lambda"] > 0).all()
    fit = lac.fit_power_law(lac_df)
    assert np.isfinite(fit["beta"])

    mfa = create_mfa_analyzer(config)
    mfa_df, _, _ = mfa.analyze(raster)
    dq = mfa.compute_generalized_dimensions(mfa_df)
    d0 = dq.loc[dq["q"] == 0, "D_q"].values[0]
    assert 1.0 < d0 <= 2.05  # ランダム点配置の D0 は 2 近傍


def test_percolation_two_clusters(config):
    """2つの離れたクラスタ: 小さい d では giant_fraction=0.5, 大きい d で 1.0"""
    import networkx as nx
    G = nx.Graph()
    # クラスタA (0,0)近傍 と クラスタB (150,0)近傍、各2ノード
    coords = {0: (0, 0), 1: (5, 0), 2: (150, 0), 3: (155, 0)}
    for n, (x, y) in coords.items():
        G.add_node(n, x=x, y=y, type="building")
    G.add_edge(0, 1, length=5.0)
    G.add_edge(2, 3, length=5.0)
    G.add_edge(1, 2, length=145.0)
    perc = create_percolation_analyzer(config)
    df, _ = perc.analyze(G)
    assert df.iloc[0]["giant_fraction"] < 1.0
    assert df.iloc[-1]["giant_fraction"] == 1.0


def test_store_roundtrip(tmp_path):
    store = ResultStore(tmp_path / "results.db")
    curves = {"percolation": pd.DataFrame({"d": [1.0, 2.0], "giant_fraction": [0.1, 1.0],
                                           "n_clusters": [5, 1]})}
    metrics = {"density": 0.05, "perc_dcrit": 42.0}
    store.upsert_result(35.0, 139.0, name="t", metrics=metrics, curves=curves,
                        elapsed_sec=1.0, code_version="test", overture_release="test")
    # 再開判定
    assert (35.0, 139.0) in store.done_keys()
    # 冪等（再 upsert しても1行のまま）
    store.upsert_result(35.0, 139.0, name="t", metrics=metrics, curves=curves,
                        elapsed_sec=2.0, code_version="test", overture_release="test")
    df = store.to_dataframe()
    assert len(df) == 1 and df.iloc[0]["density"] == 0.05
    # 曲線の往復
    c = store.load_curve(35.0, 139.0, "percolation")
    assert list(c["giant_fraction"]) == [0.1, 1.0]
    # 失敗記録は done に含まれない
    store.mark_failed(36.0, 140.0, "x", "boom", "test", "test")
    assert (36.0, 140.0) not in store.done_keys()
    store.close()


def test_render_overlay(tmp_path):
    import networkx as nx
    b = np.zeros((100, 100), dtype=np.uint8); b[40:45, 40:45] = 1
    r = np.zeros((100, 100), dtype=np.uint8); r[50, :] = 200
    G = nx.Graph()
    # 建物ノード: メートル座標 (=中心原点) で建物ラスタ位置に対応させる
    G.add_node(0, x=-8.0, y=8.0, type="building")   # → px(42, 42)
    G.add_node(1, x=0.0, y=0.0, type="road")
    G.add_edge(0, 1, length=10.0, type="virtual")
    out = render_overlay(b, r, G, tmp_path / image_filename(35.0, 139.0),
                         half_size_m=50.0, metadata={"lat": 35.0})
    assert out.exists() and out.name == "35.0000_139.0000.png"
    # 建物ノードの赤が建物ラスタ位置に描かれている
    from PIL import Image
    px = np.array(Image.open(out))
    assert (px[40:46, 40:46, 0] == 230).any()


def test_r_crit_max_slope():
    """r_crit（表1: argmax dG/dr）が最急上昇区間の中点を返す"""
    from opensparsity.indicators import find_r_crit_max_slope
    df = pd.DataFrame({
        "d": [0.0, 10.0, 20.0, 30.0, 40.0],
        "giant_fraction": [0.0, 0.05, 0.10, 0.90, 0.95],  # 20-30 で急上昇
    })
    r = find_r_crit_max_slope(df)
    assert r == 25.0
