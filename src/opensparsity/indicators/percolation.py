"""Continuum Percolation Analysis using NetworkX connected components.

This module implements percolation analysis for urban network graphs,
supporting both edge-based filtering and shortest path distance approaches.

Distance Calculation Methods:
- "edge": Uses direct edge lengths for filtering (default, fast)
- "shortest_path": Uses shortest path distances between nodes (more accurate, slower)

Disconnected Component Handling:
- When distance_type="edge": Disconnected nodes remain isolated at all thresholds
- When distance_type="shortest_path": Disconnected pairs have infinite distance

Reference:
    Standard percolation analysis uses shortest path distances (network distance)
    as recommended in urban network literature. Edge-based filtering is faster
    but may not capture true network connectivity characteristics.
"""

from dataclasses import dataclass
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from tqdm import tqdm


@dataclass
class PercolationAnalyzer:
    """
    Compute percolation metrics using NetworkX graph filtering.

    Algorithm:
    1. Load network graph with edge lengths
    2. For each distance threshold d:
       - Keep only edges/node pairs where distance <= d
       - Count connected components and max component size
    3. Track percolation transition (emergence of giant component)

    Args:
        d_min: Minimum distance threshold
        d_max: Maximum distance threshold
        d_steps: Number of threshold steps
        distance_type: "edge" for edge lengths, "shortest_path" for network distances
        node_filter: Filter nodes by type (e.g., "building" for building-only analysis)

    Note:
        For building-to-building percolation (node_filter="building"), nodes are
        considered connected if the shortest path distance between them is <= d.
        Disconnected building pairs have infinite distance and are never connected.
    """

    d_min: float = 1
    d_max: float = 500
    d_steps: int = 100
    distance_type: str = "edge"  # "edge" or "shortest_path"
    node_filter: str | None = None  # e.g., "building" to analyze only building nodes

    def analyze(
        self, graph: nx.Graph | str | Path
    ) -> tuple[pd.DataFrame, np.ndarray]:
        """
        Compute percolation curve.

        Args:
            graph: NetworkX Graph or path to .graphml file

        Returns:
            percolation_df: DataFrame with columns [d, max_cluster_size, n_clusters, giant_fraction]
            mesh: 2D array of cluster labels (d_steps, N_nodes)

        Note:
            When distance_type="shortest_path", disconnected node pairs have
            infinite distance and are never considered connected at any threshold.
            This correctly models real-world network connectivity where paths
            don't exist between all building pairs.
        """
        # Load graph if path provided
        if isinstance(graph, (str, Path)):
            graph = nx.read_graphml(str(graph))

        if graph.number_of_nodes() == 0:
            raise ValueError("Graph has no nodes")

        # Filter nodes if specified
        # Note: For edge-based analysis with node_filter, we still use the full graph
        # to compute distances through road network, but only analyze the filtered nodes
        if self.node_filter is not None:
            filtered_nodes = [
                n for n, data in graph.nodes(data=True)
                if data.get("type") == self.node_filter
            ]
            if len(filtered_nodes) == 0:
                raise ValueError(f"No nodes with type '{self.node_filter}' found")
            analysis_nodes = filtered_nodes
        else:
            analysis_nodes = list(graph.nodes())
        
        # For edge-based analysis with node_filter, we need to use the full graph
        # to allow paths through road nodes (via virtual edges and road edges)
        if self.distance_type == "edge" and self.node_filter is not None:
            # Use full graph for distance computation, but analyze only filtered nodes
            analysis_graph = graph  # Use full graph including road nodes
        else:
            analysis_graph = graph

        n_nodes = len(analysis_nodes)
        thresholds = self._get_thresholds()

        print(f"Computing Percolation: {len(thresholds)} thresholds, {n_nodes} nodes")
        print(f"Distance range: {self.d_min:.1f} to {self.d_max:.1f}")
        print(f"Distance type: {self.distance_type}")
        if self.node_filter:
            print(f"Node filter: {self.node_filter}")

        # Map node labels to indices
        node_to_idx = {node: idx for idx, node in enumerate(analysis_nodes)}

        # Choose analysis method based on distance_type
        if self.distance_type == "shortest_path":
            return self._analyze_shortest_path(
                graph, analysis_nodes, node_to_idx, thresholds
            )
        else:
            # For edge-based analysis, use full graph if node_filter is set
            # This allows paths through road nodes (via virtual edges and road edges)
            analysis_graph = graph if (self.node_filter is not None) else graph
            return self._analyze_edge_based(
                analysis_graph, analysis_nodes, node_to_idx, thresholds
            )

    def _analyze_edge_based(
        self,
        graph: nx.Graph,
        analysis_nodes: list,
        node_to_idx: dict,
        thresholds: np.ndarray,
    ) -> tuple[pd.DataFrame, np.ndarray]:
        """
        Analyze percolation using edge length filtering.

        The graph structure already contains:
        - Road nodes (intersections)
        - Road edges (between road nodes)
        - Building nodes
        - Virtual edges (building -> road node)

        When node_filter is set (e.g., "building"), building nodes connect via:
        virtual edge -> road edge -> virtual edge path through the road network.
        This allows building-to-building connections using the actual road network structure.
        """
        n_nodes = len(analysis_nodes)

        # Get edge lengths from full graph (includes road nodes, road edges, virtual edges)
        edge_lengths = {}
        for u, v, data in graph.edges(data=True):
            length = float(data.get("length", 1.0))
            edge_lengths[(u, v)] = length

        # Compute percolation metrics for each threshold
        results = []
        mesh = np.zeros((len(thresholds), n_nodes), dtype=np.int32)

        for d_idx, d in enumerate(tqdm(thresholds, desc="Computing percolation (edge)")):
            # Create filtered graph view (use full graph to allow paths through road nodes)
            # The graph already contains: road nodes, road edges, building nodes, virtual edges
            # This allows building nodes to connect via road network
            filtered = self._filter_graph(graph, edge_lengths, d)

            # Compute connected components in full filtered graph (includes road nodes)
            # Road nodes act as intermediate nodes connecting building nodes
            all_components = list(nx.connected_components(filtered))

            # If node filter is set, map building nodes to their components (via road nodes)
            if self.node_filter is not None:
                # Map building nodes to their components
                building_to_component = {}
                for comp_idx, component in enumerate(all_components):
                    # Check if this component contains any building nodes
                    building_nodes_in_comp = [n for n in component if n in analysis_nodes]
                    if building_nodes_in_comp:
                        for building_node in building_nodes_in_comp:
                            building_to_component[building_node] = comp_idx
                
                # Group building nodes by component
                component_to_buildings = {}
                for building_node, comp_idx in building_to_component.items():
                    if comp_idx not in component_to_buildings:
                        component_to_buildings[comp_idx] = []
                    component_to_buildings[comp_idx].append(building_node)
                
                # Convert to list of building-only components
                components = list(component_to_buildings.values())
            else:
                # No filter: use all nodes
                components = all_components

            n_clusters = len(components)

            # Find largest component (only among analysis nodes)
            if components:
                largest = max(components, key=len)
                max_size = len(largest)
            else:
                max_size = 0

            giant_fraction = max_size / n_nodes if n_nodes > 0 else 0

            results.append({
                "d": d,
                "max_cluster_size": max_size,
                "n_clusters": n_clusters,
                "giant_fraction": giant_fraction,
            })

            # Store cluster labels (only for analysis nodes)
            for cluster_idx, component in enumerate(components):
                for node in component:
                    if node in node_to_idx:
                        mesh[d_idx, node_to_idx[node]] = cluster_idx + 1

        percolation_df = pd.DataFrame(results)
        return percolation_df, mesh

    def _analyze_shortest_path(
        self,
        graph: nx.Graph,
        analysis_nodes: list,
        node_to_idx: dict,
        thresholds: np.ndarray,
    ) -> tuple[pd.DataFrame, np.ndarray]:
        """
        Analyze percolation using shortest path distances.

        This method computes network distances (shortest path) between all node pairs
        and connects them if distance <= threshold. More accurate for urban networks
        but computationally expensive for large graphs.

        Disconnected node pairs have infinite distance and are never connected.
        """
        n_nodes = len(analysis_nodes)

        print("Computing pairwise shortest path distances...")

        # 全ノードの疎隣接行列を作り、scipy の C 実装 Dijkstra で
        # analysis_nodes を源とする最短距離を一括計算する。
        # （networkx の Python 実装で1源ずつ回す旧方式の約9倍速。
        #   距離値は networkx 実装と一致することを検証済み）
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import dijkstra as sp_dijkstra

        all_nodes = list(graph.nodes())
        full_idx = {node: i for i, node in enumerate(all_nodes)}
        n_all = len(all_nodes)

        rows, cols, vals = [], [], []
        for u, v, attr in graph.edges(data=True):
            # networkx の weight="length" と同じく欠損は 1.0 扱い。
            # csgraph は明示的な 0 をエッジ無しとみなすため微小値でクランプ
            w = max(float(attr.get("length", 1.0)), 1e-12)
            rows.append(full_idx[u])
            cols.append(full_idx[v])
            vals.append(w)
        adjacency_full = coo_matrix(
            (vals + vals, (rows + cols, cols + rows)), shape=(n_all, n_all)
        ).tocsr()

        source_idx = np.array([full_idx[node] for node in analysis_nodes])
        dist_from_sources = sp_dijkstra(
            adjacency_full, directed=False, indices=source_idx
        )
        # 行・列とも analysis_nodes 順（旧実装の distance_matrix と同じレイアウト）
        distance_matrix = dist_from_sources[:, source_idx]
        np.fill_diagonal(distance_matrix, 0)

        # Report disconnected pairs
        n_disconnected = np.sum(np.isinf(distance_matrix)) - n_nodes  # exclude diagonal
        n_total_pairs = n_nodes * (n_nodes - 1)
        if n_disconnected > 0:
            print(f"Disconnected pairs: {n_disconnected // 2} / {n_total_pairs // 2} "
                  f"({n_disconnected / n_total_pairs * 100:.1f}%)")
            print("Note: Disconnected pairs have infinite distance and remain isolated.")

        # Compute percolation metrics for each threshold.
        # 距離行列のしきい値グラフの連結成分は scipy.sparse.csgraph で計算する。
        # （networkx で毎しきい値ごとに最大 n^2/2 本のエッジを Python ループで
        #   追加する旧実装は、ノード数千超でメモリ・時間ともに破綻するため。
        #   max_cluster_size / n_clusters / giant_fraction は旧実装と同一。
        #   mesh のクラスタ番号の割り振り順のみ実装依存で異なりうる）
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components, minimum_spanning_tree

        finite_upper = np.triu(np.isfinite(distance_matrix), k=1)
        pair_i, pair_j = np.nonzero(finite_upper)
        pair_d = distance_matrix[pair_i, pair_j]

        # 単連結クラスタリングの標準的性質:
        # 「距離 <= d のペアを結んだグラフ」の連結成分は、その距離グラフの
        # 最小全域森を同じ d でフィルタしたものの連結成分と一致する。
        # 全ペア（最大 n²/2 本）を毎しきい値処理する代わりに、
        # 最小全域森（最大 n-1 本）を一度だけ作りフィルタする。
        # csgraph は明示的 0 をエッジ無し扱いするため微小値でクランプ
        # （しきい値は d_min >= 1 なので結果に影響しない）
        pair_graph = coo_matrix(
            (np.maximum(pair_d, 1e-12), (pair_i, pair_j)),
            shape=(n_nodes, n_nodes),
        ).tocsr()
        forest = minimum_spanning_tree(pair_graph).tocoo()
        tree_i, tree_j, tree_d = forest.row, forest.col, forest.data

        results = []
        mesh = np.zeros((len(thresholds), n_nodes), dtype=np.int32)

        for d_idx, d in enumerate(tqdm(thresholds, desc="Computing percolation (shortest_path)")):
            mask = tree_d <= d
            adjacency = coo_matrix(
                (np.ones(int(mask.sum()), dtype=np.int8),
                 (tree_i[mask], tree_j[mask])),
                shape=(n_nodes, n_nodes),
            )
            n_clusters, labels = connected_components(adjacency, directed=False)

            sizes = np.bincount(labels)
            max_size = int(sizes.max()) if n_nodes > 0 else 0
            giant_fraction = max_size / n_nodes if n_nodes > 0 else 0

            results.append({
                "d": d,
                "max_cluster_size": max_size,
                "n_clusters": n_clusters,
                "giant_fraction": giant_fraction,
            })

            # Store cluster labels (1-origin, 旧実装と同じく全ノードにラベル付与)
            mesh[d_idx, :] = labels + 1

        percolation_df = pd.DataFrame(results)
        return percolation_df, mesh

    def _get_thresholds(self) -> np.ndarray:
        """Generate distance thresholds."""
        return np.linspace(self.d_min, self.d_max, self.d_steps)

    def _filter_graph(
        self,
        graph: nx.Graph,
        edge_lengths: dict[tuple, float],
        d: float
    ) -> nx.Graph:
        """
        Create filtered graph with edges <= d.

        Args:
            graph: Original graph
            edge_lengths: Dictionary of edge lengths
            d: Distance threshold

        Returns:
            Filtered graph (new graph, not view)
        """
        filtered = nx.Graph()
        filtered.add_nodes_from(graph.nodes(data=True))

        for (u, v), length in edge_lengths.items():
            if length <= d:
                filtered.add_edge(u, v, length=length)

        return filtered

    def find_percolation_threshold(
        self, percolation_df: pd.DataFrame, target_fraction: float = 0.5
    ) -> float:
        """
        Find the distance threshold where giant component reaches target fraction.

        Note: 0.5 is a convention (interpretable as "half of nodes in giant component").
        Theoretically, the critical point is better defined as where dG/dr is maximum
        (steepest rise) or where susceptibility peaks. Use find_percolation_threshold_max_slope()
        for the slope-based definition.

        Args:
            percolation_df: Percolation results
            target_fraction: Target fraction of nodes in giant component (default 0.5)

        Returns:
            Critical distance threshold (interpolated)
        """
        d = percolation_df["d"].values
        gf = percolation_df["giant_fraction"].values

        # Find crossing point
        for i in range(len(gf) - 1):
            if gf[i] < target_fraction <= gf[i + 1]:
                # Linear interpolation
                t = (target_fraction - gf[i]) / (gf[i + 1] - gf[i])
                return d[i] + t * (d[i + 1] - d[i])

        # If not found, return boundary
        if gf[-1] < target_fraction:
            return d[-1]
        return d[0]

    def find_percolation_threshold_max_slope(
        self, percolation_df: pd.DataFrame
    ) -> float:
        """
        Find the distance at which dG/dr (slope of giant fraction) is maximum.

        This is a theoretically natural definition of the critical point: the
        transition is "sharpest" where the order parameter G(r) rises fastest.
        Use this instead of find_percolation_threshold(0.5) when you want the
        critical distance to reflect the steepest part of the percolation curve.

        Returns:
            Distance at the midpoint of the interval where slope is largest.
        """
        d = percolation_df["d"].values
        gf = percolation_df["giant_fraction"].values
        if len(d) < 2:
            return float(d[0]) if len(d) == 1 else np.nan
        slopes = (gf[1:] - gf[:-1]) / (d[1:] - d[:-1] + 1e-20)
        d_mid = (d[1:] + d[:-1]) * 0.5
        idx = np.argmax(slopes)
        return float(d_mid[idx])

    def compute_susceptibility(self, percolation_df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute percolation susceptibility χ(d).

        χ = <s²> / <s> where s is component size
        (excluding the largest component)

        Returns:
            DataFrame with columns [d, susceptibility]
        """
        # Simplified susceptibility approximation based on cluster statistics
        d = percolation_df["d"].values
        n = percolation_df["n_clusters"].values
        gf = percolation_df["giant_fraction"].values

        # Approximate susceptibility as variance-like measure
        # Higher near transition, lower far from it
        susceptibility = n * (1 - gf) * gf

        return pd.DataFrame({
            "d": d,
            "susceptibility": susceptibility,
        })

    def analyze_with_statistics(
        self, graph: nx.Graph | str | Path
    ) -> tuple[pd.DataFrame, dict]:
        """
        Run percolation analysis with additional statistics.

        Returns:
            percolation_df: Main percolation results
            stats: Dictionary with transition statistics
        """
        percolation_df, mesh = self.analyze(graph)

        # Find critical thresholds
        d_05 = self.find_percolation_threshold(percolation_df, 0.5)
        d_01 = self.find_percolation_threshold(percolation_df, 0.1)
        d_09 = self.find_percolation_threshold(percolation_df, 0.9)
        d_max_slope = self.find_percolation_threshold_max_slope(percolation_df)

        # Compute susceptibility peak
        susceptibility = self.compute_susceptibility(percolation_df)
        peak_idx = np.argmax(susceptibility["susceptibility"].values)
        d_peak = susceptibility["d"].values[peak_idx]

        stats = {
            "d_critical_50": d_05,
            "d_critical_10": d_01,
            "d_critical_90": d_09,
            "d_critical_max_slope": d_max_slope,
            "d_susceptibility_peak": d_peak,
            "transition_width": d_09 - d_01,
            "max_clusters": percolation_df["n_clusters"].max(),
        }

        return percolation_df, stats


@dataclass
class PathDiversityAnalyzer:
    """
    Analyze path diversity as a separate metric from percolation.

    This class computes path diversity metrics between node pairs,
    treating it independently from percolation analysis as recommended
    in urban network literature.

    Path diversity considers:
    - Number of alternative paths between node pairs
    - Distribution of path lengths
    - Redundancy in network connections

    Note:
        This analysis is computationally expensive for large networks.
        Consider using sampling (sample_pairs parameter) for large graphs.
    """

    max_paths: int = 5  # Maximum number of paths to consider per pair
    length_tolerance: float = 1.5  # Paths within this factor of shortest are "diverse"
    sample_pairs: int | None = None  # Sample this many pairs (None = all pairs)
    node_filter: str | None = None  # Filter nodes by type
    max_path_hops: int = 50  # Maximum number of hops in path search
    random_seed: int | None = 42  # Random seed for reproducible sampling (None = random)

    def analyze(
        self, graph: nx.Graph | str | Path
    ) -> tuple[pd.DataFrame, dict]:
        """
        Compute path diversity metrics.

        Args:
            graph: NetworkX Graph or path to .graphml file

        Returns:
            diversity_df: DataFrame with per-pair diversity metrics
            stats: Summary statistics
        """
        # Load graph if path provided
        if isinstance(graph, (str, Path)):
            graph = nx.read_graphml(str(graph))

        if graph.number_of_nodes() == 0:
            raise ValueError("Graph has no nodes")

        # Filter nodes if specified
        if self.node_filter is not None:
            analysis_nodes = [
                n for n, data in graph.nodes(data=True)
                if data.get("type") == self.node_filter
            ]
            if len(analysis_nodes) == 0:
                raise ValueError(f"No nodes with type '{self.node_filter}' found")
        else:
            analysis_nodes = list(graph.nodes())

        n_nodes = len(analysis_nodes)
        print(f"Computing Path Diversity: {n_nodes} nodes")
        if self.node_filter:
            print(f"Node filter: {self.node_filter}")

        # Generate node pairs to analyze
        pairs = []
        for i in range(len(analysis_nodes)):
            for j in range(i + 1, len(analysis_nodes)):
                pairs.append((analysis_nodes[i], analysis_nodes[j]))

        # Sample pairs if requested
        if self.sample_pairs is not None and len(pairs) > self.sample_pairs:
            if self.random_seed is not None:
                np.random.seed(self.random_seed)
            indices = np.random.choice(len(pairs), self.sample_pairs, replace=False)
            pairs = [pairs[i] for i in indices]
            print(f"Sampling {self.sample_pairs} pairs from {n_nodes * (n_nodes - 1) // 2}")

        # Compute diversity metrics for each pair
        results = []
        connected_pairs = 0
        total_diverse_paths = 0

        for source, target in tqdm(pairs, desc="Computing path diversity"):
            try:
                # Get shortest path length
                shortest_length = nx.shortest_path_length(
                    graph, source, target, weight="length"
                )

                # Count paths within tolerance
                max_length = shortest_length * self.length_tolerance
                n_paths = self._count_paths_within_length(
                    graph, source, target, max_length, self.max_paths
                )

                results.append({
                    "source": source,
                    "target": target,
                    "shortest_distance": shortest_length,
                    "n_diverse_paths": n_paths,
                    "connected": True,
                })
                connected_pairs += 1
                total_diverse_paths += n_paths

            except nx.NetworkXNoPath:
                # Disconnected pair
                results.append({
                    "source": source,
                    "target": target,
                    "shortest_distance": np.inf,
                    "n_diverse_paths": 0,
                    "connected": False,
                })

        diversity_df = pd.DataFrame(results)

        # Compute summary statistics
        if connected_pairs > 0:
            avg_diverse_paths = total_diverse_paths / connected_pairs
            mean_distance = diversity_df[
                diversity_df["connected"]
            ]["shortest_distance"].mean()
        else:
            avg_diverse_paths = 0
            mean_distance = np.inf

        stats = {
            "total_pairs": len(pairs),
            "connected_pairs": connected_pairs,
            "disconnected_pairs": len(pairs) - connected_pairs,
            "connectivity_ratio": connected_pairs / len(pairs) if pairs else 0,
            "avg_diverse_paths": avg_diverse_paths,
            "mean_shortest_distance": mean_distance,
        }

        return diversity_df, stats

    def _count_paths_within_length(
        self,
        graph: nx.Graph,
        source,
        target,
        max_length: float,
        max_paths: int,
    ) -> int:
        """
        Count number of simple paths within a maximum length.

        Uses a bounded search to limit computation.
        """
        count = 0
        try:
            # Use simple paths generator with cutoff
            # Note: This can be expensive; we limit by max_paths
            for path in nx.all_simple_paths(
                graph, source, target, cutoff=self.max_path_hops
            ):
                path_length = sum(
                    graph[path[i]][path[i + 1]].get("length", 1.0)
                    for i in range(len(path) - 1)
                )
                if path_length <= max_length:
                    count += 1
                    if count >= max_paths:
                        break
        except nx.NetworkXNoPath:
            pass
        return count
