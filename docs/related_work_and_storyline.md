# 先行研究サーベイ & ストーリーテリング検討（2026-07-08）

対象: 岩田卒論「Open Sparsity」の**ネクストステップ論文**。
既存カタログ（`論文カタログ_岩田卒論_v8.csv`, 137本）を精査した上で、
カタログに欠けていて核心（低密度領域でのプロセス指標・道路網媒介パーコレーション）に
接続する系譜を Web 調査で補完した。

---

## 0. 手元カタログの評価

**強い（十分に押さえている）**:
- フラクタル都市形態（Batty & Longley, Frankhauser, Chen 系）
- ラキュナリティ（Allain-Cloitre, Plotnick, Dong, 最新の LACUNAE 2025 / gliding-box 高速化 2024 まで）
- マルチフラクタル（Halsey, Chhabra-Jensen, Ariza-Villaverde, Rényi spectra 2020, cascade 2021）
- パーコレーション×都市（Arcaute 2016, Cao/Li 2016 clusters, Makse 成長, Stauffer 教科書）
- 生物ネットワーク・人工生命（アリの巣、葉脈、Physarum、Lenia）＝谷研の文脈
- 密度の限界（Angel anatomy of density, Moroni, Jacobs）

**薄い（ネクストステップで補うべき3つの空白）**:
1. **同一密度・異形態の「建築／都市デザイン系」系譜** — 序論の主張
   「密度が同じでも形態が違う」を、Batty のフラクタル系だけでなく
   設計理論側の正統（Spacemate）に接続できていない
2. **転移の"かたち"（幅・鋭さ・勾配）を記述子に使う物理系譜** — あなたの
   独自性 W_trans / γ の直接の理論的裏付け（gradient percolation, percolation front）
3. **2026 年の直接競合** — パーコレーション×都市の全球/周縁研究が今年立て続けに
   出ており、ポジショニングを更新しないと新規性主張が弱くなる

**2026-07-12 追記**: 「転移の"かたち"(W_trans/γ的な量)で疎密度スペクトラム全体
(疎な集落も含む)の"状態"を識別する」という直接競合を探すターゲットサーベイを実施。
98エージェント・16一次資料の裏取りの結果、**直接競合は見つからず**（新規性の主張は
現時点で崩れていない）。ただし関連する周辺文献を複数発見（セクション B・D に追加、
詳細は末尾出典参照）。非英語文献（中国の農村集落研究、ラテンアメリカのインフォーマル
集落研究）や非インデックス学会（GISRUK, AAG, CSSSA）は未探索のため、投稿前の再調査を
推奨。

**2026-08-02 追記**: 「建物ノード×道路網媒介（最短路距離）」という OS の手法核心
そのものについて、既存文献が①建物/人口ノード×ユークリッド距離（Behnisch 2019, GSP
2026, Oliveira et al. 2018）と②道路交差点ノード×道路網（Arcaute 系）の2系統に
分かれ、**どちらも組み合わせていない**ことを個別に確認（詳細はセクション1-C-2）。
なぜこの組み合わせが手つかずだったかの構造的理由（動機の不一致／データ未整備／
計算コスト）も整理し、OS 自身の実装（`node_filter="building"` +
`distance_type="shortest_path"`）がこの空白を埋めるものであることをコードレベルで
確認した。

---

## 1. 追加すべき先行研究（グループ別・各々「なぜ引くか／どう差別化するか」つき）

### A. 同一密度・異形態の設計系譜（序論の補強）

- **Berghauser Pont & Haupt, *Spacemate / Spacematrix*（2004, 書籍2021）**
  FSI(容積)・GSI(建蔽)・OSR(空地圧)・L(層)・N(網密度) の多変数空間で
  「同一密度が全く異なる都市組織になる」ことを可視化した設計理論の到達点。
  → **引く理由**: あなたの「密度はスカラーに潰れる／同一 d で異形態」の主張は、
  Batty のフラクタル系だけでなくこの設計系の正統に載せると强い。
  → **差別化**: Spacemate は**静的な密度変数の空間**。OS は**プロセス指標
  （連結の転移ダイナミクス）**を軸に持つ点が本質的に新しい。
  「Spacemate が"どれだけ・どう建っているか"の空間なら、OS は
  "どうつながるか"の空間」と対比できる。

- **Caruso, Hilal & Thomas 2017, *Measuring urban forms from inter-building
  distances: MST + LISA*（Landscape and Urban Planning）**（カタログ欠）
  建物重心間距離の最小全域木＋局所空間統計。パラメータ最小・座標直接。
  → **引く理由**: 「建物間距離で低密度形態を測る」最も近い親戚。
  → **差別化**: 彼らはユークリッド距離の静的分布。OS は道路網媒介＋転移の
  動特性。**MST は今回の percolation 高速化で内部的に使っており**、
  手法的にも接続を語れる。

