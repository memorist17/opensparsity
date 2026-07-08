#!/usr/bin/env python
"""OS指標による都市形態カタログ。

os_vectors.csv（global_v2 1万地点 × 9次元 OS指標）を KMeans でクラスタリングし、
各形態タイプに指標プロファイル・レーダー・日本語類型解説・代表画像・9次元全値を
与えた HTML カタログを生成する。

改善点（2026-07-08）:
- 指標を手法グループ順に並べる（密度 → ラキュナリティ → パーコレーション → MFA）
- 桁レンジが 5 桁に及ぶ Λ̄ を対数変換してからクラスタリング（外れ値でスケールが
  歪むのを防ぐ）
- 「指標の見方」表（記号・意味・単位・大小の向き）をカタログ冒頭に置く
"""
import base64
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Hiragino Sans", "Hiragino Kaku Gothic Pro",
                                   "AppleGothic", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
import numpy as np
import pandas as pd
from PIL import Image
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

HERE = Path(__file__).parent
VECS = HERE.parent / "exp01_density_breakdown" / "os_vectors.csv"
IMG_DIR = HERE / "reps_out" / "images"
K = 6
SEED = 42

# 手法グループ順（密度 → ラキュナリティ → パーコレーション → MFA）
FEAT = ["density", "lacunarity_mean", "lacunarity_slope",
        "r_crit", "W_trans", "gamma",
        "mfa_alpha_width", "Delta_D", "S_alpha"]
# クラスタリング前に対数変換する特徴（5桁レンジの外れ値対策）
LOG_FEATURES = {"lacunarity_mean"}

GROUP = {
    "density": "密度",
    "lacunarity_mean": "ラキュナリティ", "lacunarity_slope": "ラキュナリティ",
    "r_crit": "パーコレーション", "W_trans": "パーコレーション", "gamma": "パーコレーション",
    "mfa_alpha_width": "MFA", "Delta_D": "MFA", "S_alpha": "MFA",
}
GROUP_COLOR = {"密度": "#52514e", "ラキュナリティ": "#1baf7a",
               "パーコレーション": "#2a78d6", "MFA": "#eda100"}
SHORT = {"density": "d", "lacunarity_mean": "Λ̄", "lacunarity_slope": "s_Λ",
         "r_crit": "r_crit", "W_trans": "W_trans", "gamma": "γ",
         "mfa_alpha_width": "Δα", "Delta_D": "ΔD", "S_alpha": "S_α"}
MEANING = {"density": "密度", "lacunarity_mean": "空隙のムラ",
           "lacunarity_slope": "ムラのスケール減衰", "r_crit": "連結までの距離",
           "W_trans": "連結の緩やかさ", "gamma": "連結の急峻さ",
           "mfa_alpha_width": "構造の複雑さ", "Delta_D": "質量の集中度",
           "S_alpha": "複雑さの偏り"}
UNIT = {"density": "占有率 0–1", "lacunarity_mean": "分散/平均²（対数軸）",
        "lacunarity_slope": "log–log 勾配", "r_crit": "メートル",
        "W_trans": "メートル", "gamma": "ΔG / m",
        "mfa_alpha_width": "α 幅（無次元）", "Delta_D": "D₀−D₂（無次元）",
        "S_alpha": "歪度（無次元）"}
DIR_UP = {"density": "密", "lacunarity_mean": "空隙にムラ",
          "lacunarity_slope": "急減衰", "r_crit": "連結に長距離（分断的）",
          "W_trans": "漸進的な連結（緩い転移）", "gamma": "急峻な連結（相転移的）",
          "mfa_alpha_width": "複雑（多重フラクタル強）", "Delta_D": "質量が集中（核的）",
          "S_alpha": "右に偏り"}
DIR_DOWN = {"density": "疎", "lacunarity_mean": "均質",
            "lacunarity_slope": "緩やか", "r_crit": "近距離で連結（密結合）",
            "W_trans": "急峻な連結（狭い転移）", "gamma": "緩慢な連結",
            "mfa_alpha_width": "単純（単一スケール）", "Delta_D": "質量が均等",
            "S_alpha": "左/対称"}

