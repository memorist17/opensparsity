"""Build NetworkX network from vector data."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import networkx as nx
import numpy as np
from shapely import LineString, Point
from shapely.ops import linemerge, unary_union
from tqdm import tqdm

# NetworkX is always available
GRAPH_TOOL_AVAILABLE = False # Defaulting to False to rely on NetworkX for now to avoid dependency issues unless requested.


@dataclass
class NetworkBuilder:
    """Build spatial network graph from roads and buildings using NetworkX."""

    snap_tolerance: float = 1.0  # メートル
    connection_threshold: float = 10.0  # 道路セグメント間の接続判定距離（メートル）
    use_road_width: bool = True  # 道路幅を考慮した接続判定を行うか

    def build_network(
        self,
        roads: gpd.GeoDataFrame,
        buildings: gpd.GeoDataFrame | None = None,
        verbose: bool = True,
    ) -> nx.Graph:
        """
        Build network graph with:
        - Road intersection nodes
        - Building centroid nodes (optional)
        - Road edges
        - Virtual edges (building -> nearest road) (optional)

        Args:
            roads: Road line geometries in local coordinates
            buildings: Building polygon geometries in local coordinates (optional)
            verbose: Show progress

        Returns:
            NetworkX Graph with 'length' edge attribute
        """
        G = nx.Graph()

        if len(roads) == 0:
            if verbose:
                print("No roads to process")
            return G

        if verbose:
            print(f"Building network from {len(roads)} road segments...")

        # Step 1: Extract nodes from road endpoints and intersections
        node_coords: dict[tuple[float, float], int] = {}
        created_nodes: list[tuple[float, float, int]] = []  # (x, y, node_id) 作成順
        node_counter = 0

        def get_or_create_node(x: float, y: float) -> int:
            """Get existing node or create new one at coordinates."""
            nonlocal node_counter
            # Snap to tolerance
            key = (round(x / self.snap_tolerance) * self.snap_tolerance,
                   round(y / self.snap_tolerance) * self.snap_tolerance)

            if key not in node_coords:
                node_coords[key] = node_counter
                created_nodes.append((key[0], key[1], node_counter))
                G.add_node(node_counter, x=key[0], y=key[1], type="road")
                node_counter += 1
            return node_coords[key]

        # Step 2: Add road edges
        for idx, row in tqdm(roads.iterrows(), total=len(roads), desc="Processing roads", disable=not verbose):
            geom = row.geometry
            if geom is None or geom.is_empty or not geom.is_valid:
                continue

            # Handle different geometry types
            lines = []
            if geom.geom_type == "LineString":
                lines = [geom]
            elif geom.geom_type == "MultiLineString":
                lines = [line for line in geom.geoms if not line.is_empty and line.is_valid]
            elif geom.geom_type == "GeometryCollection":
                # Handle GeometryCollection (can occur after clipping)
                for sub_geom in geom.geoms:
                    if sub_geom.geom_type == "LineString" and not sub_geom.is_empty and sub_geom.is_valid:
                        lines.append(sub_geom)
                    elif sub_geom.geom_type == "MultiLineString":
                        lines.extend([line for line in sub_geom.geoms if not line.is_empty and line.is_valid])
            
            if not lines:
                continue

            for line in lines:
                if len(line.coords) < 2:
                    continue

                coords = list(line.coords)

                # Create nodes at all vertices
                for i in range(len(coords) - 1):
                    x1, y1 = coords[i][0], coords[i][1]
                    x2, y2 = coords[i + 1][0], coords[i + 1][1]

                    node1 = get_or_create_node(x1, y1)
                    node2 = get_or_create_node(x2, y2)

                    if node1 != node2:
                        segment_length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                        # Add or update edge (keep shortest if duplicate)
                        if G.has_edge(node1, node2):
                            existing_length = G[node1][node2]["length"]
                            if segment_length < existing_length:
                                G[node1][node2]["length"] = segment_length
                        else:
                            G.add_edge(node1, node2, length=segment_length)

        # Step 2.5: Connect road segment endpoints that are close to each other
        # This addresses the issue where road segments should be connected but aren't
        # due to coordinate precision or data gaps
        if verbose:
            print("Connecting nearby road segment endpoints...")
        
        # Collect all segment endpoints with their metadata
        endpoints = []  # List of (x, y, node_id, width, segment_idx)
        segment_info = []  # Store segment metadata for connection logic
        
        for idx, row in roads.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty or not geom.is_valid:
                continue
            
            # Get road width (default to 5m if not available)
            width = row.get("width", 5.0) if "width" in row else 5.0
            
            # Handle different geometry types
            lines = []
            if geom.geom_type == "LineString":
                lines = [geom]
            elif geom.geom_type == "MultiLineString":
                lines = [line for line in geom.geoms if not line.is_empty and line.is_valid]
            elif geom.geom_type == "GeometryCollection":
                for sub_geom in geom.geoms:
                    if sub_geom.geom_type == "LineString" and not sub_geom.is_empty and sub_geom.is_valid:
                        lines.append(sub_geom)
                    elif sub_geom.geom_type == "MultiLineString":
                        lines.extend([line for line in sub_geom.geoms if not line.is_empty and line.is_valid])
            
            for line in lines:
                if len(line.coords) < 2:
                    continue
                
                coords = list(line.coords)
                # Get start and end points
                start_coord = coords[0]
                end_coord = coords[-1]
                
                # Get nodes for endpoints (they should already exist from Step 2)
                start_node = get_or_create_node(start_coord[0], start_coord[1])
                end_node = get_or_create_node(end_coord[0], end_coord[1])
                
                endpoints.append({
                    'x': start_coord[0],
                    'y': start_coord[1],
                    'node': start_node,
                    'width': width,
                    'segment_idx': len(segment_info)
                })
                endpoints.append({
                    'x': end_coord[0],
                    'y': end_coord[1],
                    'node': end_node,
                    'width': width,
                    'segment_idx': len(segment_info)
                })
                
                segment_info.append({
                    'start_node': start_node,
                    'end_node': end_node,
                    'width': width
                })
        
        # Connect endpoints that are close to each other.
        # KD-tree で「最大しきい値以内」の候補ペアだけを列挙してから
        # 元と同じ条件・同じ (i, j) 昇順で判定する（全ペア O(N^2) ループと
        # 追加されるエッジ・順序は同一で、候補列挙だけが O(N log N) になる）
        connections_added = 0
        max_connection_distance = self.connection_threshold

        if endpoints:
            from scipy.spatial import cKDTree

            ep_coords = np.array([[ep['x'], ep['y']] for ep in endpoints])
            if self.use_road_width:
                # ペアごとのしきい値 avg_width + connection_threshold の上界
                max_threshold = float(np.max([ep['width'] for ep in endpoints])) \
                    + self.connection_threshold
            else:
                max_threshold = max_connection_distance

            candidate_pairs = cKDTree(ep_coords).query_pairs(
                r=max_threshold + 1e-9, output_type="ndarray"
            )
            # 元実装の二重ループと同じ (i 昇順, j 昇順) で処理
            if len(candidate_pairs):
                order = np.lexsort((candidate_pairs[:, 1], candidate_pairs[:, 0]))
                candidate_pairs = candidate_pairs[order]

            for i, j in candidate_pairs:
                ep1 = endpoints[i]
                ep2 = endpoints[j]
                node1 = ep1['node']
                node2 = ep2['node']

                # Skip if same node or already connected
                if node1 == node2 or G.has_edge(node1, node2):
                    continue

                # Skip if from same segment (already connected)
                if ep1['segment_idx'] == ep2['segment_idx']:
                    continue

                # Calculate distance
                distance = np.sqrt((ep1['x'] - ep2['x'])**2 + (ep1['y'] - ep2['y'])**2)

                # Determine connection threshold
                if self.use_road_width:
                    # Use average road width as buffer
                    avg_width = (ep1['width'] + ep2['width']) / 2.0
                    threshold = avg_width + self.connection_threshold
                else:
                    threshold = max_connection_distance

                # Connect if within threshold
                if distance <= threshold:
                    G.add_edge(node1, node2, length=distance, type="connection")
                    connections_added += 1
        
        if verbose:
            print(f"Added {connections_added} inter-segment connections")

        if verbose:
            print(f"Road network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        # Step 3: Add building centroids as nodes (optional)
        if buildings is not None and len(buildings) > 0:
            if verbose:
                print(f"Adding {len(buildings)} building nodes...")

            building_nodes = []
            for idx, row in tqdm(buildings.iterrows(), total=len(buildings),
                                 desc="Adding buildings", disable=not verbose):
                geom = row.geometry
                if geom is None or geom.is_empty or not geom.is_valid:
                    continue

                centroid = geom.centroid
                x, y = centroid.x, centroid.y

                # Add as new node
                G.add_node(node_counter, x=x, y=y, type="building")
                building_nodes.append((node_counter, x, y))
                node_counter += 1

            # Step 4: Connect buildings to nearest road segment (not just road node)
            if building_nodes and len(roads) > 0:
                if verbose:
                    print("Connecting buildings to road network...")

                # Prepare road segments for distance calculation
                road_segments = []
                for idx, row in roads.iterrows():
                    geom = row.geometry
                    if geom is None or geom.is_empty or not geom.is_valid:
                        continue
                    
                    # Handle different geometry types
                    lines = []
                    if geom.geom_type == "LineString":
                        lines = [geom]
                    elif geom.geom_type == "MultiLineString":
                        lines = [line for line in geom.geoms if not line.is_empty and line.is_valid]
                    elif geom.geom_type == "GeometryCollection":
                        for sub_geom in geom.geoms:
                            if sub_geom.geom_type == "LineString" and not sub_geom.is_empty and sub_geom.is_valid:
                                lines.append(sub_geom)
                            elif sub_geom.geom_type == "MultiLineString":
                                lines.extend([line for line in sub_geom.geoms if not line.is_empty and line.is_valid])
                    
                    road_segments.extend(lines)

                if not road_segments:
                    if verbose:
                        print("No valid road segments found for building connection")
                else:
                    # Build a mapping from road segments to their graph edges
                    # This allows us to insert new nodes into existing edges
                    segment_to_edge = {}  # segment index -> list of (node1, node2) edges
                    
                    for seg_idx, segment in enumerate(road_segments):
                        coords = list(segment.coords)
                        edges = []
                        for i in range(len(coords) - 1):
                            x1, y1 = coords[i][0], coords[i][1]
                            x2, y2 = coords[i + 1][0], coords[i + 1][1]
                            # Find the corresponding nodes (using snap tolerance)
                            key1 = (round(x1 / self.snap_tolerance) * self.snap_tolerance,
                                    round(y1 / self.snap_tolerance) * self.snap_tolerance)
                            key2 = (round(x2 / self.snap_tolerance) * self.snap_tolerance,
                                    round(y2 / self.snap_tolerance) * self.snap_tolerance)
                            if key1 in node_coords and key2 in node_coords:
                                n1 = node_coords[key1]
                                n2 = node_coords[key2]
                                edges.append((n1, n2, x1, y1, x2, y2))
                        segment_to_edge[seg_idx] = edges
                    
                    # 空間インデックスを一度だけ構築する。
                    # 旧実装は建物ごとに全セグメントへの距離を線形走査し、
                    # さらに全ノード配列を毎回作り直していた（O(B×S) + O(B×N)）。
                    # STRtree / KD-tree に置き換えても選ばれるセグメント・ノードは
                    # 同一（同距離タイは旧実装と同じく最初＝最小インデックスを採用）。
                    from scipy.spatial import cKDTree
                    from shapely.strtree import STRtree

                    segment_tree = STRtree(road_segments)

                    # 建物ループ開始時点のノード（静的部分）は KD-tree、
                    # ループ中に追加されるノード（動的部分）は線形走査で照会する
                    static_len = len(created_nodes)
                    static_ids = [nid for _, _, nid in created_nodes]
                    static_tree = (
                        cKDTree(np.array([(x, y) for x, y, _ in created_nodes]))
                        if created_nodes else None
                    )

                    def nearest_existing_node(px: float, py: float, upto: int):
                        """created_nodes[:upto] の中で (px,py) に最近傍のノードを返す。

                        旧実装の np.argmin（挿入順で最初の最小値）と同じく、
                        タイのときは先に作られたノード（静的部分）を優先する。
                        """
                        best_d, best_id = float("inf"), None
                        if static_tree is not None:
                            _, k = static_tree.query([px, py])
                            # 距離は旧実装と同じ式で再計算（cKDTree の丸めと
                            # 最終ビットが異なることがあるため）
                            x, y, nid = created_nodes[k]
                            best_d = float(np.sqrt((x - px) ** 2 + (y - py) ** 2))
                            best_id = nid
                        for x, y, nid in created_nodes[static_len:upto]:
                            d = np.sqrt((x - px) ** 2 + (y - py) ** 2)
                            if d < best_d:
                                best_d, best_id = d, nid
                        return best_id, best_d

                    for bnode, bx, by in tqdm(building_nodes, desc="Connecting buildings", disable=not verbose):
                        building_point = Point(bx, by)
                        # この建物の処理開始時点でのノード集合（旧実装が
                        # イテレーション冒頭で配列を作り直していたのと同じ範囲）
                        nodes_upto = len(created_nodes)

                        # Find nearest road segment（同距離タイは最小インデックス）
                        tie_indices = segment_tree.query_nearest(
                            building_point, all_matches=True
                        )
                        if len(tie_indices) == 0:
                            continue
                        nearest_segment_idx = int(np.min(tie_indices))
                        nearest_segment = road_segments[nearest_segment_idx]
                        min_distance = building_point.distance(nearest_segment)
                        projected_distance_on_segment = nearest_segment.project(building_point)
                        nearest_point_on_segment = nearest_segment.interpolate(projected_distance_on_segment)

                        if nearest_point_on_segment is not None and nearest_segment is not None:
                            # Get coordinates of nearest point on segment
                            px, py = nearest_point_on_segment.x, nearest_point_on_segment.y

                            # Check if there's an existing node within snap_tolerance
                            use_existing_node = False
                            nearest_road_node = None

                            candidate_node, candidate_dist = nearest_existing_node(px, py, nodes_upto)
                            if candidate_node is not None and candidate_dist <= self.snap_tolerance:
                                # Use existing node
                                nearest_road_node = candidate_node
                                use_existing_node = True
                                connection_distance = np.sqrt((bx - px) ** 2 + (by - py) ** 2)
                            
                            if not use_existing_node:
                                # Create new node on road segment AND insert it into the road network
                                nearest_road_node = get_or_create_node(px, py)
                                connection_distance = min_distance
                                
                                # Find which edge of the segment this point falls on and insert the node
                                node_inserted = False
                                if nearest_segment_idx is not None and nearest_segment_idx in segment_to_edge:
                                    segment_coords = list(nearest_segment.coords)
                                    cumulative_length = 0.0
                                    
                                    for i in range(len(segment_coords) - 1):
                                        x1, y1 = segment_coords[i][0], segment_coords[i][1]
                                        x2, y2 = segment_coords[i + 1][0], segment_coords[i + 1][1]
                                        edge_length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                                        
                                        # Check if the projected point falls on this edge
                                        if cumulative_length <= projected_distance_on_segment <= cumulative_length + edge_length:
                                            # Find the corresponding graph nodes
                                            key1 = (round(x1 / self.snap_tolerance) * self.snap_tolerance,
                                                    round(y1 / self.snap_tolerance) * self.snap_tolerance)
                                            key2 = (round(x2 / self.snap_tolerance) * self.snap_tolerance,
                                                    round(y2 / self.snap_tolerance) * self.snap_tolerance)
                                            
                                            if key1 in node_coords and key2 in node_coords:
                                                n1 = node_coords[key1]
                                                n2 = node_coords[key2]
                                                
                                                # Calculate distances from the new node to the edge endpoints
                                                dist_to_n1 = np.sqrt((px - x1) ** 2 + (py - y1) ** 2)
                                                dist_to_n2 = np.sqrt((px - x2) ** 2 + (py - y2) ** 2)
                                                
                                                # Only insert if the new node is not too close to existing nodes
                                                if dist_to_n1 > self.snap_tolerance and dist_to_n2 > self.snap_tolerance:
                                                    # Remove the original edge if it exists
                                                    if G.has_edge(n1, n2):
                                                        G.remove_edge(n1, n2)
                                                    
                                                    # Add edges from the new node to both endpoints
                                                    G.add_edge(n1, nearest_road_node, length=dist_to_n1, type="road")
                                                    G.add_edge(nearest_road_node, n2, length=dist_to_n2, type="road")
                                                    node_inserted = True
                                            break
                                        
                                        cumulative_length += edge_length
                                
                                # If node was not inserted into an edge, connect it to the nearest road node
                                if not node_inserted:
                                    # Find nearest road node to connect to
                                    # （旧実装と同じく、この建物の処理開始時点の
                                    #   ノード集合から探す＝直前に作った分割ノードは含まない）
                                    nearest_existing_road_node, dist_to_nearest = \
                                        nearest_existing_node(px, py, nodes_upto)
                                    if nearest_existing_road_node is not None:
                                        # Connect new node to nearest road node
                                        G.add_edge(nearest_road_node, nearest_existing_road_node,
                                                  length=dist_to_nearest, type="road")
                            
                            # Add virtual edge from building to road segment point
                            G.add_edge(bnode, nearest_road_node, length=connection_distance, type="virtual")

            if verbose:
                print(f"Final network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        return G

    def save(self, graph: nx.Graph, output_path: Path) -> None:
        """Save graph to .graphml file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Ensure path has correct extension
        if output_path.suffix != ".graphml":
            output_path = output_path.with_suffix(".graphml")

        nx.write_graphml(graph, str(output_path))

    def load(self, input_path: Path) -> nx.Graph:
        """Load graph from .graphml file."""
        return nx.read_graphml(str(input_path))

    def get_edge_lengths(self, graph: nx.Graph) -> np.ndarray:
        """Extract all edge lengths as numpy array."""
        return np.array([data.get("length", 0) for _, _, data in graph.edges(data=True)])

    def compute_statistics(self, graph: nx.Graph) -> dict[str, Any]:
        """Compute basic network statistics."""
        if graph.number_of_nodes() == 0:
            return {
                "n_nodes": 0,
                "n_edges": 0,
                "n_components": 0,
                "avg_degree": 0,
                "total_length": 0,
            }

        lengths = self.get_edge_lengths(graph)
        degrees = [d for _, d in graph.degree()]

        return {
            "n_nodes": graph.number_of_nodes(),
            "n_edges": graph.number_of_edges(),
            "n_components": nx.number_connected_components(graph),
            "avg_degree": np.mean(degrees) if degrees else 0,
            "total_length": np.sum(lengths),
            "mean_edge_length": np.mean(lengths) if len(lengths) > 0 else 0,
            "max_edge_length": np.max(lengths) if len(lengths) > 0 else 0,
        }

    # Alias for backwards compatibility
    get_network_stats = compute_statistics