- **Fleischmann, Romice & Porta 2020, *Measuring urban form: overcoming
  terminological inconsistencies*（EPB）**（カタログは 2022 taxonomy のみ収録）
  361 指標を6カテゴリに分類し **spatial distribution と diversity が体系的に
  手薄**と明示、Index of Elements（Index×Element 命名）を提案。
  → **引く理由**: OS 指標群はまさにこの空白域。各 OS 指標を Index×Element で
  書き直せば分類系に正式接続でき、査読者の「用語が独自すぎる」批判を封じる。

### B. 転移の"かたち"を記述子にする物理系譜（独自性 W_trans/γ の裏付け）

- **Gradient percolation / percolation front（Sapoval 系, 応用は settlement へ）**
  占有確率が空間的に勾配を持つと臨界濃度付近に有限幅の「浸透前線」が生じ、
  その**幅は空間的不均質・相関構造に依存**する。
  → **引く理由**: 「W_trans（転移幅）が形態の相関構造を測る」という主張の
  物理的基礎。γ（臨界勾配）＝転移の鋭さ も同じ枠組みで正当化できる。
  → **位置づけ**: 物理では前線幅は"副産物"。OS は**それを形態記述子に昇格**
  させる点が貢献。

- **Stauffer & Aharony *Introduction to Percolation*（カタログ有）＋
  critical exponents の普遍性**
  転移の鋭さ・幅を臨界指数の言葉で語れる。
  → **引く理由**: γ, W_trans を「臨界現象の観測量」として理論言語に接地。
  ただし OS は無限系の普遍指数ではなく**有限 2km 窓での操作的観測量**である、
  と明示（over-claim 回避）。

- **A Review of Percolation-like Transitions in Cities and Landscapes
  （Findings, レビュー）**
  都市・景観のパーコレーション型転移の総説。
  → **引く理由**: 分野マップとして序論の位置づけに便利。

- **Kalisky & Cohen, *Width of percolation transition in complex networks*
  （Phys. Rev. E 73, 035101, 2006）**（2026-07-12 追加発見）
  複雑ネットワーク（非空間・scale-free等）における転移幅を理論的に定義した
  一次資料。W_trans が物理として独立に定義・研究されてきた量であることの直接的な
  理論的裏付けになる。
  → **引く理由**: Stauffer & Aharony の教科書的引用より具体的な一次論文として、
  「転移幅」概念そのものの先行研究に接地できる。
  → **要注意**: 具体的なスケーリング式（Δp_c ∝ p_c/N^(1/3) 等、ネットワーク型ごとの
  臨界指数）は本サーベイの裏取りで棄却された（0-3 / 1-2 で不確証）。引用する場合は
  式の中身ではなく「転移幅という量を扱った理論的先行研究がある」という事実関係のみに
  留め、具体的数式は一次資料を再確認してから引くこと。
  → **差別化**: 彼らは非空間ネットワークの無限系極限。OS は**建物-道路の空間ネット
  ワーク**を**有限 2km 窓**で扱う操作的観測量。

- **Raimbault, *Multi-dimensional Urban Network Percolation*（arXiv 1903.07141,
  2019）**（2026-07-12 追加発見）
  単次元（人口分布のみ）だった都市網パーコレーションを、urban form（人口分布）＋
  urban function（交通網特性）の多次元に拡張し、欧州都市システムの内生的地域区分に
  応用。
  → **引く理由**: 「パーコレーションを多次元指標に拡張する」という発想の直系の
  方法論的祖先。Arcaute 2026 と OS の中間に位置づけられる。
  → **差別化**: 転移の"かたち"（W_trans/γ）に相当する記述子はなく、疎・農村の
  識別も主眼ではない（地域区分が目的）。OS は形状記述子＋疎密度スペクトラム全体を
  明示的に扱う点で一歩先。

- **Zeng, Li, Guo, Gao, Gao, Stanley & Havlin, *Switch between critical
  percolation modes in city traffic dynamics*（PNAS 116(1):23-28, 2019;
  arXiv 1709.03134）**（2026-07-12 追加発見）
  同一の道路網トポロジーでも、時間帯（交通量）によってパーコレーションの普遍性
  クラスが切り替わる：オフピークは small-world/Erdős–Rényi 的（τ≈2.50）、
  ラッシュ時は 2 次元格子的（τ≈2.05）。
  → **引く理由**: 「"状態"がパーコレーションの普遍性クラスの切り替えとして現れる」
  という概念の説得力ある先例。序論で「パーコレーションで状態を語れる」ことの
  傍証に使える。
  → **差別化**: 対象は交通流動（動的トラフィック）であり静的な建物・道路形態では
  ない。疎・農村との比較もなし。

