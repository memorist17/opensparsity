# Sampling: DEGURBA層化サンプリングによる候補地点リスト生成

`experiments/exp04_degurba_census/`で設計した「134万地点のB1センサス」の代替案——
**DEGURBA（人口密度の国際標準分類）でLow/Very low density ruralに母集団を定義し、
22サブリージョン×2クラス=44層で層化抽出する**——を実装したパイプライン。

再利用可能な独立モジュールとして`experiments/`ではなくここに置く（複数の実験・将来の
再サンプリングから呼び出すことを想定）。

## パイプライン（3ステップ）

```
1. extract_candidates.py   GHS-SMODラスタ(1km) → 2km格子に間引き → class 11/12の候補点を無作為抽出
        ↓ candidates_raw.csv
2. assign_subregion.py     Overtureの国境界(divisions theme)で国コード判定 → UN 22サブリージョンに変換
        ↓ candidates_with_subregion.csv
3. stratified_sample.py    44層(22サブリージョン×2クラス)から層化抽出、design_weightを算出
        ↓ final_sample.csv, final_sample_stratum_report.csv
```

### なぜこの3分割か

- **GHS-SMOD**（既にダウンロード済み、18MB）だけで「密度クラス」は完結する。国境界の
  判定に別データセット（Natural Earth等）を新規に持ち込まず、**既存パイプラインが
  既に使っているOverture Maps（divisions theme）を再利用**する設計判断（`assign_subregion.py`）
- 2km格子への変換は**単純間引き（`band[::2, ::2]`）**。多数決等の集約はしない
  ——集約方法によってクラスごとの候補数が大きく変わってしまうため（実測: class12は
  多数決で617万→93万まで減る一方、単純間引きなら154万を保てる）。詳細はexp04参照
- 全世界の候補点（class11=3,392万、class12=154万@2km格子）に国判定をかけるのは重いため、
  先に無作為抽出（既定30万件/クラス）してから国判定する。最終的に必要なのは
  44層×600〜800点≈3万点なので、30万件/クラスは20倍以上の余裕がある

## design_weightについて

Horvitz-Thompson型: `design_weight = (層の推定全体セル数 / 層から実際に抽出した点数) * cos(lat)`

- 「層の推定全体セル数」は `extract_candidates.py` が記録した抽出率（クラスごとに一定）から
  逆算する（層別に国判定をかけ直して全数を数えるのは重すぎるため、無作為抽出である前提で
  推定する）
- `cos(lat)`項は緯度が高いほど1kmグリッド1マスの実面積が小さくなる歪みの補正
  （旧リポジトリのglobal_v2設計と同じ考え方、`configs/global_v2_N100_clean.yaml`参照）

## 候補プールが層あたり目標に届かない場合

`stratified_sample.py`は、層の候補が目標点数（既定700）に届かない場合はある分だけ全部使う
（global_v2の`n_strata_all_pop`と同じ扱い）。出力の`*_stratum_report.csv`の
`pool_exhausted`列で該当層を確認できる。

## 使い方

```bash
cd opensparsity
.venv/bin/python sampling/extract_candidates.py \
    --raster ~/Downloads/ghs_smod_2025/GHS_SMOD_E2025_GLOBE_R2023A_54009_1000_V2_0.tif \
    --out sampling/candidates_raw.csv --n-per-class 300000 --seed 42

.venv/bin/python sampling/assign_subregion.py \
    --candidates sampling/candidates_raw.csv \
    --out sampling/candidates_with_subregion.csv

.venv/bin/python sampling/stratified_sample.py \
    --candidates sampling/candidates_with_subregion.csv \
    --out sampling/final_sample.csv --n-per-stratum 700 --seed 42
```

`final_sample.csv`は`name`/`lat`/`lon`列を含むため、変換不要でそのまま
`ops run --locations sampling/final_sample.csv --out results/` に投入できる
（`_load_locations`が読めることは動作確認済み）。

## 結果（2026-07-10, seed=42）

- 候補抽出: class 11（very_low_density_rural）30万件・class 12（low_density_rural）30万件
  を無作為抽出（全体は2km格子でそれぞれ3,392万・154万セル）
- 国/サブリージョン判定: 60万件中56.3万件（93.8%）が22サブリージョンに割当成功。
  漏れの大半はAQ（南極、サブリージョン無し、想定内）
- 層化抽出: **総サンプル27,710点**。44層中39層は目標700点を達成、
  **5層は候補プール不足でそのまま全部使用**（Micronesia low=21・very_low=3、
  Polynesia low=23・very_low=6、Caribbean very_low=357）——太平洋の小島嶼国は
  そもそも土地面積が小さく、707点は無理に集められない。global_v2の
  `n_strata_all_pop`と同じ現象で、想定内・対応済み
- 出力: [final_sample.csv](final_sample.csv)（27,710行）、
  [final_sample_stratum_report.csv](final_sample_stratum_report.csv)（層別内訳）

## 技術的なつまずき（後で同じことをする人向け）

- DuckDB spatialの`ST_Contains`結合はインデックス無しだと60万点×219国ポリゴンで
  **30分以上かかっても終わらなかった**（途中でkill）。原因は2つ:
  1. 国単位に`ST_Union_Agg`で結合していた（複雑な海岸線の島嶼国でGEOS演算が非常に重い）
     → 行単位のまま結合し`QUALIFY ROW_NUMBER()...=1`で重複除去する方式に変更
  2. RTreeインデックスを使っていなかった → `CREATE INDEX ... USING RTREE (geom)`で解決。
     ただし**`CAST(geometry AS GEOMETRY)`をしないと「RTree indexes can only be created
     over GEOMETRY columns」エラーになる**（Overture divisionsのgeometry列は
     `GEOMETRY('OGC:CRS84')`という型パラメータ付きで、素のGEOMETRY型と区別される）
  - 修正後は数十秒で完了した

## 本番実行について

`final_sample.csv`ができても、**`ops run`による実際のOverture取得・指標計算（約3万点、
3台で1.6日規模）はユーザーの明示的なGOを得てから実行する**
（[technical_notes.md](../docs/technical_notes.md) §5の運用ルール）。
