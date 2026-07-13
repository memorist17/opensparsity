# Next Steps（2026-07-10時点）

2026-07-08セッションで exp01〜exp03 まで実施し、文書化が未完了のまま終了した。
その文書化を2026-07-09に完遂。2026-07-10、GitHubに新規リポジトリ作成・push、
密度系指標3種（building_count_density / building_footprint_mean_m2・median_m2 /
road_length_density）を`pipeline.py`に追加、および**DEGURBA層化サンプリングによる
候補地点リスト27,710点を生成**（`sampling/final_sample.csv`、詳細は§2）。
**まだ`ops run`本番実行はしていない（GO待ち）**。以下は次にやるべきことの優先順。

## 0. 用語の整理（低コスト・査読対策）

- [ ] Fleischmann Index-of-Elements命名で、OS9指標＋新規3指標をIndex/Elementの形で
      `related_work_and_storyline.md`に書き直す。Λ̄・s_Λ・Δα・ΔD・S_αはSpatial
      distributionカテゴリ、W_trans/γはConnectivityカテゴリに入り、いずれも
      Fleischmannが「文献で手薄」と指摘したカテゴリに一致する——この対応関係を
      ポジショニングの根拠として明記する

## 1. exp02/exp03の詰め（すぐできる・低コスト）

- [ ] exp02: 6ペア・12地点のオーバーレイ画像を生成し、比較図を作成
      （[exp02 README](experiments/exp02_isodensity_pairs/README.md)参照）
- [ ] exp03: `catalog.html` の目視最終確認。特にType4（標準中密型）の表示崩れ疑いを解消し、
      `reps2_run.log` でskipされた3件の原因を確認する
      （[exp03 README](experiments/exp03_catalog/README.md)参照）
- [ ] exp03: KMeans K=6の妥当性検証（エルボー法/シルエット係数、K=5・7との比較）
      （[exp03 REPORT.md](experiments/exp03_catalog/REPORT.md) §4）

## 2. DEGURBA層化サンプリング — **本番実行完了（2026-07-13）**

`docs/related_work_and_storyline.md`の「進行中（134万地点）」は根拠のない見積もりだったと
判明（2026-07-10）。母集団定義をDEGURBA（人口密度の国際標準分類、Low/Very low density rural）
に切り替え、22サブリージョン×2クラス=44層・層あたり最大700点の層化サンプリングを実装・実行した。
詳細: [experiments/exp04_degurba_census/README.md](experiments/exp04_degurba_census/README.md)、
[sampling/README.md](sampling/README.md)。

- [x] `sampling/final_sample.csv`生成: **27,710点**（44層、5層はプール枯渇で全数使用）
- [x] **本番`ops run`完了（2026-07-10 11:04 〜 2026-07-13 午前、GO取得済み）**:
      全27,710点処理済み（丸めキー照合で漏れゼロ確認）。
      **done 16,474点（59.5%）／failed 11,236点（40.5%）**。
      failedはほぼ全て「bboxに建物も道路も無い」= Overtureに何も記載がない地点
      （§3の分析でこのempty率自体をデータとして扱うこと）
- [x] 実行はMac(初日のみ)→mini+wslの2台に移行、途中で残りリスト方式
      （`sampling/export_remaining.py`）に切替。統合DBは**Mac上の`results_merged/results.db`**
      （mini.db/wsl.dbのマージ、27,904行、gitには含めない）。
      オーバーレイ画像はwsl(13,198枚)とmini(3,051枚)に分散したまま
- [x] **実現サンプルへのdesign_weight再計算**（2026-07-13、
      `experiments/exp05_degurba_breakdown/build_dataset.py`。empty率も層別に集計済み）
- [ ] 候補点リストのユーザーによる目視レビュー（`final_sample_stratum_report.csv`の
      `pool_exhausted`層、`un_subregions.py`の国マッピング）

## 3. DEGURBA層別再現（査読対策）— exp05として実施済み（2026-07-13）

- [x] exp01のLOFO感度分析をDEGURBA実現サンプル16,474点・design_weight付きで再実施
      （[exp05 REPORT.md](experiments/exp05_degurba_breakdown/REPORT.md)）。
      **主要な発見**: rural帯では (a) 識別の主役はΔD・Δα・s_Λ・Λ̄・d の5特徴、
      (b) W_trans・r_crit は全域で冗長（exp01の「疎の極で主役」は再現せず、
      母集団定義の差が最有力仮説）、(c) γ は d>2×10⁻³ かつ**面積加重でのみ**基準超
- [ ] **Overtureカバレッジバイアス検証（投稿前必須・本丸）**:
      `exp05/overture_bias_check.py` 準備済み。GHS-BUILT-Sラスタの入手のみ
      ユーザーの`!curl`が必要（スクリプト冒頭にURL）
- [ ] γの立ち上がり（d≈2×10⁻³）のサブリージョン層別追試（窓の振動の原因切り分け）
- [ ] exp01との食い違いの決着: global_v2の同一地点をopensparsityパイプラインで
      再処理してネットワーク構築差（L3）を除外検証する

## 4. 論文への統合

- [ ] `docs/related_work_and_storyline.md` の3案（B1センサス中心／Exp01中心／
      疎居住アトラス）のうち、exp01〜exp03の結果を踏まえてどれを主軸にするか決定する
- [ ] exp01の「密度軸両極端でダイナミクスが支配」とexp03の「クラスタ構造」を
      統合したストーリーラインを書く

## 5. 運用メモ

- 旧リポジトリ（`251229_repro_apple`）は論文・図生成用として凍結気味に維持。
  今後の地点処理・バッチは`opensparsity`側で行う
- 重い処理（バッチ・全球スイープ・複数台デプロイ）は必ずGO待ち
  （[technical_notes.md](docs/technical_notes.md) §5）