- **dos Santos & Ricardo, *Topological Percolation in Urban Dengue
  Transmission: A Multi-Scale Analysis of Spatial Connectivity*
  （arXiv 2601.09747, 2026-01, rev. 2026-02）**（2026-07-12 追加発見）
  デング熱の症例点群に percentile-parametrized Vietoris-Rips filtration ＋
  0次パーシステントホモロジーを適用し、「断片化〜完全パーコレーション」の
  幾何学的レジームを識別する枠組み。
  → **引く理由**: 発想（パーコレーション閾値で"状態/レジーム"を分類する）が
  OS に最も近い 2026 年の論文。ただし対象がデング熱の症例点群（レシフェの
  単一の稠密都市、疎住区の扱いなし）であり、建物・道路の集落形態とは無関係。
  → **位置づけ**: 「パーコレーションによる状態分類」という発想自体は他分野
  （疫学）で既に使われているが、**集落形態・疎密度スペクトラムに適用した例は
  見つからなかった**、という新規性の傍証として引ける。

### C. 【要警戒】2026 年の直接競合（ポジショニング更新が必須）

- **Arcaute et al. 2026, *Revealing Peri-Urban Dislocation through Percolation
  Analysis*（arXiv 2606.12399）** — Barrientos-Trinanes, Marshall, Arcaute
  道路網パーコレーションの階層クラスタリングで「周縁都市の構造的転位」を定義し、
  **density / land-use mix / fragmentation とは異なる構造次元**だと主張。
  Valdivia と Boston の対比。
  → **これは思想的に最も近い**（「密度では捉わらない構造次元をパーコレーションで」）。
  → **差別化の言い方**: 彼らは(1)**道路網のみ**でノードは交差点、(2)出力は
  **階層クラスタ／境界・地域構造**、(3)2 ケーススタディ。OS は(1)**建物ノードを
  道路網媒介で連結**、(2)出力は**転移ダイナミクス W_trans/γ の連続量**、
  (3)**全球 B1 センサス（進行中）で密度軸に沿った寄与曲線**。
  「彼らが *where the hierarchy breaks* を問うなら、OS は *how sharply it
  connects* を測る」。**先に出さないと新規性が削られるので、投稿を急ぐ論拠**。

- **Settlement percolation: global maps of Critical Distances
  （arXiv 2603.04439, 2026-03）**（前回発見）
  WSF から臨界距離 r_crit の全球マップ（GSP データセット）。
  → **差別化**: 彼らは r_crit（転移の**位置**）で止まる。OS は W_trans/γ
  （転移の**幅・鋭さ**）＝Exp01 で「全密度帯で一様基準以上の固有情報を持つ」
  と実証済みの量。**「位置の先の、かたち」**が一言のポジショニング。
  → **利用**: r_crit 全球マップは外部比較・検証データとして引用できる（競合かつ土台）。

- **Behnisch, Schorcht, Kriewald & Rybski, *Settlement percolation: A study of
  building connectivity and poles of inaccessibility*
  （Landscape and Urban Planning 191, 103631, 2019）**（2026-08-02 詳細確認・訂正）
  ドイツの建物重心点(地籍データ由来)に City Clustering Algorithm (CCA) の点データ版を
  適用。臨界距離 830±10m で国全体が単一クラスタに転移。
  → **重要**: **道路網は一切使用していない**。純粋な空間近接性(ユークリッド/測地
  バッファー距離)での接続判定。建物ノードだが道路網媒介ではない点に注意
  （旧記載「建物ノード・距離しきい値パーコレーションの手法的先例」は不正確だったため訂正）。

### C-2. 建物ノード×道路網媒介という組み合わせの新規性（2026-08-02 確認）

OS の手法核心（建物重心をノードとし、**道路網上の最短路距離**で接続性を判定する
パーコレーション）そのものが、先行研究のどちらの系統にも属さないことを個別に確認した。

**系統①: 建物/人口ノード ＋ ユークリッド/測地距離（道路網不使用）**
- Behnisch et al. 2019（上記）— ドイツ、建物重心、CCA、道路網不使用
- Settlement percolation: global maps of Critical Distances（arXiv 2603.04439,
  2026）— 上記の全球版。World Settlement Footprint 使用。論文内に明記:
  "The WSF does not include the road network"。距離は測地バッファー
- Oliveira, Furtado, Andrade Jr. & Makse, *A worldwide model for boundaries of
  urban settlements*（Royal Society Open Science 5, 180468, 2018）— 建物です
  らなく人口グリッドセル(GRUMPv1, 0.926km格子)。ユークリッド距離閾値クラスタリング
  (CLCA)。道路網不使用

**系統②: 道路交差点ノード ＋ 道路セグメントエッジ（建物不使用）**
- Arcaute et al. 2015, *Cities and Regions in Britain through hierarchical
  percolation*（arXiv 1504.08318）
- Arcaute et al. 2026, peri-urban dislocation（既出、arXiv 2606.12399）

**OS の位置**: 建物ノード×道路網媒介(最短路距離)は、探索した範囲では①②どちらの
系統にも属さない空白であることを確認した。

