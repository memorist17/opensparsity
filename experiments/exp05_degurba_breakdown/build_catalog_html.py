#!/usr/bin/env python
"""クラスタリング結果のHTMLカタログ生成（Artifact公開用、自己完結）。

- マクロ3分類（K=3、シルエット0.60）: バルク88% / 超疎斑点形態 / 長距離転移形態
- バルク内部のK=6サブ類型
- PCA散布図はSVGで直接描画（2,000点に間引き）、代表画像はdata URI埋め込み
"""
import base64
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
FEATURES = ["density", "lacunarity_mean", "lacunarity_slope", "r_crit",
            "mfa_alpha_width", "W_trans", "gamma", "Delta_D", "S_alpha"]
FLABEL = {"density": "d", "lacunarity_mean": "Λ̄", "lacunarity_slope": "s_Λ",
          "r_crit": "r_crit", "mfa_alpha_width": "Δα", "W_trans": "W_trans",
          "gamma": "γ", "Delta_D": "ΔD", "S_alpha": "S_α"}

main = json.loads((HERE / "cluster_summary.json").read_text())
sub = json.loads((HERE / "subcluster_summary.json").read_text())
df = pd.read_csv(HERE / "cluster_result.csv")

# dataviz参照パレット（categorical、light/dark）
PAL_L = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948"]
PAL_D = ["#3987e5", "#199e70", "#c98500", "#008300", "#9085e9", "#e66767"]
MACRO_L = {1: "#e34948", 2: "#4a3aa7"}
MACRO_D = {1: "#e66767", 2: "#9085e9"}

def img_uri(lat, lon):
    p = HERE / "rep_images" / "thumb" / f"{lat:.4f}_{lon:.4f}.png"
    if not p.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()

# --- 散布図SVG（PCA / t-SNE / UMAP、サブクラスタ色分け・外れ群は正方形） ---
rng = np.random.default_rng(42)
bulk = df[df["cluster"] == 0]
keep = bulk.iloc[rng.choice(len(bulk), 3000, replace=False)]
outl = df[df["cluster"] != 0]
plot_df = pd.concat([keep, outl])
W, H, PAD = 640, 480, 36

def scatter_svg_for(xc, yc, xlabel, ylabel, title):
    x0, x1 = plot_df[xc].quantile([0.001, 0.999])
    y0, y1 = plot_df[yc].quantile([0.001, 0.999])
    def sx(v): return PAD + (v - x0) / (x1 - x0) * (W - 2 * PAD)
    def sy(v): return H - PAD - (v - y0) / (y1 - y0) * (H - 2 * PAD)
    pts = []
    for _, r in keep.iterrows():
        if not (x0 <= r[xc] <= x1 and y0 <= r[yc] <= y1):
            continue
        pts.append(f'<circle cx="{sx(r[xc]):.1f}" cy="{sy(r[yc]):.1f}" r="2.2" '
                   f'class="p s{int(r["subcluster"])}" opacity="0.55"/>')
    for _, r in outl.iterrows():
        if not (x0 <= r[xc] <= x1 and y0 <= r[yc] <= y1):
            continue
        pts.append(f'<rect x="{sx(r[xc])-2.6:.1f}" y="{sy(r[yc])-2.6:.1f}" '
                   f'width="5.2" height="5.2" class="p m{int(r["cluster"])}" opacity="0.85"/>')
    return f'''<svg viewBox="0 0 {W} {H}" role="img" aria-label="{title}">
<line x1="{PAD}" y1="{H-PAD}" x2="{W-PAD}" y2="{H-PAD}" class="axis"/>
<line x1="{PAD}" y1="{PAD}" x2="{PAD}" y2="{H-PAD}" class="axis"/>
<text x="{W/2}" y="{H-8}" class="axlabel" text-anchor="middle">{xlabel}</text>
<text x="12" y="{H/2}" class="axlabel" text-anchor="middle" transform="rotate(-90 12 {H/2})">{ylabel}</text>
{"".join(pts)}
</svg>'''

