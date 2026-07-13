# Exp05 実行レポート: DEGURBA疎居住センサスの密度崩壊分析

**実行日**: 2026-07-13 / **データ**: DEGURBA層化サンプル本番実行の実現サンプル
（done 16,474地点、design_weight再計算済み） / **手法**: exp01と同一のLOFO感度分析
（一様基準 5.72%）を design_weight 付きで実施

## TL;DR

> **exp01（global_v2全球サンプル）の「疎の極でパーコレーション系が主役」は、
> DEGURBA rural限定の母集団では再現しない。** rural帯（d ≈ 10⁻⁵〜10⁻¹）全域で
> 固有情報の主役は **d・Λ̄・s_Λ・Δα・ΔD の5特徴（8〜10%）**であり、
> **r_crit・W_trans・S_α は全域で冗長（1〜3%）**。
> γ のみ d ≈ 2×10⁻³ を境に固有情報を持ち始める（4.5%→7.5%）が、
> **この γ の立ち上がりは design_weight を掛けたときだけ現れる**
> （重みなしでは基準以下のまま）——すなわち大面積の疎居住層でこそ
> 「転移の鋭さ」が識別に効く、という設計ベース推測ならではの知見。

## 1. データと重み

- 本番バッチ（27,710点試行）の done 16,474点。9特徴すべて完備（NaN除外 0件）
- design_weight は **cos(lat)バグ修正後**の式で実現サンプルに再計算:
  `w_h = 層hの推定全体セル数 / 層hの試行数`（層内一定）。
  empty(failed)は無作為欠測でなく「Overtureに何も無いセル」という構造カテゴリとして
  分離し、doneの重みには繰り入れない（`build_dataset.py` docstring参照）
- empty率は層別に大きく異なる: **very_low 67.5% vs low 14.3%**。
  最高はMelanesia very_low 93.9%、最低はWestern Europe low 0.0%
  （`stratum_realized.csv`）。この差が実態（真の無人）か
  Overture未記載かの切り分けは §4 のバイアス検証で行う

## 2. 結果

![breakdown curve](breakdown_curve.png)
![all features](contribution_all_features.png)
![weighting robustness](weighting_robustness.png)

### 2.1 全域で固有情報を持つ特徴（rural帯、重み付き全体）

| 特徴 | 全体寄与 | 判定 |
|---|---|---|
| ΔD | 12.2% | 基準超・最大 |
| Δα | 10.2% | 基準超 |
| s_Λ | 8.7% | 基準超 |
| γ | 7.9% | 基準超（ただし密度依存、§2.2） |
| Λ̄ | 6.9% | 基準超 |
| d | 6.4% | 基準超 |
| S_α | 2.3% | **冗長** |
| W_trans | 2.0% | **冗長** |
| r_crit | 1.9% | **冗長** |

移動窓で見ると d は全窓で 9〜10%——**rural帯の内部では密度は崩壊しない**。
exp01 の d\*_sparse ≈ 0.0013（これより疎でダイナミクスが密度を上回る）は
本サンプルでは観測されない（どの窓でも d ≫ γ, W_trans）。

### 2.2 γ の立ち上がりと design_weight の効果

- γ は d < 2×10⁻³ で 4.5〜5%（基準以下）、d > 2×10⁻³ で 6〜7.5%（基準超）に遷移
- **この遷移は重み付きでのみ出現**（重みなしは全域 ~4%）。重みは推定全体セル数に
  比例するので、γ の固有情報は「セル数の多い＝広大な疎居住層」で強いことを意味する
- 窓ごとの振動が大きい（窓内のサブリージョン構成が変わるため）。
  サブリージョン層別の追試が次の課題

### 2.3 exp01 との食い違いの解釈（正直な注記）

exp01 は疎の極（d~0.0007）で「9特徴ほぼ直交、W_trans/r_crit が主役」だった。
本実験は同じ密度帯で W_trans/r_crit が冗長。指標定義は同一
（`find_r_crit_max_slope` = argmax dG/dr、パイプラインが同じ関数を使用）なので、
差の候補は:

1. **母集団定義**: global_v2 は WSF（既知の集落）アンカーの5分位×22サブリージョン。
   本実験は GHS-SMOD の rural セル一様抽出——「集落があるとは限らない場所」を含む。
   建物数が極端に少ない bbox では percolation 曲線が退化し、W_trans・r_crit が
   互いに（また建物数と）強く相関 → 冗長化する、が最有力仮説
2. **ネットワーク構築差（卒論の制約L3）**: exp01 の曲線は旧リポジトリのパイプライン
   由来。スナップ許容度等の構築パラメータ差が percolation 系指標に効く可能性
3. 除外規則の差: exp01 は percolation 曲線が無い地点を除外（10,068/10,555）。
   本実験の done はグラフが構築できた地点のみで同種のフィルタだが閾値挙動が違う

**論文への含意**: 「疎ではダイナミクスが主役」という単純な物語は成立しない。
代わりに (a) rural帯の識別の主役は質量分布系（ΔD, Δα）と空隙系（Λ̄, s_Λ）、
(b) γ は面積加重でのみ疎側の中〜上部で効く、(c) 密度は rural帯**内部**では
崩壊しない（exp01の崩壊は密側の極 d>0.06 でのみ確認済み）、という
より精密な三部構成になる。

## 3. 除外・頑健性

- NaN除外: 0件（16,474点すべて9特徴完備）
- 重み付き vs 重みなし: d はほぼ不変（頑健）。γ のみ重みで結論が変わる（§2.2）
- ブートストラップ95%CI（B=100、窓内再抽出）を全窓で計算済み
  （`window_contributions.csv` の `*_lo`/`*_hi` 列）

## 4. 未完了: Overtureカバレッジバイアス検証（投稿前必須）

`overture_bias_check.py` 準備済み。GHS-BUILT-S（衛星由来、Overtureと独立）との
突き合わせで「empty＝真の無人 vs 未記載」を層別に分解する。
**GHS-BUILT-S ラスタのダウンロードはユーザーの `!curl` が必要**（スクリプト冒頭の
URL参照。JRCサーバーはエージェントからの直接取得がブロックされるため）。

## 成果物

- `build_dataset.py` / `realized_sample.csv`（16,474行）/ `stratum_realized.csv`（44層）
- `weighted_breakdown.py` / `window_contributions.csv` / `overall_contributions.csv`
- `breakdown_curve.png` / `contribution_all_features.png` / `weighting_robustness.png`
- `overture_bias_check.py`（実行待ち）