**なぜこの組み合わせが手つかずだったか（3つの要因）**:
1. **動機の不一致** — ①の問いは「都市の境界はどこか」(道路網は不要)、②の問いは
   「道路網自体の階層構造」(建物は不要)。OS の問い「建物への到達可能性がスケールに
   応じてどう転移するか」は両方を要するが、これは既存2系統のどちらの核心的問いでも
   なかった
2. **データ** — 建物と道路網を位相的に正しく結合したグローバルデータは最近まで
   存在しなかった。Overture Maps(2023年発足)でさえ「道路・歩道がトポロジー的に
   非接続で格納される」既知の問題があり(Esri Australia技術ブログで確認)、スナッピング
   処理が別途必要（OS自身の `snap_tolerance` / `connection_threshold` パラメータが
   これに対応）
3. **計算コスト** — ユークリッド/測地バッファー距離は空間インデックスでほぼ線形、
   国・全球規模を一発処理できる。道路網媒介の最短路距離は Dijkstra 法などグラフ探索
   が必要で計算コストが桁違いに高く、国・全球を1つの巨大グラフとしてパーコレーション
   させるのは非現実的。**OS が1地点=2km四方の独立ウィンドウを大量サンプリングする
   設計を採っているのは、まさにこの計算コストの壁を回避する工夫**であり、①が単純
   距離で国・全球を一発処理できていたのとは対照的

**コード上の裏付け（2026-08-02、`memorist17/OS` リポジトリ確認）**:
`src/preprocessing/network_builder.py` は道路交差点ノード(`type="road"`)に加え
建物重心ノード(`type="building"`)を作り、最寄りの道路セグメント上の点へ virtual
edge で接続する。`src/analysis/percolation.py` は `node_filter="building"` +
`distance_type="shortest_path"` を明示的にサポートし、docstring に
"building-to-building percolation ... shortest path distance" と明記——現行
opensparsity の `config.yaml`（`distance_type: "shortest_path"`,
`node_filter: "building"`）と一致する、実際に使われている手法であることを確認した。

**要注意（over-claim 回避）**: コード自身の docstring に「ネットワーク距離は都市
ネットワーク文献で標準的に推奨される」との記述があるが、これは「ネットワーク距離と
いう概念一般」の話であり、「建物パーコレーションにネットワーク距離を使う」先行研究が
あるという意味ではない。論文では**「ネットワーク距離の概念自体は新しくない、それを
疎密度スペクトラム全体の建物パーコレーションに適用したことが新しい」**と切り分けて
書くこと。

### D. 低密度・スプロールの測り方（対象領域の外部標準）

- **DEGURBA（EU/UN Degree of Urbanisation, GHSL）**（前回）
  rural cluster / low density rural / very low density rural の国際標準クラス。
  → **引く理由**: 「低密度」を著者定義でなく国際標準で層別・検証でき、査読に強い。
- **"Beyond average population density: density-allocation indicators"（CEUS）**
  平均密度を超えて分散の**配分**を測る系。
  → **引く理由**: 低密度＝分散をどう測るかの現代的議論に OS を位置づける。
- **世界の都市は 2000–2020 に上方より外方へ 3.7 倍速く拡大（大規模実証）**
  → **引く理由**: 低密度・分散形態の記述が喫緊という**動機（motivation）**の数字。

- **2025-2026 年の疎・農村・インフォーマル集落識別の"波"**（2026-07-12 追加発見、
  方法論上の競合ではないが動機付けの証拠として重要）
  以下いずれも「疎・農村・インフォーマル集落を識別する」こと自体を主題にしているが、
  **手法はリモートセンシングのセグメンテーション・汎用 ML 分類器・人口統計クラスタ
  リングに限られ、パーコレーション・臨界指数・構造的な生成メカニズムには一切触れて
  いない**：
  - SLUM-i（arXiv 2602.04525, 2026）— Class-Aware Adaptive Thresholding + DINOv2
    OOD フィルタリングによる半教師あり衛星画像セグメンテーション、8都市
  - Kakooei et al., Sci. Rep. 2025（arXiv 2411.02935; nature.com/articles/
    s41598-025-34295-7）— DeepLabV3(ResNet-50) による urban/rural/非居住地の
    3クラス 10m 解像度マップ、アフリカ全土
  - Hallopeau et al.（arXiv 2509.26171, ECML PKDD 2025）— 近傍考慮 GCN による
    インフォーマル集落グリッドセル分類、リオ・ファベーラ5地区のみ
  - Liu, Jang, Dimitrov et al., npj Urban Sustainability 2025（nature.com/
    articles/s42949-025-00295-9）— ウェアラブル LiDAR + 3DMASC(RF) による
    単一ファベーラ(Vidigal, リオ)のセグメンテーション
  - Sentinel-2 ML 分類器研究（tandfonline.com/doi/full/10.1080/19376812.
    2024.2375376, 2025）— Gradient Boost/KNN/RF/SVM ベンチマーク、南ア Gcuwa の
    疎なインフォーマル集落
  - Cui, Zhai & Villa, *Land* 2025（doi.org/10.3390/land14112154）— 「細胞-鎖-形」
    生体模倣フレームワーク + GIS/AHP + natural-breaks 分類、陝西省南部の農村
    形態レジリエンス
  - Tocchi, Pittore & Polese, NHESS 2025（nhess.copernicus.org/articles/25/
    3665/2025/）— ISTAT 自治体データ(7,960自治体・19変数)の階層+k-prototypes
    二段クラスタリングで都市中枢〜周縁農村までの18ネスト類型を構築。**建物・道路網
    グラフデータは自治体スケールで使えないため明示的に除外**、と論文内に明記
  → **引く理由**: 「疎・農村・インフォーマル集落の識別」は 2025-2026 年に非常に
  活発なテーマだが（半年で6本以上）、いずれも画像認識・統計的クラスタリングに
  偏っており、**構造的な生成メカニズム・接続ダイナミクスによる説明には至っていない**
  ——この空白が OS の位置づけそのものであるという動機付けの証拠として束ねて引用できる。
  → **要確認（未確証）**: 検索中に見つかった Space Syntax 系論文
  （nature.com/articles/s41599-025-06413-3、「Space Syntax のネットワーク形態指標
  だけでは formal/informal を判別できなかった」という趣旨）は本サーベイの裏取りで
  1-2 票と確証に至らず。OS の主張（ネットワーク位相の記述子で判別できる）と直接
  関わるため、引用を検討するなら一次資料を自分で確認すること。

