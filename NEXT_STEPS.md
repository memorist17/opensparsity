# Next Steps（2026-07-10時点）

2026-07-08セッションで exp01〜exp03 まで実施し、文書化が未完了のまま終了した。
その文書化を2026-07-09に完遂。2026-07-10、GitHubに新規リポジトリ作成・push、および
密度系指標3種（building_count_density / building_footprint_mean_m2・median_m2 /
road_length_density）を`pipeline.py`に追加（[technical_notes.md](docs/technical_notes.md) §2）。
以下は次にやるべきことの優先順。

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

## 2. B1全球センサス → DEGURBA層化サンプリングに置き換え（設計完了、実行はGO待ち）

`docs/related_work_and_storyline.md`の「進行中（134万地点）」は根拠のない見積もりだったと
判明（2026-07-10）。母集団定義をDEGURBA（人口密度の国際標準分類、Low/Very low density rural）
に切り替え、22サブリージョン×2クラス=44層・層あたり600〜800点・総計約3万点の層化サンプリング
設計に確定した。詳細: [experiments/exp04_degurba_census/README.md](experiments/exp04_degurba_census/README.md)、
[sampling/README.md](sampling/README.md)。

- [x] GHS-SMODラスタ入手・DEGURBA定義確認・既存exp01地点の分布集計
- [x] 候補セル数の実測（2km格子でclass11=3,392万・class12=154万セル、枯渇リスクなし確認）
- [x] `sampling/`パイプライン実装（候補抽出→国/サブリージョン判定→層化抽出→design_weight算出）
- [ ] `sampling/final_sample.csv`の生成（実行中/実行待ち、進捗はセッションログ参照）
- [ ] 生成された候補点リストの目視レビュー（層別レポートで`pool_exhausted`層を確認）
- [ ] mini/WSL/Macの3台構成での分割実行計画（`config.yaml`の`n_jobs`調整含む、
      [technical_notes.md](docs/technical_notes.md) §4）
- [ ] **本番`ops run`（約3万点、3台で約1.6日）は必ずユーザーの明示的なGOを得てから実行**
      （[technical_notes.md](docs/technical_notes.md) §5）

## 3. DEGURBA層別再現（査読対策）

- [ ] exp01の分析をDEGURBA（都市化度）クラスで層別して再実行し、結果が頑健かを確認
- [ ] design_weight（層化サンプリングの重み）を付けた再計算で、無作為抽出でない
      バイアスの影響を確認する

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