ev = main["pca_variance"]
has_embed = "tsne1" in df.columns
tabs = [("pca", "PCA",
         scatter_svg_for("pc1", "pc2", f"PC1 ({ev[0]:.0%} var) — 疎密と転移の鋭さ",
                         f"PC2 ({ev[1]:.0%} var) — 転移の長距離性", "PCA projection"),
         f"線形射影・分散カバー{ev[0]+ev[1]:.0%}。PC1はγ・s_Λ(+)/Δα・d(−)、"
         "PC2はW_trans・S_α・r_crit(+)が主成分")]
if has_embed:
    tabs.append(("tsne", "t-SNE",
                 scatter_svg_for("tsne1", "tsne2", "t-SNE 1", "t-SNE 2", "t-SNE embedding"),
                 "非線形・局所近傍保存（perplexity=50、PCA初期化）。"
                 "軸自体に意味はなく、近さだけを読む"))
    tabs.append(("umap", "UMAP",
                 scatter_svg_for("umap1", "umap2", "UMAP 1", "UMAP 2", "UMAP embedding"),
                 "非線形・局所+大域バランス（n_neighbors=30, min_dist=0.1）。"
                 "軸自体に意味はなく、近さと分離だけを読む"))

tab_radios = "".join(
    f'<input type="radio" name="proj" id="tab-{k}" {"checked" if i==0 else ""}/>'
    for i, (k, *_ ) in enumerate(tabs))
tab_labels = "".join(
    f'<label for="tab-{k}">{name}</label>' for k, name, *_ in tabs)
tab_panels = "".join(
    f'<div class="panel panel-{k}">{svg}<p class="projnote">{note}</p></div>'
    for k, name, svg, note in tabs)
tab_css = "\n".join(
    f'#tab-{k}:checked ~ .panels .panel-{k} {{ display:block; }}\n'
    f'#tab-{k}:checked ~ .tabbar label[for="tab-{k}"] '
    f'{{ color:var(--ink); border-color:var(--accent); }}'
    for k, *_ in tabs)
scatter_block = f'''<div class="projtabs">
{tab_radios}
<div class="tabbar">{tab_labels}</div>
<div class="panels">{tab_panels}</div>
</div>'''

# --- プロファイルバー（z-score横棒） ---
def profile_bars(pz, color_class):
    rows = []
    for f in FEATURES:
        v = pz[f]
        w = min(abs(v) / 3.5, 1.0) * 50
        side = "left:50%" if v >= 0 else f"left:{50-w}%"
        rows.append(
            f'<div class="prow"><span class="pf">{FLABEL[f]}</span>'
            f'<span class="ptrack"><span class="pbar {color_class}" '
            f'style="{side};width:{w}%"></span><span class="pzero"></span></span>'
            f'<span class="pv">{v:+.2f}</span></div>')
    return "".join(rows)

def rep_cards(reps, n=4):
    cards = []
    for r in reps[:n]:
        uri = img_uri(r["lat"], r["lon"])
        if uri is None:
            continue
        cards.append(
            f'<figure class="rep"><img src="{uri}" alt="overlay {r["country"]}" loading="lazy"/>'
            f'<figcaption>{r["country"]} · {r["subregion"]}<br>'
            f'<span class="mono">{r["lat"]:.3f}, {r["lon"]:.3f} · d={r["density"]:.4f}</span>'
            f'</figcaption></figure>')
    return "".join(cards)

def region_chips(top):
    return "".join(f'<span class="chip">{k} {v:.0%}</span>' for k, v in list(top.items())[:3])

