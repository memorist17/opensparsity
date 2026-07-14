# Baseline指標サーベイ（deep research, 2026-07-15）

目的: OSの「疎空間での分別能力」を主張するための、**同じ入力（建物footprint＋道路網、
2km窓）で計算できる既存baseline指標**の候補を、実装ポインタ付きで確定する。
評価軸は「低密度域での分別保持」。21ソース→93主張→25を3票検証（24確定/1却下）。

⚠️ 検証注意: サブエージェント1つがcurlでdeny規則を回避（該当は分割票2-1の
「従来指標が都市/農村境界で失敗する」系の主張＝下記でも中信頼度扱い）。

---

## ショートリスト（4ファミリー）

### Family 1 — 古典的密度・形態計量（査読者が必ず期待する基準）

- **momepy**（Fleischmann 2019, JOSS doi:10.21105/joss.01807）＋
  **numerical taxonomy of urban form**（Fleischmann et al. 2022, EPB
  doi:10.1177/23998083211059835）。**信頼度: 高（査読済み＋コード再現確認）**
  - 定義: 建物footprint＋街路網から、6カテゴリ（dimension/shape/spatial
    distribution/intensity/connectivity/diversity）の形態character群を、
    **morphological tessellation（Voronoiをplot代理に）**経由で算出。**第3の入力不要
    ＝OSの入力と一致**。
  - コード: conda/pip、`environment.yaml`＋`morphometric_assessment.ipynb`＋
    figshareデータ（doi:10.6084/m9.figshare.16897102）。repo:
    github.com/martinfleis/numerical-taxonomy-paper
  - **使い方の注意**: taxonomyの**クラスラベルはPrague/Amsterdamで較正**されているので、
    移植するのは分類ラベルでなく**characterの計算パイプライン**。OSの点群で走らせて
    character群を得る。
- **Spacematrix**（Berghauser Pont & Haupt）: FSI・GSI・N（街路密度）と派生
  OSR=(1-GSI)/FSI、L=FSI/GSI、w。**信頼度: 中**
  - ⚠️ **却下事項（0-3）**: FSI/GSI/N/OSRの「一行定義」の引用文言は検証で落ちた。
    式の実質は正しいが、**式は二次資料の言い換えでなくSpacematrix原典を引くこと**。
  - **入力適合の注意**: **FSIは階数/高さが必要でOvertureのfootprintでは不足しうる**。
    GSI・N・OSR(GSI由来)はfootprint＋網だけで計算可。

### Family 2 — 空間点パターン統計（建物＝点、最も直に走る）

- **PySAL `pointpats`**（pysal.org/pointpats）。**信頼度: 高（実行して再現確認）**
  - 定義/API: `f, g, k, l`（Ripleyの空隙F・最近傍G・K・線形化L）＋`g_test, k_test`
    （CSRエンベロープ）を、**(n,2)座標配列から一行で**。footprint重心にそのまま適用可。
  - 解釈規則: CSR下で K(d)~πd²、L(d)~0。**L>0=集積、L<0=規則/抑制**。
  - 現行版の注意: 返り値フィールドは`values`でなく`statistic`、`PointPattern`クラスは任意
    （座標配列だけで足りる）。
  - **Clark-Evans / 最近傍指数(NNI)**がこの family の古典的分散baseline
    （疎居住の分散/集積の一次指標）。

### Family 3 — パーコレーション/ネットワーク系（直接の競合）

- **Arcaute et al. 2016**（R. Soc. Open Sci. 3:150691, doi:10.1098/rsos.150691）。
  **信頼度: 高（査読・基礎文献）**。**これが正典の直接競合**。
  - 定義: 街路交差点を閾値dで単連結クラスタリング（「各点がd以内に隣接点を持つ」）、
    dを掃引してクラスタ階層を作り、**クラスタのfractal次元が最大になるdをr_critに採る**
    （交差点180m/網300m）。そのr_critのクラスタが**Corine衛星都市域と一致**
    ＝外部真値による検証プロトコル付き。道路網/交差点点群だけで計算可。
  - ⚠️ **OSは既にr_critをOS指標として計算している**。よって正直な位置づけは
    「percolation文献は転移の**位置**r_critで止まる／OSは転移の**かたち**
    W_trans・γを足す」（＝storyline案1そのもの）。
- **Settlement percolation: global maps of Critical Distances**
  （arXiv:2603.04439, 2026）。**信頼度: 高（内容）／ただし下記の可用性注意**。
  **最も的中した競合**。
  - 定義: 点を成長閾値でクラスタリングし、**2〜4番目に大きいクラスタの平均面積が
    最も急に落ちる閾値をl_c（Critical Distance）**とする。2km窓で計算可。
  - ⚠️ **コード可用性は未確認**: Docker/Python/PostGISツールと言及があるが公開URLなし、
    repoは査読用privateリンクで「出版後公開」。**今は走らせられない → アルゴリズムは
    単純なので再実装が現実的**。

