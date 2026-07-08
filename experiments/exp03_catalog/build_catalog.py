#!/usr/bin/env python
"""OS指標による都市形態カタログ（試作）。

os_vectors.csv（global_v2 1万地点 × 9次元 OS指標）を KMeans でクラスタリングし、
各クラスタ（形態タイプ）に指標プロファイル・レーダーチャート・日本語類型解説・
代表地点・地理分布を与えた HTML カタログを生成する。

AlphaEarth が「学習された不透明な埋め込み」で地表を類型化するのに対し、
本カタログは「各軸が物理的意味を持つ OS 指標」で都市形態を類型化する。
"""
import base64
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
# 画像内の日本語（散布図タイトル・凡例）用フォント。Mac のヒラギノを優先
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
IMG_DIR = HERE / "reps_out" / "images"   # 代表地点のオーバーレイ画像
K = 6
SEED = 42


def embed_image(lat: float, lon: float, size: int = 420) -> str | None:
    """代表地点のオーバーレイ PNG を縮小して data URI に。無ければ None。"""
    p = IMG_DIR / f"{lat:.4f}_{lon:.4f}.png"
    if not p.exists():
        return None
    im = Image.open(p).convert("RGB")
    im.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

FEAT = ["density", "lacunarity_mean", "lacunarity_slope", "r_crit",
        "mfa_alpha_width", "W_trans", "gamma", "Delta_D", "S_alpha"]
LABEL = {"density": "d 密度", "lacunarity_mean": "Λ̄ 空隙むら",
         "lacunarity_slope": "s_Λ 減衰", "r_crit": "r_crit 臨界距離",
         "mfa_alpha_width": "Δα MFA幅", "W_trans": "W_trans 転移幅",
         "gamma": "γ 臨界勾配", "Delta_D": "ΔD 次元ギャップ", "S_alpha": "S_α 歪度"}
SHORT = {"density": "d", "lacunarity_mean": "Λ̄", "lacunarity_slope": "s_Λ",
         "r_crit": "r_crit", "mfa_alpha_width": "Δα", "W_trans": "W_trans",
         "gamma": "γ", "Delta_D": "ΔD", "S_alpha": "S_α"}

# dataviz 参照パレット（categorical, light）
PALETTE = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948"]
C_TEXT, C_MUTED, C_GRID = "#0b0b0b", "#52514e", "#d8d8d4"

# z-score プロファイルからの日本語ラベル生成ルール（高=+0.7σ超, 低=-0.7σ未満）
HIGH = {
    "density": "高密", "lacunarity_mean": "空隙が不均質（むらが大きい）",
    "lacunarity_slope": "スケール減衰が急", "r_crit": "連結に長距離を要する（分断的）",
    "mfa_alpha_width": "多重フラクタル性が強い（複雑）", "W_trans": "連結が緩やかに進む（漸進的）",
    "gamma": "連結が急峻に立ち上がる（相転移的）", "Delta_D": "質量が集中（核的）",
    "S_alpha": "スペクトルの偏りが強い",
}
LOW = {
    "density": "低密（疎）", "lacunarity_mean": "空隙が均質",
    "lacunarity_slope": "スケール減衰が緩", "r_crit": "近距離で連結（密結合）",
    "mfa_alpha_width": "構造が単純（単一スケール的）", "W_trans": "連結が急峻（狭い転移）",
    "gamma": "連結がマイルド（緩慢）", "Delta_D": "質量が均等に分布",
    "S_alpha": "スペクトルが対称的",
}


# 代表画像を実際に見て洗練した日本語類型名・解説（rank をキーに機械ドラフトを上書き）。
DESCRIPTIONS: dict[int, dict] = {
    1: {"name": "街道集落型（疎・線形連結）",
        "body": "幹線道路に沿って建物が線状に張り付き、道路から離れた背後は"
                "広大な空地となる。密度は低い（d≈0.006）が、連結は一本の街道が"
                "担うため転移は標準的。世界の疎居住で最も多い基本形（最大クラスタ）。"},
    2: {"name": "分岐集村型（中密・急峻連結）",
        "body": "枝分かれする在来道路網に建物が付随し、ある距離スケールで一気に"
                "全体がつながる（γ が +0.8σ と急峻）。中密度ながら連結の立ち上がりが"
                "鋭い、相転移的な集村。"},
    3: {"name": "凝集開拓型（中密・漸進連結）",
        "body": "建物が一角に塊で凝集し、そこから道路が放射・分岐する。連結が広い"
                "距離範囲にわたって緩やかに進む（W_trans が +1.8σ と際立って大きい）。"
                "開拓前線や緩斜面の集村に多い。"},
    4: {"name": "稠密市街型（高密・密連結）",
        "body": "密な街路網に建物がびっしり詰まった有機的な市街地（d≈0.062 と"
                "本カタログ最高密）。近距離で全体が連結する、いわゆる「街」。"},
    5: {"name": "山間散村型（疎・漸進連結）",
        "body": "建物がごく小さな塊で点在し、間を長い道路が縫う。極めて疎（d≈0.005）で"
                "建物間距離が大きく、連結は緩慢。山間・内陸の孤立集落。"},
    6: {"name": "通過地・準無人型（極疎）",
        "body": "建物がほとんど無く（d≈0）、道路網だけが広大な空地を貫く。峠道や"
                "通過地の切り出しに相当する外れ値的タイプ（最小クラスタ）。"},
}