SUB_NAMES = {
    0: "均質・低集中型", 1: "点集中型", 2: "微小疎+急転移型",
    3: "極疎・高集中型", 4: "相対稠密型", 5: "単調スケール型",
}
SUB_DESC = {
    0: "ΔD低・密度低め。塊を作らず均一にばらける、最も『特徴のない』疎地。北米・南米の平原に多い",
    1: "ΔD突出。少数の点に質量が集中し、周囲はほぼ空。孤立農家・小集落のパターン",
    2: "d≈0.0004。γ・s_Λ高い＝わずかな建物が急峻につながる。乾燥帯の縁に多い",
    3: "d≈0.0002で最も疎。集中度も勾配も高い＝ぽつんと一軒家の世界",
    4: "d≈0.018でバルク中最稠密。Δα高い＝スケール依存の複雑さを持つ、村落級の組織",
    5: "Δα極小＝どのスケールで見ても同じ単調な配置。特異な少数派（n=233）",
}
MACRO_NAMES = {1: "超疎斑点形態（外れ群）", 2: "長距離転移形態（外れ群）"}
MACRO_DESC = {
    1: "n=537。Λ̄がz=+4.6と極端: ほぼ空のキャンバスに極小の斑点。d中央値0.00001",
    2: "n=150。W_trans/r_critがz=+8〜9: 連結が350m超の長距離でだらだら進む。"
       "Eastern Africa 60%・豪州24%に集中——広域散居のシグネチャ",
}

macro_cards = []
for c in main["clusters"]:
    if c["id"] == 0:
        continue
    i = c["id"]
    macro_cards.append(f'''
<article class="cluster outlier">
<header><span class="badge m{i}">outlier</span>
<h3>{MACRO_NAMES[i]}</h3>
<p class="meta">n={c["n"]:,} · 面積加重シェア {c["weight_share"]:.1%}</p></header>
<p class="desc">{MACRO_DESC[i]}</p>
<div class="chips">{region_chips(c["top_subregions"])}</div>
<div class="profile">{profile_bars(c["profile_z"], f"m{i}")}</div>
<div class="reps">{rep_cards(c["representatives"])}</div>
</article>''')

sub_cards = []
for c in sub["subclusters"]:
    i = c["id"]
    sub_cards.append(f'''
<article class="cluster">
<header><span class="badge s{i}">type {i+1}</span>
<h3>{SUB_NAMES[i]}</h3>
<p class="meta">n={c["n"]:,} · バルク内加重シェア {c["weight_share_of_bulk"]:.1%} ·
d中央値 {c["profile_median"]["density"]:.5f}</p></header>
<p class="desc">{SUB_DESC[i]}</p>
<div class="chips">{region_chips(c["top_subregions"])}</div>
<div class="profile">{profile_bars(c["profile_z"], f"s{i}")}</div>
<div class="reps">{rep_cards(c["representatives"])}</div>
</article>''')

sil = main["silhouette_by_k"]
sil_rows = "".join(
    f'<tr{" class=chosen" if int(k)==main["chosen_k"] else ""}>'
    f'<td>{k}</td><td>{v:.3f}</td></tr>' for k, v in sil.items())

pal_css_l = "\n".join(f".s{i}{{--c:{PAL_L[i]}}}" for i in range(6)) + \
    "\n" + "\n".join(f".m{i}{{--c:{MACRO_L[i]}}}" for i in MACRO_L)
pal_css_d = "\n".join(f".s{i}{{--c:{PAL_D[i]}}}" for i in range(6)) + \
    "\n" + "\n".join(f".m{i}{{--c:{MACRO_D[i]}}}" for i in MACRO_D)

legend = "".join(
    f'<span class="lg s{i}"><span class="sw"></span>{SUB_NAMES[i]}</span>'
    for i in range(6)) + "".join(
    f'<span class="lg m{i}"><span class="sw sq"></span>{MACRO_NAMES[i]}</span>'
    for i in MACRO_L)