### Family 4 — 疎居住・スプロール特化

- **Urban Sprawl (WUP)**（Behnisch/Krüger/Jaeger 2022）、**Urban Dispersion (DIS)**、
  **density-allocation / "beyond average density"**（Land Use Policy,
  sciencedirect S026483772100555X）。**信頼度: 中**
  - ⚠️ これらは競合paper(2603.04439)で**比較変数として名前が出るだけ**。
    **正確な計算式と実装は原典（Behnisch/Krüger/Jaeger 2022, WUP方法論）に当たる必要**
    （今回の検証では式・コードまで固められていない）。

---

## 🎯 crux証拠（「低密度で密度系baselineが崩れる」の引用）

**arXiv:2603.04439 が唯一、定量的な直接証拠を出している**（信頼度: 高だが下記caveat）:
Critical Distance と各baselineの相関が低密度域で崩壊——

| baseline | vs Critical Distance の R² |
|---|---|
| settlement-area share（≒密度） | **0.031** |
| Urban Sprawl WUP | 0.025 |
| Urban Dispersion DIS | 0.05 |
| Human Footprint Index | 0.094 |

「**built-up <2% の地点が Critical Distance の全域と共起する＝依存性なし**」。
これは「密度も sprawl/dispersion 系も低密度で構成を分別できない／configuration指標だけが
できる」という、あなたが欲しかった証拠そのもの。

⚠️ **正直なcaveat（重要）**: この crux は**思ったより薄い**。
- 上記R²は**非査読プレプリント**で、log軸2Dヒストからの自己申告値。
- Arcaute系の「従来morphometricsが失敗する」主張2件は**分割票(2-1)**で、しかも
  内容は「都市/農村**境界の非明瞭さ**」「core-periphery構造」であって
  「疎な**形態同士**の分別崩壊」とは微妙にズレる（かつ片方はcurl違反claim）。
- **結論**: 一般のmorphometric family全体が「低密度で崩れる」というクリーンな引用は
  文献から出てこない。→ **これはあなたが16,474点で自分で実証すべき**（むしろ
  その方が論文として強い。既存exp05のLOFOが土台）。

---

## 反straw-man: 最小防御ライン（査読者が要求する基準セット）

1. 密度 **GSI**（保有済み）
2. momepy character 部分集合（dimension/shape/spatial distribution）
3. 点パターン **Clark-Evans/NNI ＋ Ripley's L**（pointpats）
4. パーコレーション **r_crit**（Arcaute式、保有済み）
5. スプロール/分散 1本（**WUP** または **DIS**）

この5系に対しOSが低密度域で分別を保つと示せれば「straw-man」批判を封じられる。

## 評価プロトコルの先行例

- **外部真値との一致**: Arcaute 2016 = Corine都市域。
- **独立性R²**: percolation 2026 = 外部指標に対する R²。
- **設定タイプ分類**: Jochem et al. 2021（EPB doi:10.1177/2399808320921208,
  建物footprintのmulti-scale patternで設定タイプ分類）＝**農村/疎の分別の最も近い先行例**。
- **外部ラベル**: DEGURBA（Copernicus）。
- ⚠️ **DEGURBA復元やsilhouetteでの明示的benchmarkは文献に無い**（open question）
  ＝OSで新規に定義する余地。ただしOvertureカバレッジバイアス（未記載>20%層）を
  先に処理しないと汚染される。

## 次の一手（exp06案）

同じ16,474点で上記5系baselineを計算（momepy characters＋pointpats Clark-Evans/L）し、
exp05と同じLOFO/分別評価を**疎層に限定**、DEGURBA復元を外部ラベルにして
OSと横並び比較。**前提: Overtureバイアス感度（未記載>20%層の除外再現）を先に済ませる**。

## 主要ソース（検証済み）

- momepy: doi:10.21105/joss.01807
- numerical taxonomy: doi:10.1177/23998083211059835 / repo martinfleis/numerical-taxonomy-paper / figshare 10.6084/m9.figshare.16897102
- Spacematrix: Berghauser Pont & Haupt（原典を引く）
- pointpats: pysal.org/pointpats
- Arcaute 2016: doi:10.1098/rsos.150691
- Settlement percolation global Critical Distances: arXiv:2603.04439（コード未公開）
- megaregions percolation: doi:10.1007/s43762-024-00140-2 / arXiv:2408.09054
- peri-urban dislocation: arXiv:2606.12399
- Jochem et al. 2021（設定タイプ分類）: doi:10.1177/2399808320921208
- beyond average density: sciencedirect S026483772100555X