def radar(profile: dict, color: str) -> str:
    """9指標 z-score プロファイルのレーダーチャート → data URI（PNG）。"""
    feats = FEAT
    vals = [profile[f] for f in feats]
    ang = np.linspace(0, 2 * np.pi, len(feats), endpoint=False)
    ang = np.concatenate([ang, ang[:1]])
    vals = vals + vals[:1]
    fig, ax = plt.subplots(figsize=(3.4, 3.4), subplot_kw=dict(polar=True), dpi=110)
    ax.set_ylim(-2, 2)
    ax.plot(ang, vals, color=color, linewidth=2)
    ax.fill(ang, vals, color=color, alpha=0.2)
    ax.axhline(0, color=C_MUTED, linewidth=0.6)  # z=0 基準円は set_rgrids で
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
    """全地点を PCA 2次元に射影し、クラスタ色で散布図 → data URI。"""
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
    """z-score プロファイル → (類型名ドラフト, 日本語解説)。

    突出軸（|z|>0.7）を形態的意味に翻訳した機械ドラフト。
    最終的な類型名は代表画像を見て人手/VLM で洗練する前提。
    """
    highs = [f for f in FEAT if profile[f] > 0.7]
    lows = [f for f in FEAT if profile[f] < -0.7]
    phrases = [HIGH[f] for f in highs] + [LOW[f] for f in lows]
    # 密度水準を類型名の頭に
    d = profile["density"]
    dens_word = "高密" if d > 0.7 else ("疎" if d < -0.4 else "中密")
    # 連結ダイナミクスの性格
    if profile["gamma"] > 0.5:
        conn = "急峻連結型"
    elif profile["W_trans"] > 0.5:
        conn = "漸進連結型"
    elif profile["r_crit"] > 0.5:
        conn = "分断型"
    else:
        conn = "標準連結型"
    name = f"{dens_word}・{conn}"
    if not phrases:
        body = "9指標すべてが平均付近に収まる、際立った偏りのない標準的な形態。"
    else:
        body = "、".join(phrases) + "、という特徴を持つ形態タイプ。"
    return name, body