---

## 2. あなたの確定資産（ストーリーの原料、Exp01 で実証済み）

- OS = 9 次元**特徴空間**（単一指標でない、Fleischmann の空白域）
- **道路網媒介パーコレーション**（Arcaute 系の建物版・独自）
- **W_trans, γ が全密度帯で一様基準(5.72%)以上の固有情報**を持つ唯一の指標ペア
- 密度の識別寄与は**両極端で崩壊**（d\*_sparse≈0.0013 / d\*_dense≈0.060）
- **全球 B1 センサス（134 万地点、進行中）** — サンプリング不要の全数
- 1 地点 = オーバーレイ画像 1 枚（同一密度・異形態ペアの定性エビデンスに直結）

---

## 3. ストーリーテリング 3 案

### 案1（推奨）: 「位置から、かたちへ」— Beyond Critical Distance
**主張**: 疎な居住形態の識別は、連結が*どこで*起きるか（r_crit）ではなく
*どれだけ鋭く／広く*起きるか（γ, W_trans）に宿る。
- 対抗軸が明快: Settlement percolation 全球マップ(r_crit)の「次」、
  Arcaute peri-urban(階層構造)の「連続量版」
- Exp01 の「両極端での崩壊」と B1 センサスがそのまま主結果になる
- タイトル例: *"Beyond the critical distance: transition dynamics of the
  building–street network as morphological descriptors of sparse settlement"*
- **弱点**: 物理寄りに見える。→ DEGURBA と同一密度ペア画像で"都市"に接地

### 案2: 「密度が失敗する所で何が効くか」— When Density Fails（卒論の直系拡張）
**主張**: 低密度領域で密度は情報解像度を失い、識別はプロセス指標へ移行する。
- 卒論の物語を全球 N=134 万へ格上げ（探索的→統計的）
- Spacemate / Angel の「密度分解」系に正面から接続
- **弱点**: Exp01 で判明した通り「密度の崩壊は**両極端**」であり、
  素朴な「低密度で密度が効かない」は中間帯では成り立たない。
  正直に「2 つの崩壊メカニズム」として書けば逆に深い（が物語は複雑）

### 案3: 「疎居住の全球アトラス」— A Global Atlas of Sparse Settlement Form
**主張**: 最疎帯(B1)の全球センサスで OS 指標の世界地図を作り、
疎な居住形態の類型を提示する。
- Fleischmann の Urban Atlas / GSP 全球マップと同じ土俵で"疎"に特化
- B1 センサスと 134 万枚の画像が主役、記述的で示しやすい
- **弱点**: 記述に寄り、理論的貢献（なぜ γ/W_trans か）が薄まる。
  案1 の主張を検証パートに内包すると強い

### 推奨: **案1 を主軸、案3 を実証エンジン、案2 を序論の入口**
1 本の論文として:
- 序論 = 案2（密度の限界、Spacemate/Angel、Jacobs）で入る
- 方法・主張 = 案1（転移ダイナミクスを記述子に）
- 検証 = 案3（B1 全球センサス）＋ Exp01（寄与曲線）＋同一密度ペア画像
- 対抗 = Arcaute 2026 / GSP 2026 を「位置・階層」に対する「かたち・連続量」として配置

---

## 4. 各案に要る追加実験（優先順）

