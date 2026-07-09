# Exp04: DEGURBA層化サンプリングによる疎居住センサス（設計中）

## 背景・目的

`docs/related_work_and_storyline.md`の「全球B1センサス（134万地点）」は、根拠のない
粗い見積もりだったことが判明した（2026-07-10）。母集団の定義（「B1」）自体も、
旧リポジトリの`bandwise_sensitivity.py`が使う内部的な密度バンド名（B1〜B7の最疎バンド）
と、WSF自己流の閾値（0.005相当）という**2つの別物が混同されていた**。

本実験は、母集団定義を**DEGURBA（EU/UN Degree of Urbanisation、人口密度ベースの
国際標準分類）**に置き換え、統計的に必要十分な規模の層化サンプルを設計する。

## DEGURBAの定義

人口密度1km²グリッドセルを基準とする階層分類（[JRC/UN統計委員会 2020年採用](https://unstats.un.org/UNSDWebsite/statcom/session_52/documents/BG-4a-DEGURBA_Manual-E.pdf)）。
GHS-SMODラスタのコード値（[凡例](https://human-settlement.emergency.copernicus.eu/ghs_smod2023.php)）:

| コード | クラス | 基準 |
|---|---|---|
| 30 | Urban Centre | >1,500人/km²（連続塊で人口5万人以上） |
| 23 | Dense Urban Cluster | — |
| 22 | Semi-Dense Urban Cluster | — |
| 21 | Suburban/Peri-urban | — |
| 13 | Rural Cluster | 300人/km²以下（Rural全体の基準） |
| **12** | **Low Density Rural** | **母集団に含める** |
| **11** | **Very Low Density Rural** | **母集団に含める（<50人/km²）** |
| 10 | Water | — |

**重要な注意**: DEGURBAは**人口密度**、OSの`density`はOverture建物footprintの
**占有率（GSI）**——別軸。両者は必ずしも一致しない（人口が少なくても建物footprint
占有率が高いケース等）。独立した外部基準で層化する設計として妥当。

## サンプリング設計（案、2026-07-10時点でユーザーと合意した粒度）

- **層**: 22サブリージョン（global_v2と同じ区分）× DEGURBA 2クラス（11, 12）= 44層
- **層あたり点数**: 600〜800点
- **総設計点数**: 約3万点（exp01の5〜10%脱落率を見込む）
- **実行時間見積り**: 3万点 × 130秒 ÷ 28並列（Mac/mini/WSL） ≈ 1.6日
- **design_weight**: 各層の実面積（DEGURBA該当セル数）に応じた逆確率重みが必要
  （国・地域で分布が大きく偏るため）

## 進め方

1. `analyze_existing_degurba.py` — GHS-SMODラスタが入手できたら、既存exp01の
   10,050地点がどのDEGURBAクラスに落ちるかを集計（母集団サイズ・既存データの
   偏りの見積もり用。ブロッカー: 下記参照）
2. （未着手）DEGURBA11/12セルの全球候補地点リストを生成し、22サブリージョン×
   2クラスで層化抽出（600〜800点/層）
3. （未着手）design_weightの算出方法を確定
4. **本番実行は必ずユーザーのGOを得てから**（[technical_notes.md](../../docs/technical_notes.md) §5）

## GHS-SMODラスタの入手（2026-07-10、解決済み）

`curl`/`wget`/`urllib`はユーザーの権限ルールでブロック、ブラウザ拡張経由でも503で
取得できなかったため、最終的にユーザーが`!curl`で直接ダウンロード（28MB、成功）。
入手先: `https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_SMOD_GLOBE_R2023A/
GHS_SMOD_E2025_GLOBE_R2023A_54009_1000/V2-0/GHS_SMOD_E2025_GLOBE_R2023A_54009_1000_V2_0.zip`

## 結果: 既存exp01・10,068地点のDEGURBAクラス分布

`analyze_existing_degurba.py`実行結果（[os_vectors_with_degurba.csv](os_vectors_with_degurba.csv)）:

| DEGURBAクラス | 地点数 | 割合 |
|---|---|---|
| very_low_density_rural (11) | 3,619 | 36.0% |
| low_density_rural (12) | 2,955 | 29.3% |
| rural_cluster (13) | 1,130 | 11.2% |
| suburban_periurban (21) | 823 | 8.2% |
| water (10) | 603 | 6.0% |
| dense_urban_cluster (23) | 455 | 4.5% |
| urban_centre (30) | 306 | 3.0% |
| semi_dense_urban_cluster (22) | 177 | 1.8% |

**母集団2クラス（11+12）合計: 6,574地点（65.3%）**——global_v2の設計（WSF密度で層化）は
そもそも疎な地点を多く含んでいたため、想定より高い割合でDEGURBA最疎2クラスに合致した。
`water`が6%あるのは、Overtureの建物footprintは存在する沿岸・島嶼部の地点が、1km解像度の
人口ラスタでは海セルに分類されるため（解像度のミスマッチ、想定内の誤差）。

サブリージョン別（対象2クラスのみ、22地域）は **92地点(Micronesia)〜411地点(Southern Africa)**
と大きく偏っている。44層(22サブリージョン×2クラス)で層あたり600〜800点を目指す設計に対し、
**既存データだけでは大半の層が全く足りない**（小さいサブリージョンでは片クラス平均50点未満）。
また新パイプラインの3新指標(building_count_density等)は既存地点の生geometryを保持していない
ため後付けできず、**実質的にほぼ全点を新規`ops run`する必要がある**（既存データは母集団サイズ
の見積もりと候補地点選定の参考にのみ使う）。

## 次にやること

1. DEGURBA11/12セルの全球候補地点リストを生成（GHS-SMODラスタから該当セルを抽出、
   22サブリージョンでタグ付け）
2. 各層（サブリージョン×クラス）から600〜800点を無作為抽出
3. design_weight（層の実セル数に基づく逆確率重み）を算出
4. **本番実行（`ops run`を新規約3万点で）は必ずユーザーのGOを得てから**
   （[technical_notes.md](../../docs/technical_notes.md) §5）
