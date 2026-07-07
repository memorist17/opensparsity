# opensparsity

都市空間の Open-Sparsity 指標パイプライン。任意の緯度経度について Overture Maps から建物・道路を取得し、
ラスタ化・ネットワーク構築・指標計算（Lacunarity / MFA / Percolation / 追加指標）を行う。

**成果物は 1地点 = 1画像 + SQLite の1行だけ**（中間ファイルなし）:

```
results/
├── results.db            # 全地点の指標・曲線・処理ステータス（これが唯一の数値成果物）
└── images/
    └── {lat}_{lon}.png   # 建物・道路ラスタ + ネットワークのオーバーレイ（メタデータ埋込み）
```

旧リポジトリ `251229_repro_apple`（1地点 = 7ファイル・8〜15MB）からの移植・再設計版。
1地点あたり約 0.1〜0.8MB + db 数 KB。

## セットアップ

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e .
```

## 使い方

```bash
# 実行（クラッシュ・中断しても再実行すれば処理済み地点をスキップして続きから）
.venv/bin/ops run --locations locations.yaml --out results/

# 並列バッチ（同じ db に安全に書ける / WAL モード）
.venv/bin/ops run --locations all.csv --out results/ --start 0    --end 2500 &
.venv/bin/ops run --locations all.csv --out results/ --start 2500 --end 5000 &

# 進捗
.venv/bin/ops status --out results/

# 分析用に CSV へ
.venv/bin/ops export --out results/ --csv metrics.csv
```

地点リストは YAML（`{locations: [{name, lat, lon}, ...]}` / 旧形式 `coords: [lat, lon]` も可）
または CSV（`lat, lon[, name]` 列）。

## 設計

- **モジュールは相互非依存**: `fetch` / `project` / `raster` / `network` / `indicators/*` は
  それぞれ単独で import して使える。組み合わせるのは `pipeline.py` だけ
- **results.db が真実源**: `locations`（指標＋status）と `curves`（percolation / MFA / lacunarity 曲線）。
  曲線を残すのは、新しい指標を思いついたとき再フェッチせずに db だけで追加計算するため
- **行にはコード版と Overture リリース版を記録**: どの実装・どのデータで計算した値か常に追跡可能
- **再開**: 主キー (lat, lon) の UPSERT + status。`--force` で再計算

## 計算実装について

計算コアは旧リポジトリで最適化・検証済みのものをそのまま移植:
- ネットワーク構築: STRtree / cKDTree（旧全走査実装とグラフがビット単位一致することを検証済み）
- Percolation: scipy Dijkstra + 最小全域森フィルタ（旧 networkx 実装と全しきい値一致を7地点で検証済み）
- Overture の古いリリースは S3 から消えるため、fetch が "No files found" になったら
  `fetch.py` の `OVERTURE_RELEASE` を更新すること

## 参考実行時間（Apple Silicon, 2km² / 1m px）

フェッチ約 100〜120 秒（地点によらずほぼ一定）＋ 計算 5〜35 秒（建物ノード数の2乗で増加、
建物 14,000 ノードのキベラで 35 秒）。