1. **同一密度・異形態ペアの提示**（全案で必要・軽い）: B1/global_v2 から
   d がほぼ等しく OS 距離が最大／最小のペアを抽出し、オーバーレイ画像で並置。
   「密度は同じ、γ/W_trans が違う」を一目で。→ opensparsity の画像がそのまま図
2. **DEGURBA クラスによる層別再現**（案1/2）: 各地点に rural cluster /
   low density rural を付与し、Exp01 の寄与曲線を層別に。国際標準で頑健性主張
3. **W_trans/γ の全球マップ**（案1/3・B1 センサス完了後）: GSP の r_crit マップと
   並べ、「位置マップ」対「かたちマップ」の対比図
4. **設計 weight 付き Exp01 再計算**（査読対策）: global_v2 の design_weight で
   重み付け、結論の頑健性を確認

---

## 5. 引用管理メモ

- 新規 BibTeX 追加候補（カタログ未収録）: Berghauser Pont & Haupt 2004/2021,
  Caruso Hilal Thomas 2017, Fleischmann Romice Porta 2020,
  Arcaute et al. 2026 (2606.12399), Settlement percolation GSP 2026 (2603.04439),
  DEGURBA/GHSL user guide, gradient percolation (Sapoval et al.),
  Findings percolation-transitions review, "3.7x outward" 実証論文
- 新規 BibTeX 追加候補・第2弾（2026-07-12 ターゲットサーベイ、カタログ未収録）:
  Kalisky & Cohen 2006 (PRE, width of percolation transition),
  Raimbault 2019 (arXiv 1903.07141, multi-dimensional urban network percolation),
  Zeng et al. 2019 (PNAS/arXiv 1709.03134, percolation mode switching in traffic),
  dos Santos & Ricardo 2026 (arXiv 2601.09747, topological percolation in dengue),
  SLUM-i 2026 (arXiv 2602.04525), Kakooei et al. 2025 (arXiv 2411.02935),
  Hallopeau et al. 2025 (arXiv 2509.26171), Liu/Jang/Dimitrov et al. 2025
  (npj Urban Sustainability), Sentinel-2 ML classifier 2025 (tandfonline),
  Cui/Zhai/Villa 2025 (Land), Tocchi/Pittore/Polese 2025 (NHESS)
- カタログの「条件付き(31)」を上記フレームに沿って「はい／いいえ」に再仕分けすると
  参考文献リストが締まる
- 新規BibTeX追加候補・第3弾（2026-08-02、建物×道路網媒介の新規性確認）:
  Behnisch, Schorcht, Kriewald & Rybski 2019 (Landscape and Urban Planning 191,
  103631, building connectivity CCA), Oliveira, Furtado, Andrade Jr. & Makse 2018
  (Royal Society Open Science 5, 180468, worldwide urban boundaries CLCA),
  Arcaute et al. 2015 (arXiv 1504.08318, hierarchical percolation Britain)

## 6. 投稿・実装戦略 — momepy コミットと「誰が嬉しいか」（2026-08-02）

### 6-1. momepy の現状（コードレベルで確認済み）

momepy（PySAL 傘下、メンテナ = Martin Fleischmann 本人）の全モジュールを確認:
- `graph.py` は**道路網のみ**の指標（meshedness, gamma, centrality 系）。ノードは交差点
- 建物×道路は `get_nearest_street()` 等の**属性付与ヘルパーのみ**。結合グラフは作らない
- **percolation・臨界距離・転移に相当する機能はゼロ**（全モジュール grep で確認）

つまり OS の手法は momepy の機能空白であり、Fleischmann 自身が 2020 年に明言した
「spatial distribution が体系的に手薄」という空白（セクション A）と正確に一致する。
**「あなたのライブラリに欠けているとあなた自身が書いたものを持ってきた」形になる。**

### 6-2. 推奨する順序（順番が重要）

1. **arXiv プレプリント最優先**（案1の方法論文）。優先権はこれで確定。
   momepy PR を先に出すと、査読の遅い論文より先にコードだけが世に出て、
   手法が「momepy の一機能」として消費されるリスクがある
2. **プレプリント公開直後に momepy へ PR**。`momepy.percolation()` 的な形で、
   入力 = buildings/streets GeoDataFrame、出力 = 転移曲線 + r_crit/W_trans/γ。
   docstring でプレプリントを引用 → momepy ユーザー全員が引用候補になる
3. **ジャーナル投稿時に「momepy vX.Y で利用可能」と書く**。再現性の主張が強まり、
   EPB / Landscape and Urban Planning 系の査読者（momepy コミュニティと重なる）の
   心証も良い

opensparsity 単体の JOSS 論文は発見されにくく採用チャネルとして弱いので優先度低
（後からでも出せる）。

### 6-3. 誰にとって・どのような状況で嬉しいのか（序論の設計図）