PALETTE = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948"]
C_TEXT, C_MUTED, C_GRID = "#0b0b0b", "#52514e", "#d8d8d4"

HIGH = {f: DIR_UP[f] for f in FEAT}
LOW = {f: DIR_DOWN[f] for f in FEAT}

# 代表画像を確認して洗練した日本語類型名・解説（Λ̄対数変換・再クラスタ後）
DESCRIPTIONS: dict[int, dict] = {
    1: {"name": "格子核・急峻連結型（中密）",
        "body": "計画的な格子街区を核に持ち、そこから周辺へ建物が散在する。核の内部が"
                "ある距離で一気に連結するため γ が高い（+0.7σ）。中密度（d≈0.015）で、"
                "本カタログ最大のクラスタ。"},
    2: {"name": "街道散在型（疎）",
        "body": "山あいや海岸沿いの道路に沿って建物がまばらに点在する。空隙のムラが"
                "大きく（Λ̄ が高い）、密度は低い（d≈0.003）。世界の疎居住に広く見られる。"},
    3: {"name": "凝集放射型（中密・漸進連結）",
        "body": "建物が一角に凝集し、そこから道路が枝分かれして広がる。連結が広い距離"
                "範囲にわたって緩やかに進む（W_trans が +1.8σ と際立つ）。開拓前線や"
                "緩斜面の集落に多い。"},
    4: {"name": "標準中密型",
        "body": "9指標がいずれも平均付近に収まる、際立った偏りのない中密度（d≈0.018）の"
                "集落。特定の形態に偏らず多様な地域に分布する「基準的」なタイプ。"},
    5: {"name": "稠密市街型（高密）",
        "body": "建物が密に詰まり空隙が均質（d≈0.075 と最高密、Λ̄ 最小）。街路網が"
                "発達し、近距離で全体が連結する市街地＝いわゆる「街」。"},
    6: {"name": "山間散村型（疎・漸進連結）",
        "body": "極めて疎（d≈0.004）で空隙のムラが最大（Λ̄ 最高）、建物が小塊で点在し"
                "連結は緩慢（W_trans +0.8σ）。山間・内陸の孤立した散村。"},
}


def to_feature_matrix(frame: pd.DataFrame) -> np.ndarray:
    """DataFrame → クラスタリング用特徴行列（LOG_FEATURES を対数変換）。"""
    X = frame[FEAT].to_numpy(float).copy()
    for f in LOG_FEATURES:
        j = FEAT.index(f)
        X[:, j] = np.log(np.maximum(X[:, j], 1e-9))
    return X


