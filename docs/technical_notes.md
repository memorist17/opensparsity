# 技術ノート（2026-07-08 実装分）

`opensparsity`（[memory: opensparsity-new-repo]）の実装上の決定事項・高速化・運用ルールを
まとめる。個々の変更の詳細はコミット履歴（`git log`）を参照。

## 1. アーキテクチャ

- **設計原則**: 1地点 = オーバーレイPNG1枚（`results/images/{lat:.4f}_{lon:.4f}.png`）+
  SQLite（`results/results.db`）1行。中間ファイル（npy/graphml/地点別CSV）は書かない
  - **Why**: 旧リポジトリ（`251229_repro_apple`）は1地点7ファイル・8〜15MBで、
    1万地点=150GB級になり全球スケール（134万地点想定のB1センサス）で破綻する
- パッケージは `src/opensparsity/`（fetch/project/raster/network/indicators/render/store/pipeline/cli）
  で相互非依存、pyproject化済みでsys.pathハックなし
- CLI: `ops run --locations X --out results/`。(lat,lon)主キーのUPSERT+statusで**再開可能**、
  `--force`で強制再計算。`ops status` / `ops export --csv`
- DBには指標12種＋曲線3種（percolation/mfa_spectrum/lacunarity, JSON）＋code_version＋
  overture_releaseを保存。**曲線を残すのは新指標の後付け計算を再フェッチ無しで可能にするため**
- 検証済み: 単体テスト4件、E2Eで旧リポジトリと指標が一致（最大差1.8e-15）、再開動作確認済み

## 2. 研究上の確定事項（変更不可の設計判断）

- **パーコレーションは道路ネットワーク媒介**——著者の独自性であり変更禁止
- **r_crit の正定義は論文表1の `argmax dG/dr`**（旧実装の `G=0.5交差`は不使用、fb7a4ea/fc00eefで修正）
- **`density` は Fleischmann Index-of-Elements 命名で "Covered Area Ratio (GSI)"**——建物footprintの
  画素占有率であり、建物数密度とは別物（[Fleischmann, Romice & Porta 2020, EPB](https://journals.sagepub.com/doi/10.1177/2399808320910444)
  のIndex/Element分離に準拠。同記事の平易版: https://martinfleischmann.net/confused-terminology-in-urban-morphology/）
- **2026-07-10、密度系の追加指標3種を`pipeline.py`に追加**（既存の`density`はそのまま維持、値は変更なし）:
  - `building_count_density`（建物数/km²）
  - `building_footprint_mean_m2` / `building_footprint_median_m2`（建物footprintの平均・中央値面積）
  - `road_length_density`（道路網長km/km²、Spacemateの N に相当）
  - **Why**: `density`(GSI)だけでは「大きい建物少数」と「小さい建物多数」を区別できない。
    いずれもフェッチ済みgeometryの集計のみで追加コストほぼゼロ（既存の10,050地点=exp01の
    データセットには無い。134万地点の本番からは全地点で取得される）
  - **FSI（容積率）は採用しない**: Overtureの`height`/`num_floors`欠損率が高すぎる
    （横浜での実測: height 0.8%, num_floors 3.9%。global-scaleでは使い物にならない）
  - 実測値（横浜, density=0.2176）: building_count_density=1422.5/km², footprint_mean=153.1m²,
    footprint_median=75.9m²（平均>中央値=右に歪んでいる=大きい建物が少数混在）, road_length_density=33.4km/km²

## 3. 高速化（07-08実施）

| 変更 | 効果 | コミット |
|---|---|---|
| MFAを整数積分画像＋質量ヒストグラム化 | 5.5〜13倍高速化 | 3c4c4f2 |
| percolation (shortest_path) をscipy実装に置換 | 大幅高速化 | 0f8a653, 251229側は032ae5c |
| ネットワーク構築の空間インデックス化 | 大幅高速化 | 032ae5c |
| Dijkstraのscipy化＋フェッチ並列化 | 地点あたり356s→229s（横浜） | fb0bc5f |
| 一括プリフェッチ機構（`ops prefetch` / `--cache` / `--no-image` / `ops merge`） | バッチ処理の再フェッチ削減 | 88ce4d6 |
| prefetchのparquet書き出しをduckdb COPY化 | pyarrow非依存に | 74e5f1a |

## 4. 運用・デプロイ

- **実測ピークRSS**: 疎地点 1.2GB / 横浜級 5.2GB
- **並列度**: 多プロセスで回すときは `config.yaml` の `analysis.n_jobs=1` にしてプロセス並列へ寄せる。
  B1疎スイープなら6並列可、全Quintile混在なら2並列まで（メモリ抑制、fc00eef付近で`n_jobs`をconfig化）
- **`ssh mini`**（M系Mac, 16GB/8コア/空き100GB, macOS 26）にopensparsity一式をデプロイ済み
  （`~/dev/OS/opensparsity`, uv+Python3.12, テスト・実フェッチ確認済み）。mini↔Mac間で指標の一致確認済み
- **`ssh wsl`** にも接続可能。global_v2の曲線データ転送済み（旧リポ`outputs/real_world_global_v2/`）
- コード更新時はrsync（`--exclude .venv/results`）で再同期
- Overtureリリース切れ時は `src/opensparsity/fetch.py` の `OVERTURE_RELEASE` を更新
  （2026-07-07時点で `2026-06-17.0` に更新済み、旧リポジトリと同じ運用）

## 5. 運用ルール: 重い処理はGO待ち

**重い計算（バッチ処理・全球スイープ・複数台デプロイ後の一括実行など）を開始する前に、
必ずユーザーの明示的なGOを待つ。** 計画・見積り・準備までは進めてよいが、実行コマンドは
承認後に叩く。

- **Why**: 07-08時点でB1センサス（134万地点想定）やmini/WSLでの並列実行は
  「インフラは完成しているが未起動」の状態。長時間・大容量・複数台にまたがる処理を
  無断で開始すると、ユーザーの意図と異なるリソース消費や、既存の他ジョブとの競合
  （mini上には他プロジェクトのpythonプロセスが常駐している）を招く
- **How to apply**: `ops run` を数百〜数万地点規模、複数プロセス、複数ホストで回す前には
  必ず一度立ち止まって確認する。少数地点（数件〜数十件、単一プロセス、動作確認目的）の
  実行は都度確認不要

## 6. 既知の未解決事項

- exp03カタログのK=6は感度分析未実施（[exp03 REPORT.md](../experiments/exp03_catalog/REPORT.md) §4）
- `reps2_run.log` でskipされた3件の原因未記録
- B1全球センサス（134万地点）は`docs/related_work_and_storyline.md`で「進行中」と
  記述されているが、実際には**地点リスト生成・実行のいずれも未着手**（2026-07-08時点、
  [NEXT_STEPS.md](../NEXT_STEPS.md)参照）