1. **集落マッピング・モニタリング機関（JRC/GHSL, WSF, 世銀系）** — 最も具体的な
   「困っている人」。密度ベース分類（DEGURBA）の識別力は最疎帯でちょうど崩壊する
   （Exp01, d*_sparse≈0.0013）。**彼らの道具が一番効かない場所こそ、彼らが一番
   測りたい場所**（農村の変容、インフォーマル集落の成長）。OS は GSP の r_crit
   全球マップの「次の一枚」として、同じデータから計算できる構造軸を提供する
2. **都市形態学コミュニティ（Fleischmann 系, momepy ユーザー）** — 分類学 361 指標
   に静的指標しかなく「どう繋がっていくか」のプロセス指標が空白だと自認している。
   momepy コミットはこの層への直接デリバリー
3. **疎地域の計画実務（農村サービス配置・災害復興・人道マッピング）** — W_trans が
   狭い＝一つの鋭い共同体 / 広い＝段階的に付加された散在構造。学校・診療所の配置、
   道路投資の優先順位、復興時の「どこを直せば連結が戻るか」の判断を変える。
   HOT（人道 OSM）や MSF の集落マッピング文脈にも接続可能
4. **統計物理コミュニティ** — 転移のかたちが観測量になる新しい実証系。ただし
   「受益者」ではなく「正当性を保証する審級」なので序論の主役にしない

### 6-4. ストーリーテリングへの反映

案1主軸＋案3実証＋案2導入（セクション3の推奨）は維持しつつ、**導入は抽象論でなく
受益者①の具体的状況から入る**:

> 全球集落モニタリングの標準（DEGURBA/GSP）は密度と臨界距離で集落を分類している。
> しかしその識別力は、世界で最も急速に変化している最疎帯でちょうど崩壊する（Exp01）。
> われわれは、彼らが既に持っているのと同じデータから計算でき、彼らの r_crit マップと
> 並べられる、"転移のかたち" という次の記述子を提供する。

これにより案1の弱点「物理寄りに見える」を、物理を薄めるのではなく**受益者を先に
立てる**ことで解消する。momepy 実装は「すぐ使える」という約束の担保。

---

## 7. 計算資源見積もり — 日本全域 / 全球（2026-08-02）

### 7-1. 実測ベースの単価（Apple M1 Mac mini, 16GB, 実測値）

| 項目 | 値 | 備考 |
|---|---|---|
| フェッチ（地点別 S3 スキャン） | 100–120 秒/地点 | 地点によらずほぼ一定。**ボトルネック** |
| フェッチ（`prefetch.py` join 方式） | 償却 ~1 秒/地点 | 実装済み。中断再開可（manifest.json） |
| 計算 | 5–35 秒/地点 | 建物ノード数の**2乗**で増加（14,000 ノードのキベラ = 35 秒） |
| ストレージ | 0.1–0.8 MB/地点（画像）＋ 数 KB（DB 行） | |

### 7-2. 日本全域

- 国土 378,000 km² ÷ 4 km²（2km 窓）= 全被覆 **~94,500 窓**。ただし大半は無人の
  山林なので、**建物を含む窓 ~30,000–40,000**（可住地面積 ~33% と整合）が実処理対象
- **注意**: 東京・大阪の稠密窓は建物 2–3 万ノード → 計算 60–160 秒/窓、かつ
  距離行列が 30k²×8B ≈ **7.2 GB/プロセス**。16GB マシンでは稠密窓の並列度を
  落とす（または float32 化・ノード上限）必要あり。日本の平均計算時間は
  混合で ~15–25 秒/窓と見積もる

| 項目 | 見積もり |
|---|---|
| プリフェッチ | 日本は連続 bbox なので row-group pruning が効く（join 不要、static 的抽出で可）。転送 ~15–30 GB、一晩 |
| 計算時間 | 35,000 窓 × 20 秒 ÷ 6 並列 ≈ **33 時間（1.5 日）** |
| ストレージ | 画像 ~14 GB + DB ~1 GB + ローカルキャッシュ 20–30 GB = **合計 ~50 GB** |
| メモリ | 通常窓は ~1–2 GB/プロセス。稠密窓のみ 4–8 GB → 稠密窓は並列度 2 で別バッチ |

**結論: 日本全域は手元の M1 Mac mini で 2–3 日・50 GB。完全に現実的。**

### 7-3. 全球

- **B1 センサス（最疎帯 134 万地点、既定計画）**: 疎なので建物数少・計算 ~5 秒/地点
  - 計算: 1.34M × 5 秒 ≈ 1,860 CPU 時間 → M1 6 並列で ~13 日 / クラウド 32 vCPU で **~2.5 日**
  - プリフェッチ: 地点が全球散在なので join 方式必須（述語プッシュダウン不可、
    テーマ全走査）。建物テーマ全球 ~300–400 GB 走査 → **自宅回線では重い。
    Overture バケットと同リージョン（AWS us-west-2）で実行すれば転送無料・高速**で
    数時間〜1日
  - ストレージ: 画像 1.34M × ~0.2 MB ≈ **270 GB** + DB ~10 GB。
    フラットな `images/` に 134 万ファイルは危険 → **サブディレクトリ分割が必要**
  - クラウド費用: スポットで **$100–300 程度**＋ストレージ ~$10/月。安い
