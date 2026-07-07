"""オーバーレイ画像の生成: combined ラスタ + ネットワークを1枚の PNG に。

レイヤ（下から）:
  白背景 → 道路ラスタ(薄グレー) → 建物ラスタ(濃グレー)
  → 道路エッジ(青) → 仮想エッジ(水色・細) → 建物ノード(赤点)
座標系: 北が上（raster row0 = 北端 / network: col = x + half, row = half - y）
"""

from pathlib import Path

import networkx as nx
import numpy as np
from PIL import Image, ImageDraw
from PIL.PngImagePlugin import PngInfo

COL_ROAD_RASTER = (208, 208, 208)
COL_BLDG_RASTER = (105, 105, 105)
COL_ROAD_EDGE = (0, 90, 230)
COL_VIRT_EDGE = (120, 190, 255)
COL_BLDG_NODE = (230, 30, 30)


def render_overlay(
    b_raster: np.ndarray,
    r_raster: np.ndarray,
    graph: nx.Graph,
    out_path: str | Path,
    *,
    half_size_m: float = 1000.0,
    metadata: dict[str, str] | None = None,
) -> Path:
    """ラスタとネットワークのオーバーレイ PNG を保存して検証情報を返す。

    Args:
        b_raster: 建物二値ラスタ (H, W), row0 = 北端
        r_raster: 道路ラスタ (H, W)
        graph: NetworkBuilder が生成したグラフ（ノード属性 x, y はメートル・中心原点・+y=北）
        out_path: 出力 PNG パス
        half_size_m: キャンバス半径（メートル）
        metadata: PNG tEXt チャンクに埋め込むキー/値
    """
    H, W = b_raster.shape
    img = np.full((H, W, 3), 255, dtype=np.uint8)
    img[r_raster > 0] = COL_ROAD_RASTER
    img[b_raster > 0] = COL_BLDG_RASTER
    im = Image.fromarray(img)
    draw = ImageDraw.Draw(im)

    def to_px(x: float, y: float) -> tuple[float, float]:
        return x + half_size_m, half_size_m - y

    pos = {
        n: to_px(float(a["x"]), float(a["y"]))
        for n, a in graph.nodes(data=True)
        if "x" in a and "y" in a
    }

    road_edges, virt_edges = [], []
    for u, v, a in graph.edges(data=True):
        if u in pos and v in pos:
            (virt_edges if a.get("type") == "virtual" else road_edges).append((pos[u], pos[v]))
    for p, q in road_edges:
        draw.line([p, q], fill=COL_ROAD_EDGE, width=2)
    for p, q in virt_edges:
        draw.line([p, q], fill=COL_VIRT_EDGE, width=1)

    for n, a in graph.nodes(data=True):
        if a.get("type") == "building" and n in pos:
            c, r = pos[n]
            draw.ellipse([c - 2.5, r - 2.5, c + 2.5, r + 2.5], fill=COL_BLDG_NODE)

    info = PngInfo()
    for k, v in (metadata or {}).items():
        info.add_text(k, str(v))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path, pnginfo=info, optimize=True)
    return out_path


def image_filename(lat: float, lon: float) -> str:
    """地点画像のファイル名規約: {lat:.4f}_{lon:.4f}.png"""
    return f"{lat:.4f}_{lon:.4f}.png"
