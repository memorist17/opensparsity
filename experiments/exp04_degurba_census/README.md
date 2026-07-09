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

## 現在のブロッカー（2026-07-10）

GHS-SMODグローバルラスタ（GeoTIFF, 1km, World Mollweide EPSG:54009, JRC提供）の入手:

- ダウンロードページ: https://human-settlement.emergency.copernicus.eu/download.php?ds=smod
- 対象ファイル: `GHS_SMOD_E2025_GLOBE_R2023A_54009_1000_V2_0.zip`（28MB、
  `https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_SMOD_GLOBE_R2023A/GHS_SMOD_E2025_GLOBE_R2023A_54009_1000/V2-0/`配下）
- **`curl`/`wget`/Python `urllib`はユーザーの権限ルールでブロック**（CLAUDE.mdの
  「外部サーバーにデータを送信するな」）
- ブラウザ拡張（claude-in-chrome）経由でも、実ファイルへの直接GETが503を返す
  （ディレクトリ一覧は200で見える）。クリックしても`~/Downloads`にファイルが
  現れない——おそらく拡張のダウンロード許可がサイト単位でユーザーの明示操作を
  要するため（safety gate、[claude-in-chromeスキルの説明](https://human-settlement.emergency.copernicus.eu/)参照）
- **要対応**: ユーザーが`!curl`または手動ブラウザ操作でダウンロードし、
  ローカルパスを渡してもらう必要がある