- **全球・全密度帯（もしやるなら）**: 建物を含む窓 ~800–1,200 万。
  平均 15 秒 → 33,000–50,000 CPU 時間 ≈ 128 vCPU スポットで 11–16 日、
  **$1,500–4,000**、画像 **3–6 TB**。可能だが一つのプロジェクト規模。
  → **推奨: やらない**。B1 全数 + 中高密度帯の層化サンプル（exp01 の 10,050 /
  exp04 の 16,474 方式）が統計的にも費用的にも正しい設計

### 7-4. まとめ

| シナリオ | 時間 | ストレージ | 費用 | 判定 |
|---|---|---|---|---|
| 日本全域（~35,000 窓） | 2–3 日 | ~50 GB | 電気代のみ | **手元で可** |
| 全球 B1（134 万地点） | 2.5 日（32 vCPU）〜13 日（手元） | ~300 GB | ~$100–300 | **クラウド推奨（us-west-2）** |
| 全球・全密度帯（~1,000 万窓） | 2 週間（128 vCPU） | 3–6 TB | $1,500–4,000 | **非推奨**（層化サンプルで代替） |

## 出典（本サーベイで参照した URL）

- Berghauser Pont & Haupt, Spacemate — https://journals.sagepub.com/doi/10.1068/b39141
- Caruso, Hilal & Thomas 2017 — https://www.sciencedirect.com/science/article/abs/pii/S0169204617300518
- Fleischmann, Romice & Porta 2020 — https://journals.sagepub.com/doi/10.1177/2399808320910444
- Arcaute et al. 2026, Peri-Urban Dislocation — https://arxiv.org/abs/2606.12399
- Settlement percolation: global maps of Critical Distances — https://arxiv.org/abs/2603.04439
- A Review of Percolation-like Transitions in Cities and Landscapes — https://findingspress.org/article/150358
- gradient percolation fronts — https://arxiv.org/pdf/1210.0889
- DEGURBA user guide (JRC) — https://publications.jrc.ec.europa.eu/repository/bitstream/JRC118444/dug_3.0_user_guide_final.pdf
- Beyond average population density (density-allocation) — https://www.sciencedirect.com/science/article/abs/pii/S026483772100555X
- Fleischmann Urban Atlas / numerical taxonomy — https://journals.sagepub.com/doi/full/10.1177/23998083211059835

### 追加出典（2026-07-12 ターゲットサーベイ）

- Kalisky & Cohen 2006, Width of percolation transition in complex networks — https://pubmed.ncbi.nlm.nih.gov/16605583/
- Raimbault 2019, Multi-dimensional Urban Network Percolation — https://arxiv.org/pdf/1903.07141
- Zeng et al. 2019, Switch between critical percolation modes in city traffic dynamics — https://arxiv.org/pdf/1709.03134
- dos Santos & Ricardo 2026, Topological Percolation in Urban Dengue Transmission — https://arxiv.org/abs/2601.09747
- SLUM-i 2026 — https://arxiv.org/abs/2602.04525
- Kakooei et al. 2025 — https://www.nature.com/articles/s41598-025-34295-7 （arXiv 2411.02935）
- Hallopeau et al. 2025 — https://arxiv.org/abs/2509.26171
- Liu, Jang, Dimitrov et al. 2025 — https://www.nature.com/articles/s42949-025-00295-9
- Sentinel-2 ML classifier 2025 — https://www.tandfonline.com/doi/full/10.1080/19376812.2024.2375376
- Cui, Zhai & Villa 2025 — https://doi.org/10.3390/land14112154
- Tocchi, Pittore & Polese 2025 — https://nhess.copernicus.org/articles/25/3665/2025/
- （未確証・要一次資料確認）Space Syntax formal/informal 判別論文 — https://www.nature.com/articles/s41599-025-06413-3

### 追加出典（2026-08-02、建物×道路網媒介の新規性確認）

- Behnisch, Schorcht, Kriewald & Rybski 2019, Settlement percolation (building connectivity) — https://doi.org/10.1016/j.landurbplan.2019.103631
- Oliveira, Furtado, Andrade Jr. & Makse 2018, A worldwide model for boundaries of urban settlements — https://royalsocietypublishing.org/doi/full/10.1098/rsos.180468
- Arcaute et al. 2015, Cities and Regions in Britain through hierarchical percolation — https://arxiv.org/pdf/1504.08318
- 実装確認（内部リポジトリ、公開コード）: memorist17/OS — https://github.com/memorist17/OS
  （`src/analysis/percolation.py`, `src/preprocessing/network_builder.py`）
