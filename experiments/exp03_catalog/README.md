# Exp03: OS指標による都市形態カタログ

## 目的

exp01/exp02 は「密度 vs ダイナミクス」という1軸の物語を扱うが、本実験はより記述的に、
OS9次元ベクトルから**世界の集落を形態タイプに分類するカタログ**を作る。
論文の記述的貢献（「疎居住の全球アトラス」案、[docs/related_work_and_storyline.md](../../docs/related_work_and_storyline.md) 案3）の土台。

## 手法（`build_catalog.py`）

1. exp01 の `os_vectors.csv`（全球10,050地点）を入力
2. 9特徴 `[density, lacunarity_mean, lacunarity_slope, r_crit, W_trans, gamma,
   mfa_alpha_width, Delta_D, S_alpha]` を使用。`lacunarity_mean` は値のレンジが
   5桁に及ぶため対数変換してからクラスタリング（外れ値でスケールが歪むのを防ぐ）
3. 標準化（z-score）後、**KMeans（K=6, seed=42）**でクラスタリング
4. クラスタごとに9次元プロファイル（レーダー図）・PCA散布図・9次元全値テーブルを算出
5. 各クラスタの代表地点（`reps.yaml`→`reps2.yaml`の2回に分けて計33地点、
   `ops run`でオーバーレイ画像を実フェッチ）を1〜3枚選び、カタログに埋め込み（base64）
6. 日本語での類型解説を各クラスタに付与（`DESCRIPTIONS`辞書、代表画像を見た上で執筆）
7. 指標を手法グループ順（密度→ラキュナリティ→パーコレーション→MFA）に並べ、
   「指標の見方」表（記号・意味・単位・大小の向き）をカタログ冒頭に配置

クラスタ番号（Type1〜6）は**サイズ降順**（`value_counts()`順）で振り直している
（sklearnのラベル0〜5とは対応しない）。

## 結果（`catalog.html`, `catalog_assignments.csv`）

| Type | 名称 | 地点数 | 特徴 |
|---|---|---|---|
| 1 | 格子核・急峻連結型（中密） | 3,066 | 計画的格子街区が核、γが高い（+0.7σ）、d≈0.015、最大クラスタ |
| 2 | 街道散在型（疎） | 2,360 | 道路沿いにまばらに点在、Λ̄大、d≈0.003 |
| 3 | 凝集放射型（中密・漸進連結） | 1,591 | 一角に凝集し道路が放射、W_trans +1.8σと際立つ |
| 4 | 標準中密型 | 1,449 | 9指標すべて平均付近、d≈0.018、基準的タイプ |
| 5 | 稠密市街型（高密） | 822 | d≈0.075最高密、Λ̄最小、街路網発達 |
| 6 | 山間散村型（疎・漸進連結） | 762 | d≈0.004最疎、Λ̄最高、W_trans +0.8σ |

合計 10,050地点（exp01の解析対象と同じ集合）。

## 未完了・既知の課題

- [ ] カタログHTML（`catalog.html`, 1.1MB, base64埋め込み）を目視で最終確認。
      前回の作業セッションでは表示崩れの疑いがあり、特に **Type4（標準中密型）** の
      代表画像・レーダー図が正しく表示されているか未確認のまま終了した
- [ ] `reps2_run.log` で `[8/18]` の1件が欠番（3件skip中の1件、原因未記録）。
      どの地点がskipされ、代替が採用されたか要確認
- [ ] 論文本文への統合（どの案で使うか、[storyline案3](../../docs/related_work_and_storyline.md)参照）は未着手

## 再現手順

```bash
cd opensparsity
.venv/bin/python experiments/exp03_catalog/build_catalog.py
# 代表画像がまだ無い場合は先に:
.venv/bin/ops run --locations experiments/exp03_catalog/reps.yaml  --out experiments/exp03_catalog/reps_out/
.venv/bin/ops run --locations experiments/exp03_catalog/reps2.yaml --out experiments/exp03_catalog/reps_out/
```

詳細な実行ログ・結果の解釈は [REPORT.md](REPORT.md) を参照。
