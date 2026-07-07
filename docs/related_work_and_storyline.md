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

- **Settlement percolation: building connectivity & poles of inaccessibility
  （Sci. Total Environ. 系）／独 830m country-spanning cluster**
  建物接続パーコレーションの先行実装例。
  → **引く理由**: 建物ノード・距離しきい値パーコレーションの手法的先例として。

### D. 低密度・スプロールの測り方（対象領域の外部標準）

- **DEGURBA（EU/UN Degree of Urbanisation, GHSL）**（前回）
  rural cluster / low density rural / very low density rural の国際標準クラス。
  → **引く理由**: 「低密度」を著者定義でなく国際標準で層別・検証でき、査読に強い。
- **"Beyond average population density: density-allocation indicators"（CEUS）**
  平均密度を超えて分散の**配分**を測る系。
  → **引く理由**: 低密度＝分散をどう測るかの現代的議論に OS を位置づける。
- **世界の都市は 2000–2020 に上方より外方へ 3.7 倍速く拡大（大規模実証）**
  → **引く理由**: 低密度・分散形態の記述が喫緊という**動機（motivation）**の数字。

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
- カタログの「条件付き(31)」を上記フレームに沿って「はい／いいえ」に再仕分けすると
  参考文献リストが締まる

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