html = f'''<title>疎居住形態カタログ — DEGURBA全球サンプル16,474点</title>
<style>
:root {{
  --bg:#fbfbf9; --ink:#1c1b18; --ink2:#5b594f; --line:#e4e2d8;
  --card:#ffffff; --accent:#2a78d6; --mono:ui-monospace,Menlo,monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#191916; --ink:#f2f1ea; --ink2:#b6b4a6; --line:#33322c;
           --card:#211f1c; --accent:#3987e5; }}
}}
:root[data-theme="dark"] {{ --bg:#191916; --ink:#f2f1ea; --ink2:#b6b4a6;
  --line:#33322c; --card:#211f1c; --accent:#3987e5; }}
:root[data-theme="light"] {{ --bg:#fbfbf9; --ink:#1c1b18; --ink2:#5b594f;
  --line:#e4e2d8; --card:#ffffff; --accent:#2a78d6; }}
{pal_css_l}
@media (prefers-color-scheme: dark) {{ {pal_css_d} }}
:root[data-theme="dark"] {pal_css_d.replace(chr(10), " ").replace(".s", " .s").replace(".m", " .m")}
body {{ background:var(--bg); color:var(--ink);
  font:16px/1.75 "Hiragino Sans","Noto Sans JP",sans-serif;
  margin:0; padding:2.5rem 1.2rem 5rem; }}
main {{ max-width:1080px; margin:0 auto; }}
h1 {{ font-size:1.7rem; line-height:1.4; letter-spacing:.01em; margin:0 0 .3rem;
  text-wrap:balance; }}
.sub {{ color:var(--ink2); margin:0 0 2.2rem; max-width:46rem; }}
h2 {{ font-size:1.15rem; margin:3rem 0 .8rem; padding-top:1.4rem;
  border-top:1px solid var(--line); }}
.lead {{ color:var(--ink2); max-width:46rem; margin:.2rem 0 1.4rem; }}
.grid2 {{ display:grid; grid-template-columns:1fr auto; gap:2rem; align-items:start; }}
@media (max-width:820px) {{ .grid2 {{ grid-template-columns:1fr; }} }}
svg {{ width:100%; height:auto; }}
.axis {{ stroke:var(--line); stroke-width:1; }}
.axlabel {{ fill:var(--ink2); font-size:12px; }}
.p {{ fill:var(--c,#888); }}
table {{ border-collapse:collapse; font-variant-numeric:tabular-nums; }}
td,th {{ padding:.25rem .9rem; border-bottom:1px solid var(--line);
  text-align:right; font-size:.9rem; }}
tr.chosen td {{ font-weight:700; color:var(--accent); }}
.legend {{ display:flex; flex-wrap:wrap; gap:.4rem 1.1rem; margin:.8rem 0 0;
  font-size:.82rem; color:var(--ink2); }}
.lg {{ display:inline-flex; align-items:center; gap:.4rem; }}
.sw {{ width:11px; height:11px; border-radius:50%; background:var(--c); }}
.sw.sq {{ border-radius:2px; }}
.catalog {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(480px,1fr));
  gap:1.2rem; }}
@media (max-width:560px) {{ .catalog {{ grid-template-columns:1fr; }} }}
.cluster {{ background:var(--card); border:1px solid var(--line);
  border-radius:6px; padding:1.2rem 1.3rem 1.1rem; }}
.cluster.outlier {{ border-style:dashed; }}
.badge {{ display:inline-block; font-size:.72rem; letter-spacing:.08em;
  text-transform:uppercase; color:#fff; background:var(--c);
  padding:.1rem .55rem; border-radius:3px; }}
h3 {{ margin:.5rem 0 .1rem; font-size:1.05rem; }}
.meta {{ color:var(--ink2); font-size:.82rem; margin:0 0 .5rem;
  font-variant-numeric:tabular-nums; }}
.desc {{ font-size:.9rem; margin:.2rem 0 .7rem; }}
.chips {{ display:flex; flex-wrap:wrap; gap:.35rem; margin-bottom:.9rem; }}
.chip {{ font-size:.75rem; background:var(--bg); border:1px solid var(--line);
  padding:.08rem .5rem; border-radius:99px; color:var(--ink2); }}
.profile {{ margin-bottom:1rem; }}
.prow {{ display:flex; align-items:center; gap:.6rem; font-size:.78rem;
  line-height:1.45; }}
.pf {{ width:3.4rem; text-align:right; color:var(--ink2);
  font-family:var(--mono); }}
.ptrack {{ position:relative; flex:1; height:9px; background:var(--bg);
  border-radius:2px; overflow:hidden; }}
.pbar {{ position:absolute; top:0; height:100%; background:var(--c);
  border-radius:1px; }}
.pzero {{ position:absolute; left:50%; top:0; width:1px; height:100%;
  background:var(--line); }}
.pv {{ width:3.2rem; font-family:var(--mono); font-size:.74rem;
  color:var(--ink2); }}
.reps {{ display:grid; grid-template-columns:repeat(4,1fr); gap:.5rem; }}
@media (max-width:560px) {{ .reps {{ grid-template-columns:repeat(2,1fr); }} }}
.rep {{ margin:0; }}
.rep img {{ width:100%; aspect-ratio:1; object-fit:cover; border-radius:4px;
  border:1px solid var(--line); display:block; }}
.rep figcaption {{ font-size:.68rem; color:var(--ink2); line-height:1.5;
  margin-top:.25rem; }}
.mono {{ font-family:var(--mono); font-size:.64rem; }}
.note {{ font-size:.85rem; color:var(--ink2); border-left:3px solid var(--accent);
  padding:.2rem 0 .2rem 1rem; margin:1.2rem 0; max-width:46rem; }}
.projtabs input {{ position:absolute; opacity:0; pointer-events:none; }}
.tabbar {{ display:flex; gap:.2rem; margin-bottom:.6rem; }}
.tabbar label {{ font-size:.85rem; color:var(--ink2); padding:.25rem .9rem;
  border-bottom:2px solid transparent; cursor:pointer; }}
.tabbar label:hover {{ color:var(--ink); }}
.projtabs input:focus-visible ~ .tabbar label {{ outline:1px dotted var(--accent); }}
.panel {{ display:none; }}
.projnote {{ font-size:.78rem; color:var(--ink2); margin:.3rem 0 0; }}
{tab_css}
</style>
<main>
<h1>疎居住形態カタログ</h1>
<p class="sub">DEGURBA層化サンプル（全球 rural 27,710地点試行 → 指標取得 16,474地点）の
OS 9次元特徴空間クラスタリング。KMeans（design_weight加重・seed 42）。
1枚の画像 = 2km×2km の建物（赤）+ 道路（青）オーバーレイ。</p>

<h2>マクロ構造: K=3 が最良分割</h2>
<div class="grid2">
<div>
<p class="lead">シルエット係数はK=3で0.60と突出（他は0.27前後）。ただしその内実は
「バルク96% + 2つの外れ形態」——類型というより<strong>異常形態の検出</strong>。
散布図は9次元z-score空間の射影（バルクは3,000点に間引き、外れ群は正方形マーカー全点）。
PCAの分散カバーは64%に留まるため、非線形のt-SNE / UMAPも併置。</p>
{scatter_block}
<div class="legend">{legend}</div>
</div>
<table>
<thead><tr><th>K</th><th>silhouette</th></tr></thead>
<tbody>{sil_rows}</tbody>
</table>
</div>

<h2>外れ形態（2群、合計687点）</h2>
<p class="lead">全体の4%だが面積加重では12%——「異常」ではなく広大な領域を代表する少数派。</p>
<div class="catalog">{"".join(macro_cards)}</div>

<h2>バルク（15,787点）内部の6類型</h2>
<p class="lead">バルクをK=6でサブクラスタリング（exp03のK=6カタログと比較可能）。
プロファイルは全サンプル基準のz-scoreで、±3.5σでクリップ表示。</p>
<div class="catalog">{"".join(sub_cards)}</div>

<p class="note">方法メモ: 特徴は d, Λ̄, s_Λ, r_crit, Δα, W_trans, γ, ΔD, S_α の9次元
（z-score標準化）。クラスタ番号は面積加重シェア降順。代表点は各クラスタ重心への
ユークリッド距離最小の地点。design_weight はMollweide等積格子上のHorvitz-Thompson重み
（cos(lat)補正なし・2026-07-12修正版）。データ: Overture 2026-06-17 / GHS-SMOD E2025。</p>
</main>'''

out = HERE / "catalog_degurba.html"
out.write_text(html)
print(f"saved: {out} ({len(html)/1024:.0f} KB)")