def main():
    df = pd.read_csv(VECS)
    df = df[df.density > 1e-5].reset_index(drop=True)
    X = df[FEAT].to_numpy(float)
    scaler = StandardScaler().fit(X)
    Xz = scaler.transform(X)
    km = KMeans(n_clusters=K, random_state=SEED, n_init=10).fit(Xz)
    df["cluster"] = km.labels_

    df.to_csv(HERE / "catalog_assignments.csv", index=False)

    # クラスタをサイズ降順に並べ替え
    order = df["cluster"].value_counts().index.tolist()

    names = {}
    cards = []
    for rank, cid in enumerate(order, 1):
        sub = df[df.cluster == cid]
        prof = {f: float(scaler.transform(sub[FEAT].mean().to_frame().T)[0][i])
                for i, f in enumerate(FEAT)}
        # 代表地点: クラスタ中心（z空間）に最も近い5地点
        center = km.cluster_centers_[cid]
        dist = np.linalg.norm(scaler.transform(sub[FEAT].to_numpy(float)) - center, axis=1)
        reps = sub.iloc[np.argsort(dist)[:5]]
        # 日本語類型名・解説: 代表画像を見て洗練した手書き版があれば優先、なければ機械ドラフト
        if rank in DESCRIPTIONS:
            name, body = DESCRIPTIONS[rank]["name"], DESCRIPTIONS[rank]["body"]
        else:
            name, body = describe(prof)
        names[cid] = name
        regions = sub["subregion"].value_counts().head(3)
        color = PALETTE[rank - 1]
        # 代表画像（中心最近傍の先頭3地点）
        gallery = "".join(
            f'<figure><img src="{uri}"><figcaption>{r["lat"]:.3f}, {r["lon"]:.3f}</figcaption></figure>'
            for _, r in reps.head(3).iterrows()
            if (uri := embed_image(r["lat"], r["lon"]))
        )

        rep_rows = "".join(
            f"<tr><td>{r['lat']:.3f}, {r['lon']:.3f}</td>"
            f"<td>{r['subregion']}</td>"
            f"<td>{r['density']:.4f}</td><td>{r['lacunarity_mean']:.1f}</td>"
            f"<td>{r['lacunarity_slope']:.3f}</td><td>{r['r_crit']:.0f}</td>"
            f"<td>{r['mfa_alpha_width']:.3f}</td><td>{r['W_trans']:.0f}</td>"
            f"<td>{r['gamma']:.4f}</td><td>{r['Delta_D']:.3f}</td>"
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
            <div>
              <h2>{name}</h2>
              <div class="meta">{len(sub):,} 地点（全体の {len(sub)/len(df)*100:.1f}%）</div>
            </div>
          </div>
          <div class="card-body">
            <img class="radar" src="{radar(prof, color)}" alt="radar">
            <div class="desc">
              <p>{body}</p>
              <div class="badges">{badges}</div>
              <div class="regions"><b>主な地域:</b> {reg_txt}</div>
            </div>
          </div>
          <div class="gallery">{gallery}</div>
          <div class="table-wrap"><table class="reps">
            <thead><tr><th>lat, lon</th><th>地域</th>
              <th>d</th><th>Λ̄</th><th>s_Λ</th><th>r_crit</th><th>Δα</th>
              <th>W_trans</th><th>γ</th><th>ΔD</th><th>S_α</th></tr></thead>
            <tbody>{rep_rows}</tbody>
          </table></div>
        </section>""")

    html = f"""<div class="wrap">
      <header>
        <h1>都市形態カタログ（OS指標・試作）</h1>
        <p class="sub">global_v2 全球サンプル {len(df):,} 地点を 9 次元 Open-Sparsity 指標で
        教師なしクラスタリング（KMeans, k={K}）。各タイプの指標プロファイルを
        レーダーで、突出軸をバッジで示す。類型名・解説は各タイプの代表画像を
        確認して記述した。</p>
      </header>
      <div class="overview">
        <img src="{scatter_pca(Xz, km.labels_.astype(int), order, names)}" alt="PCA散布図">
      </div>
      {"".join(cards)}
      <footer>OS指標 = [d 密度, Λ̄ 空隙むら, s_Λ 減衰, r_crit 臨界距離,
      Δα MFA幅, W_trans 転移幅, γ 臨界勾配, ΔD 次元ギャップ, S_α 歪度]。
      レーダーは各指標の z-score（全体平均=0, ±1σ 目盛）。代表地点表の値は生の実測値。</footer>
    </div>
    <style>
      .wrap {{ max-width: 1000px; margin: 0 auto; font-family: system-ui, sans-serif;
              color: {C_TEXT}; line-height: 1.6; }}
      header h1 {{ margin-bottom: 4px; }}
      .sub {{ color: {C_MUTED}; font-size: 14px; }}
      .card {{ border: 1px solid {C_GRID}; border-radius: 10px; margin: 18px 0;
               overflow: hidden; }}
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
      .overview img {{ width: 100%; max-width: 780px; display: block; margin: 8px auto 4px; }}
      .table-wrap {{ overflow-x: auto; }}
      table.reps {{ width: 100%; border-collapse: collapse; font-size: 12.5px;
                    white-space: nowrap; font-variant-numeric: tabular-nums; }}
      table.reps th, table.reps td {{ text-align: left; padding: 6px 16px;
                                       border-top: 1px solid {C_GRID}; }}
      table.reps th {{ color: {C_MUTED}; font-weight: 600; }}
      footer {{ color: {C_MUTED}; font-size: 12px; margin-top: 24px; }}
      @media (prefers-color-scheme: dark) {{
        .wrap {{ color: #eee; }} .card-head {{ background: #1e1e1c; }}
        .card {{ border-color: #333; }} table.reps th, table.reps td {{ border-color:#333; }}
      }}
    </style>"""
    (HERE / "catalog.html").write_text(html, encoding="utf-8")
    print(f"カタログ生成: {HERE/'catalog.html'} ({K} タイプ, {len(df):,} 地点)")
    for rank, cid in enumerate(order, 1):
        sub = df[df.cluster == cid]
        prof = {f: float(scaler.transform(sub[FEAT].mean().to_frame().T)[0][i])
                for i, f in enumerate(FEAT)}
        name, _ = describe(prof)
        print(f"  {rank}. {name}: {len(sub):,}地点 "
              f"(d={sub.density.mean():.4f} γz={prof['gamma']:+.1f} "
              f"W_trans z={prof['W_trans']:+.1f})")


if __name__ == "__main__":
    main()