def embed_image(lat: float, lon: float, size: int = 420) -> str | None:
    p = IMG_DIR / f"{lat:.4f}_{lon:.4f}.png"
    if not p.exists():
        return None
    im = Image.open(p).convert("RGB")
    im.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def radar(profile: dict, color: str) -> str:
    feats = FEAT
    vals = [profile[f] for f in feats]
    ang = np.linspace(0, 2 * np.pi, len(feats), endpoint=False)
    ang = np.concatenate([ang, ang[:1]])
    vals = vals + vals[:1]
    fig, ax = plt.subplots(figsize=(3.4, 3.4), subplot_kw=dict(polar=True), dpi=110)
    ax.set_ylim(-2, 2)
    ax.plot(ang, vals, color=color, linewidth=2)
    ax.fill(ang, vals, color=color, alpha=0.2)
    ax.set_xticks(ang[:-1])
    ax.set_xticklabels([SHORT[f] for f in feats], fontsize=8, color=C_TEXT)
    ax.set_yticks([-1, 0, 1])
    ax.set_yticklabels(["-1σ", "0", "+1σ"], fontsize=6, color=C_MUTED)
    ax.grid(color=C_GRID, linewidth=0.5)
    ax.spines["polar"].set_color(C_GRID)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", transparent=True)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def scatter_pca(Xz: np.ndarray, labels: np.ndarray, order: list,
                names: dict[int, str]) -> str:
    pca = PCA(n_components=2, random_state=SEED)
    coords = pca.fit_transform(Xz)
    evr = pca.explained_variance_ratio_ * 100
    fig, ax = plt.subplots(figsize=(8.5, 6), dpi=120)
    for rank, cid in enumerate(order, 1):
        m = labels == cid
        ax.scatter(coords[m, 0], coords[m, 1], s=5, c=PALETTE[rank - 1],
                   alpha=0.35, linewidths=0, label=f"{rank}. {names[cid]}")
    ax.set_xlabel(f"PC1 ({evr[0]:.0f}%)", color=C_TEXT, fontsize=10)
    ax.set_ylabel(f"PC2 ({evr[1]:.0f}%)", color=C_TEXT, fontsize=10)
    ax.set_title("9次元 OS 空間の PCA 射影（色＝クラスタ）", color=C_TEXT, fontsize=12)
    ax.grid(True, alpha=0.2, linewidth=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    for sp in ax.spines.values():
        sp.set_color(C_MUTED)
    ax.tick_params(colors=C_MUTED, labelsize=8)
    leg = ax.legend(loc="best", fontsize=8, framealpha=0.9, markerscale=2)
    for t in leg.get_texts():
        t.set_color(C_TEXT)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def describe(profile: dict) -> tuple[str, str]:
    highs = [f for f in FEAT if profile[f] > 0.7]
    lows = [f for f in FEAT if profile[f] < -0.7]
    phrases = [HIGH[f] for f in highs] + [LOW[f] for f in lows]
    d = profile["density"]
    dens_word = "高密" if d > 0.7 else ("疎" if d < -0.4 else "中密")
    if profile["gamma"] > 0.5:
        conn = "急峻連結型"
    elif profile["W_trans"] > 0.5:
        conn = "漸進連結型"
    elif profile["r_crit"] > 0.5:
        conn = "分断型"
    else:
        conn = "標準連結型"
    name = f"{dens_word}・{conn}"
    body = ("、".join(phrases) + "、という特徴を持つ形態タイプ。") if phrases else \
        "9指標すべてが平均付近に収まる、際立った偏りのない標準的な形態。"
    return name, body


def legend_table() -> str:
    """指標の見方表（グループ・記号・意味・単位・大小の向き）。"""
    rows = ""
    for f in FEAT:
        g = GROUP[f]
        rows += (
            f'<tr><td><span class="gdot" style="background:{GROUP_COLOR[g]}"></span>{g}</td>'
            f'<td class="sym">{SHORT[f]}</td><td>{MEANING[f]}</td>'
            f'<td class="unit">{UNIT[f]}</td>'
            f'<td class="up">↑ {DIR_UP[f]}</td><td class="dn">↓ {DIR_DOWN[f]}</td></tr>'
        )
    return f"""<table class="legend">
      <thead><tr><th>群</th><th>記号</th><th>意味</th><th>単位</th>
        <th>値が大きい</th><th>値が小さい</th></tr></thead>
      <tbody>{rows}</tbody></table>"""


def main():
    df = pd.read_csv(VECS)
    df = df[df.density > 1e-5].reset_index(drop=True)
    Xt = to_feature_matrix(df)
    scaler = StandardScaler().fit(Xt)
    Xz = scaler.transform(Xt)
    km = KMeans(n_clusters=K, random_state=SEED, n_init=10).fit(Xz)
    df["cluster"] = km.labels_
    df.to_csv(HERE / "catalog_assignments.csv", index=False)

    order = df["cluster"].value_counts().index.tolist()
    names, cards = {}, []
    for rank, cid in enumerate(order, 1):
        sub = df[df.cluster == cid]
        prof = {f: float(scaler.transform(to_feature_matrix(sub).mean(axis=0, keepdims=True))[0][i])
                for i, f in enumerate(FEAT)}
        center = km.cluster_centers_[cid]
        dist = np.linalg.norm(scaler.transform(to_feature_matrix(sub)) - center, axis=1)
        reps = sub.iloc[np.argsort(dist)[:5]]
        if rank in DESCRIPTIONS:
            name, body = DESCRIPTIONS[rank]["name"], DESCRIPTIONS[rank]["body"]
        else:
            name, body = describe(prof)
        names[cid] = name
        regions = sub["subregion"].value_counts().head(3)
        color = PALETTE[rank - 1]
        gallery = "".join(
            f'<figure><img src="{uri}"><figcaption>{r["lat"]:.3f}, {r["lon"]:.3f}</figcaption></figure>'
            for _, r in reps.head(3).iterrows()
            if (uri := embed_image(r["lat"], r["lon"]))
        )
        rep_rows = "".join(
            f"<tr><td>{r['lat']:.3f}, {r['lon']:.3f}</td><td>{r['subregion']}</td>"
            f"<td>{r['density']:.4f}</td><td>{r['lacunarity_mean']:.1f}</td>"
            f"<td>{r['lacunarity_slope']:.3f}</td><td>{r['r_crit']:.0f}</td>"
            f"<td>{r['W_trans']:.0f}</td><td>{r['gamma']:.4f}</td>"
            f"<td>{r['mfa_alpha_width']:.3f}</td><td>{r['Delta_D']:.3f}</td>"
            f"<td>{r['S_alpha']:.3f}</td></tr>"
            for _, r in reps.iterrows()
        )
        badges = "".join(
            f'<span class="badge" style="background:{color}">'
            f'{SHORT[f]} {"↑" if prof[f] > 0 else "↓"}{abs(prof[f]):.1f}σ</span>'
            for f in sorted(FEAT, key=lambda f: -abs(prof[f]))[:4]
        )
        reg_txt = " / ".join(f"{k}（{v}）" for k, v in regions.items())
        cards.append(f"""
        <section class="card">
          <div class="card-head" style="border-color:{color}">
            <span class="rank" style="background:{color}">{rank}</span>
            <div><h2>{name}</h2>
              <div class="meta">{len(sub):,} 地点（全体の {len(sub)/len(df)*100:.1f}%）</div></div>
          </div>
          <div class="card-body">
            <img class="radar" src="{radar(prof, color)}" alt="radar">
            <div class="desc"><p>{body}</p>
              <div class="badges">{badges}</div>
              <div class="regions"><b>主な地域:</b> {reg_txt}</div></div>
          </div>
          <div class="gallery">{gallery}</div>
          <div class="table-wrap"><table class="reps">
            <thead><tr><th>lat, lon</th><th>地域</th>
              <th>d</th><th>Λ̄</th><th>s_Λ</th><th>r_crit</th><th>W_trans</th>
              <th>γ</th><th>Δα</th><th>ΔD</th><th>S_α</th></tr></thead>
            <tbody>{rep_rows}</tbody></table></div>
        </section>""")

    html = f"""<div class="wrap">
      <header>
        <h1>都市形態カタログ（OS指標）</h1>
        <p class="sub">global_v2 全球サンプル {len(df):,} 地点を 9 次元 Open-Sparsity 指標で
        教師なしクラスタリング（KMeans, k={K}）。指標は手法グループ順（密度→ラキュナリティ
        →パーコレーション→MFA）に並べ、Λ̄ は対数変換してからクラスタリングした。</p>
      </header>
      <section class="legend-box">
        <h3>指標の見方</h3>
        {legend_table()}
      </section>
      <div class="overview">
        <img src="{scatter_pca(Xz, km.labels_.astype(int), order, names)}" alt="PCA散布図">
      </div>
      {"".join(cards)}
      <footer>レーダーは各指標の z-score（全体平均=0, ±1σ 目盛、Λ̄ は対数後）。
      代表地点表の値は生の実測値（Λ̄ は対数前）。</footer>
    </div>
    <style>
      .wrap {{ max-width: 1000px; margin: 0 auto; font-family: system-ui, sans-serif;
              color: {C_TEXT}; line-height: 1.6; }}
      header h1 {{ margin-bottom: 4px; }}
      .sub {{ color: {C_MUTED}; font-size: 14px; }}
      .legend-box {{ border: 1px solid {C_GRID}; border-radius: 10px; padding: 12px 16px;
                     margin: 16px 0; background: #fafaf8; }}
      .legend-box h3 {{ margin: 0 0 8px; font-size: 15px; }}
      table.legend {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
      table.legend th {{ text-align: left; color: {C_MUTED}; font-weight: 600;
                         padding: 4px 8px; border-bottom: 1px solid {C_GRID}; }}
      table.legend td {{ padding: 4px 8px; border-bottom: 1px solid #eee; vertical-align: top; }}
      table.legend .sym {{ font-family: ui-monospace, monospace; font-weight: 700; }}
      table.legend .unit {{ color: {C_MUTED}; font-size: 12px; }}
      table.legend .up {{ color: #1a6; font-size: 12px; }}
      table.legend .dn {{ color: #a63; font-size: 12px; }}
      .gdot {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%;
               margin-right: 5px; vertical-align: middle; }}
      .overview img {{ width: 100%; max-width: 780px; display: block; margin: 8px auto 4px; }}
      .card {{ border: 1px solid {C_GRID}; border-radius: 10px; margin: 18px 0; overflow: hidden; }}
      .card-head {{ display: flex; align-items: center; gap: 12px; padding: 12px 16px;
                    border-left: 6px solid; background: #fafaf8; }}
      .card-head h2 {{ margin: 0; font-size: 19px; }}
      .rank {{ color: #fff; width: 30px; height: 30px; border-radius: 50%;
               display: grid; place-items: center; font-weight: 700; }}
      .meta {{ color: {C_MUTED}; font-size: 13px; }}
      .card-body {{ display: flex; gap: 18px; padding: 16px; align-items: center; }}
      .radar {{ width: 260px; flex: none; }}
      .desc p {{ margin: 0 0 10px; }}
      .badges {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }}
      .badge {{ color: #fff; font-size: 12px; padding: 2px 8px; border-radius: 10px; }}
      .regions {{ font-size: 13px; color: {C_MUTED}; }}
      .gallery {{ display: flex; gap: 8px; padding: 0 16px 12px; flex-wrap: wrap; }}
      .gallery figure {{ margin: 0; }}
      .gallery img {{ width: 200px; height: 200px; object-fit: cover;
                      border: 1px solid {C_GRID}; border-radius: 6px; display: block; }}
      .gallery figcaption {{ font-size: 11px; color: {C_MUTED}; margin-top: 3px;
                             font-variant-numeric: tabular-nums; }}
      .table-wrap {{ overflow-x: auto; }}
      table.reps {{ width: 100%; border-collapse: collapse; font-size: 12.5px;
                    white-space: nowrap; font-variant-numeric: tabular-nums; }}
      table.reps th, table.reps td {{ text-align: left; padding: 6px 12px;
                                       border-top: 1px solid {C_GRID}; }}
      table.reps th {{ color: {C_MUTED}; font-weight: 600; }}
      footer {{ color: {C_MUTED}; font-size: 12px; margin-top: 24px; }}
      @media (prefers-color-scheme: dark) {{
        .wrap {{ color: #eee; }} .card-head, .legend-box {{ background: #1e1e1c; }}
        .card, .legend-box {{ border-color: #333; }}
        table.reps th, table.reps td {{ border-color: #333; }}
        table.legend td {{ border-color: #2a2a28; }}
      }}
    </style>"""
    (HERE / "catalog.html").write_text(html, encoding="utf-8")
    print(f"カタログ生成: {K} タイプ, {len(df):,} 地点")
    for rank, cid in enumerate(order, 1):
        sub = df[df.cluster == cid]
        prof = {f: float(scaler.transform(to_feature_matrix(sub).mean(axis=0, keepdims=True))[0][i])
                for i, f in enumerate(FEAT)}
        name, _ = describe(prof)
        reps = sub.iloc[np.argsort(np.linalg.norm(
            scaler.transform(to_feature_matrix(sub)) - km.cluster_centers_[cid], axis=1))[:3]]
        print(f"  {rank}. {name}: {len(sub):,}地点 d={sub.density.mean():.4f} "
              f"Λ̄={sub.lacunarity_mean.median():.1f} γz={prof['gamma']:+.1f} Wz={prof['W_trans']:+.1f}")
        for _, r in reps.iterrows():
            print(f"       rep {r['lat']:.4f},{r['lon']:.4f}")


if __name__ == "__main__":
    main()
