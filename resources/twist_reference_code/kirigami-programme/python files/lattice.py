import os
import sys
import json
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import ast

def offset_polygon(verts, offset, edge_vertices=None):
    verts = np.asarray(verts)
    center = np.mean(verts, axis=0)
    direction = verts - center
    norm = np.linalg.norm(direction, axis=1, keepdims=True)
    norm[norm == 0] = 1
    if edge_vertices is None:
        return center + direction * (1 + offset / (norm + 1e-12))
    else:
        edge_vertices = np.asarray(edge_vertices)
        new_verts = verts.copy()
        for i, vert in enumerate(verts):
            if np.any(np.all(np.isclose(edge_vertices, vert), axis=1)):
                new_verts[i] = center + direction[i] * (1 + offset / (norm[i] + 1e-12))
        return new_verts

def plot_colored_polygons(polygon_vertices_dict, facecolors=None, edgecolor='k', alpha=0.7, edgewidth=0.5, offset=0.0):
    ax = plt.gca()
    for idx, (poly_id, verts) in enumerate(polygon_vertices_dict.items()):
        if facecolors is None:
            color = None
        elif isinstance(facecolors, dict):
            color = facecolors.get(poly_id, None)
        else:
            color = facecolors[idx % len(facecolors)]
        alpha1 = alpha
        verts = np.asarray(verts)
        verts_to_draw = verts
        if offset != 0.0:
            verts_to_draw = offset_polygon(verts, offset)
        polygon = Polygon(verts_to_draw, closed=True, facecolor=color, edgecolor=edgecolor, alpha=alpha1, linewidth=edgewidth)
        ax.add_patch(polygon)

def truncate_tuple(t, decimals=2):
    return tuple(round(x, decimals) for x in t)

class GraphAnalyzer:
    def __init__(self, graph, pos, geometry):
        self.graph = graph
        self.pos = pos
        self.geometry = geometry
        self.polygon_centers, self.polygon_cycles = self.detect_polygon_centers()
        self.G1, self.pos1 = self.build_G1()
        self.G2, self.pos2 = self.build_G2()
        self.labels1 = {node: truncate_tuple(self.pos1[node]) for node in self.G1.nodes()}
        self.labels2 = {node: truncate_tuple(self.pos2[node]) for node in self.G2.nodes()}

    def detect_polygon_centers(self):
        """
        Detect the centroid of each polygon (cycle) in a 2D lattice graph.
        Ensures all cycles are in counterclockwise direction.
        For each cycle, starts at the vertex with the lowest (y, then x).
        Sorts the centroids by (cx, cy) and renumbers the dict keys.

        Returns:
            tuple:
                - dict: Mapping new_polygon_id to centroid (x, y).
                - dict: Mapping new_polygon_id to list of vertices (positions).
        """
        def is_counterclockwise(vertices):
            # Shoelace formula: positive area means counterclockwise
            n = len(vertices)
            area = 0.0
            for i in range(n):
                x1, y1 = vertices[i]
                x2, y2 = vertices[(i + 1) % n]
                area += (x2 - x1) * (y2 + y1)
            return area < 0

        cycles = list(nx.simple_cycles(self.graph.to_undirected(), length_bound=self.lb)) # type: ignore
        centers = []
        cycles_pos = []
        for cycle in cycles:
            vertices = [self.pos[node] for node in cycle]
            # Ensure counterclockwise order
            if not is_counterclockwise(vertices):
                vertices = vertices[::-1]
            # Find the lowest vertex (by y, then x)
            min_idx = min(range(len(vertices)), key=lambda i: (vertices[i][1], vertices[i][0]))
            # Rotate so that the lowest vertex is first
            vertices = vertices[min_idx:] + vertices[:min_idx]
            cycles_pos.append(vertices)
            n = len(vertices)
            cx = sum(x for x, y in vertices) / n
            cy = sum(y for x, y in vertices) / n
            centers.append((cx, cy))
        return {i: centers[i] for i in range(len(centers))}, {i: cycles_pos[i] for i in range(len(cycles_pos))}

    def build_G1(self):
        G1 = nx.DiGraph()
        for node, p in self.pos.items():
            float_pos = (float(p[0]), float(p[1]))
            G1.add_node(float_pos, pos=float_pos)
        for u, v in self.graph.edges():
            u_pos = (float(self.pos[u][0]), float(self.pos[u][1]))
            v_pos = (float(self.pos[v][0]), float(self.pos[v][1]))
            G1.add_edge(u_pos, v_pos)
        pos1 = {node: node for node in G1.nodes()}
        return G1, pos1

    def build_G2(self):
        G2 = nx.Graph()
        float_centers = list(self.polygon_centers.values())
        for center in float_centers:
            G2.add_node(center)
        edge_to_cycles = {}
        for idx, vertices in self.polygon_cycles.items():
            n = len(vertices)
            for i in range(n):
                edge = tuple(sorted([tuple(vertices[i]), tuple(vertices[(i+1)%n])]))
                edge_to_cycles.setdefault(edge, []).append(idx)
        added_edges = set()
        for idx, vertices in self.polygon_cycles.items():
            center1 = self.polygon_centers[idx]
            n = len(vertices)
            for i in range(n):
                edge = tuple(sorted([tuple(vertices[i]), tuple(vertices[(i+1)%n])]))
                midpoint = ((vertices[i][0] + vertices[(i+1)%n][0]) / 2, (vertices[i][1] + vertices[(i+1)%n][1]) / 2)
                dist1 = np.linalg.norm(np.array(center1) - np.array(midpoint))
                for other_idx in edge_to_cycles[edge]:
                    if other_idx != idx:
                        center2 = self.polygon_centers[other_idx]
                        dist2 = np.linalg.norm(np.array(center2) - np.array(midpoint))
                        if np.isclose(dist1, dist2, atol=1e-8):
                            edge_tuple = tuple(sorted([center1, center2]))
                            if edge_tuple not in added_edges:
                                G2.add_edge(center1, center2)
                                added_edges.add(edge_tuple)
        pos2 = {node: node for node in G2.nodes()}
        return G2, pos2

def create_lattice(m,n,geometry,shape, casex):
    G, pos = None, None

    match shape:
        case "Equilateral Triangle":
            match casex:
                    case 1:
                        G = nx.DiGraph()
                        M = m + 1 
                        N = n + 2
                        sq3 = float(np.sqrt(3))
                        for i in range(N):
                            for j in range(M):
                                if i % 2 == 0 and j % 2 == 0 :
                                    if n%2 == 0 and i+2 < N:
                                        G.add_edge((i, sq3*j), (i+2, sq3*j))
                                    elif n%2 != 0 and i+2 < N:
                                        G.add_edge((i, sq3*j), (i+2, sq3*j))
                                    
                                    if n%2==0 and j+1 < M and i+1 < N:
                                        G.add_edge((i, sq3*j), (i+1, sq3*(j+1)))
                                    elif n%2!=0 and j+1 < M and i+1 < N:
                                        G.add_edge((i, sq3*j), (i+1, sq3*(j+1)))
                                    
                                    if n%2 == 0 and j+1 <M and i-1>=0 :
                                        G.add_edge((i, sq3*j), (i-1, sq3*(j+1)))
                                    elif n%2 != 0 and j+1 <M  and i-1 >= 0:
                                        G.add_edge((i, sq3*j), (i-1, sq3*(j+1)))
                                
                                elif i % 2 != 0 and j % 2 != 0:
                                    if n%2 == 0 and i+2 < N:
                                        G.add_edge((i, sq3*j), (i+2, sq3*j))
                                    elif n%2 != 0 and i+2 < N:
                                        G.add_edge((i, sq3*j), (i+2, sq3*j))
                                
                                    if n%2==0 and j+1 < M and i+1 < N:
                                        G.add_edge((i, sq3*j), (i+1, sq3*(j+1)))
                                    elif n%2!=0 and j+1 < M and i+1 < N:
                                        G.add_edge((i, sq3*j), (i+1, sq3*(j+1)))
                                    
                                    if n%2 == 0 and j+1 <M and i-1>=0 :
                                        G.add_edge((i, sq3*j), (i-1, sq3*(j+1)))
                                    elif n%2 != 0 and j+1 <M  and i-1 >= 0:
                                        G.add_edge((i, sq3*j), (i-1, sq3*(j+1)))

                        for node in list(G.nodes()):
                            if m%2 == 0 and  n%2 == 0:
                                if node[0] == 0 and node[1] == 0:
                                    G.remove_node(node)
                                elif node[0] == 0 and node[1] == sq3*(m):
                                    G.remove_node(node)
                            elif m%2 == 0 and n%2 != 0:
                                if node[0] == 0 and node[1] == 0:
                                    G.remove_node(node)
                                elif node[0] == 0 and node[1] == sq3*(m):
                                    G.remove_node(node)
                                elif node[0] == N-1 and node[1] == 0:
                                    G.remove_node(node)
                                elif node[0] == N-1 and node[1] == sq3*(m):
                                    G.remove_node(node)
                            elif m%2 != 0 and n%2 == 0:
                                if node[0] == 0 and node[1] == 0:
                                    G.remove_node(node)
                                elif node[0] == N-1 and node[1] == sq3*(m):
                                    G.remove_node(node)
                            elif m%2 != 0 and n%2 != 0:
                                if node[0] == 0 and node[1] == 0:
                                    G.remove_node(node)
                                elif node[0] == N-1 and node[1] == 0:
                                    G.remove_node(node)
                                    
                        pos = {(x, y): (x, y) for x, y in G.nodes()}

                    case 2:
                        G = nx.DiGraph()
                        M = m + 2
                        N = n + 2
                        sq3 = float(np.sqrt(3))
                        for i in range(N):
                            for j in range(M):
                                if i % 2 == 0 and j % 2 == 0 :
                                    if n%2 == 0 and i+2 < N:
                                        G.add_edge((i, sq3*j), (i+2, sq3*j))
                                    elif n%2 != 0 and i+2 < N:
                                        G.add_edge((i, sq3*j), (i+2, sq3*j))
                                    
                                    if n%2==0 and j+1 < M and i+1 < N:
                                        G.add_edge((i, sq3*j), (i+1, sq3*(j+1)))
                                    elif n%2!=0 and j+1 < M and i+1 < N:
                                        G.add_edge((i, sq3*j), (i+1, sq3*(j+1)))
                                    
                                    if n%2 == 0 and j+1 <M and i-1>=0 :
                                        G.add_edge((i, sq3*j), (i-1, sq3*(j+1)))
                                    elif n%2 != 0 and j+1 <M  and i-1 >= 0:
                                        G.add_edge((i, sq3*j), (i-1, sq3*(j+1)))
                                
                                elif i % 2 != 0 and j % 2 != 0:
                                    if n%2 == 0 and i+2 < N:
                                        G.add_edge((i, sq3*j), (i+2, sq3*j))
                                    elif n%2 != 0 and i+2 < N:
                                        G.add_edge((i, sq3*j), (i+2, sq3*j))
                                
                                    if n%2==0 and j+1 < M and i+1 < N:
                                        G.add_edge((i, sq3*j), (i+1, sq3*(j+1)))
                                    elif n%2!=0 and j+1 < M and i+1 < N:
                                        G.add_edge((i, sq3*j), (i+1, sq3*(j+1)))
                                    
                                    if n%2 == 0 and j+1 <M and i-1>=0 :
                                        G.add_edge((i, sq3*j), (i-1, sq3*(j+1)))
                                    elif n%2 != 0 and j+1 <M  and i-1 >= 0:
                                        G.add_edge((i, sq3*j), (i-1, sq3*(j+1)))
                            
                        for node in list(G.nodes()):
                            if node[1] == 0:
                                G.remove_node(node)

                        for node in list(G.nodes()):
                            if m%2 == 0 and  n%2 == 0:
                                if node[0] == N-1 and node[1] == sq3:
                                    G.remove_node(node)
                                elif node[0] == N-1 and node[1] == sq3*(M-1):
                                    G.remove_node(node)
                            elif m%2 != 0 and n%2 == 0:
                                if node[0] == N-1 and node[1] == sq3:
                                    G.remove_node(node)
                                elif node[0] == 0 and node[1] == sq3*(M-1):
                                    G.remove_node(node)
                            elif m%2 != 0 and n%2 != 0:
                                if node[0] == 0 and node[1] == sq3*(M-1):
                                    G.remove_node(node)
                                elif node[0] == N-1 and node[1] == sq3*(M-1):
                                    G.remove_node(node)

                        pos = {(x, y): (x, y) for x, y in G.nodes()}

        case "Square and Rectangle":
            match casex:
                    case 1:
                        m,n = m+1, n+1
                        c, d = 1, 1
                        G = nx.grid_2d_graph(n, m, create_using=nx.DiGraph)
                        node_mapping = {(x, y): ((d*x) ,(c*y)) for x, y in G.nodes()}
                        G = nx.relabel_nodes(G, node_mapping)
                        pos = {(x, y): (x, y) for x, y in G.nodes()}
                    case 2:
                        m, n = m + 1, n + 1
                        c, d = 1, 2
                        G = nx.grid_2d_graph(n, m, create_using=nx.DiGraph)
                        node_mapping = {(x, y): ((d*x) ,(c*y)) for x, y in G.nodes()}
                        G = nx.relabel_nodes(G, node_mapping)
                        pos = {(x, y): (x, y) for x, y in G.nodes()}
                        
        case "Regular Hexagon":
            match casex:
                    case 1:
                        G = nx.hexagonal_lattice_graph(m, n, with_positions=True, create_using=nx.DiGraph)
                        pos = nx.get_node_attributes(G, 'pos')
                    case 2:
                        G = nx.DiGraph() 
                        M = 2 * m  # twice as many nodes as hexagons vertically
                        rows = range(M + 3)
                        cols = range(n + 2)
                        # make lattice
                        col_edges = (((i, j), (i, j + 1)) for i in cols for j in rows[: M + 2])
                        row_edges = (((i, j), (i + 1, j)) for i in cols[:n+1] for j in rows if i % 2 == j % 2)
                        G.add_edges_from(col_edges)
                        G.add_edges_from(row_edges)
                        # Remove corner nodes with one edge
                        if (n + 1) % 2 == 0:
                            G.remove_node((n + 1, (M + 2)))
                            G.remove_node((n + 1, 0))
                        rmnodes = ((i, j) for i in cols for j in rows if i == 0)
                        G.remove_node((1,0))
                        G.remove_node((1,M+2))
                        G.remove_nodes_from(rmnodes)
                        # Translate and relabel node i by -1
                        relabel = {node: (node[0] - 1, node[1]) for node in G.nodes()}
                        G = nx.relabel_nodes(G, relabel)

                        # Add positions to the nodes
                        ii = (i for i in cols for j in rows)
                        jj = (j for i in cols for j in rows)
                        xx = (i  + (i + 1) // 2 + (j % 2) * (((i + 1) % 2) - 0.5) for i in cols for j in rows)
                        h = np.sqrt(3) / 2
                        yy = (h * j for i in cols for j in rows)
                        pos = {(i, j): (x, y) for i, j, x, y in zip(ii, jj, xx, yy) if (i, j) in G}
                        nx.set_node_attributes(G, pos, 'pos')
                        pos = nx.get_node_attributes(G, 'pos')
                    case 3:
                        G = nx.DiGraph() 
                        M = 2 * m  # twice as many nodes as hexagons vertically
                        rows = range(M + 3)
                        cols = range(n + 1)
                        # make lattice
                        col_edges = (((i, j), (i, j + 1)) for i in cols for j in rows[: M + 2])
                        row_edges = (((i, j), (i + 1, j)) for i in cols[:n] for j in rows if i % 2 == j % 2)
                        G.add_edges_from(col_edges)
                        G.add_edges_from(row_edges)
                        # Remove corner nodes with one edge
                        if n % 2 == 0:
                            G.remove_node((n, (M + 2)))
                            G.remove_node((n, 0))

                        # Add positions to the nodes
                        ii = (i for i in cols for j in rows)
                        jj = (j for i in cols for j in rows)
                        xx = (0.5 + i + i // 2 + (j % 2) * ((i % 2) - 0.5) for i in cols for j in rows)
                        h = np.sqrt(3) / 2
                        yy = (h * j for i in cols for j in rows)
                        pos = {(i, j): (x, y) for i, j, x, y in zip(ii, jj, xx, yy) if (i, j) in G}
                        nx.set_node_attributes(G, pos, 'pos')
                        pos = nx.get_node_attributes(G, 'pos')

        case "Derived Geometries":
            match casex:
                    case 1: #square into 2 traingles
                        c, d = 5, 5
                        a,b = m,n
                        m,n = b+1, a+1
                        G = nx.DiGraph()
                        for i in range(0, c*m, c):
                            for j in range(0, d*n, d):
                                if i < c*(m-1):
                                    G.add_edge((i, j), (i+c, j))
                                if j < d*(n-1):
                                    G.add_edge((i, j), (i, j+d))
                                if i < c*(m-1) and j < d*(n-1):
                                    G.add_edge((i, j), (i+(c), j+(d)))

                        G.remove_node((0, d*(n-1)))
                        G.remove_node((c*(m-1), 0))

                        pos = {(x, y): (x, y) for x, y in G.nodes()}
                    case 2: #square into 4 triangles
                        c, d =5, 5
                        a,b = m,n
                        m,n = b+1, a+1
                        G = nx.DiGraph()
                        for i in range(0, c*m, c):
                            for j in range(0, d*n, d):
                                if i < c*(m-1):
                                    G.add_edge((i, j), (i+c, j))
                                if j < d*(n-1):
                                    G.add_edge((i, j), (i, j+d))
                                if i < c*(m-1) and j < d*(n-1):
                                    G.add_edge((i, j), (i+(c/2), j+(d/2)))
                                    G.add_edge((i+(c/2), j+(d/2)), (i+c, j+d))
                                if i < c*(m) and j < d*(n-1) and i > 0:
                                    G.add_edge((i, j), (i-(c/2), j+(d/2)))
                                    G.add_edge((i-(c/2), j+(d/2)), (i-c, j+d))
                        pos = {(x, y): (x, y) for x, y in G.nodes()}
                    case 3: #hexagon case 1 into 6 triangles
                        G = nx.hexagonal_lattice_graph(m, n, with_positions=True, create_using=nx.DiGraph)
                        pos = nx.get_node_attributes(G, 'pos')
                    case 4: # hexagon case 2 into 6 triangles
                        G = nx.DiGraph() 
                        M = 2 * m  # twice as many nodes as hexagons vertically
                        rows = range(M + 3)
                        cols = range(n + 2)
                        # make lattice
                        col_edges = (((i, j), (i, j + 1)) for i in cols for j in rows[: M + 2])
                        row_edges = (((i, j), (i + 1, j)) for i in cols[:n+1] for j in rows if i % 2 == j % 2)
                        G.add_edges_from(col_edges)
                        G.add_edges_from(row_edges)
                        # Remove corner nodes with one edge
                        if (n + 1) % 2 == 0:
                            G.remove_node((n + 1, (M + 2)))
                            G.remove_node((n + 1, 0))
                        rmnodes = ((i, j) for i in cols for j in rows if i == 0)
                        G.remove_node((1,0))
                        G.remove_node((1,M+2))
                        G.remove_nodes_from(rmnodes)
                        # Translate and relabel node i by -1
                        relabel = {node: (node[0] - 1, node[1]) for node in G.nodes()}
                        G = nx.relabel_nodes(G, relabel)

                        # Add positions to the nodes
                        ii = (i for i in cols for j in rows)
                        jj = (j for i in cols for j in rows)
                        xx = (i  + (i + 1) // 2 + (j % 2) * (((i + 1) % 2) - 0.5) for i in cols for j in rows)
                        h = np.sqrt(3) / 2
                        yy = (h * j for i in cols for j in rows)
                        pos = {(i, j): (x, y) for i, j, x, y in zip(ii, jj, xx, yy) if (i, j) in G}
                        nx.set_node_attributes(G, pos, 'pos')
                        pos = nx.get_node_attributes(G, 'pos')
                    case 5: # hexagon case 3 into 6 triangles
                        G = nx.DiGraph() 
                        M = 2 * m  # twice as many nodes as hexagons vertically
                        rows = range(M + 3)
                        cols = range(n + 1)
                        # make lattice
                        col_edges = (((i, j), (i, j + 1)) for i in cols for j in rows[: M + 2])
                        row_edges = (((i, j), (i + 1, j)) for i in cols[:n] for j in rows if i % 2 == j % 2)
                        G.add_edges_from(col_edges)
                        G.add_edges_from(row_edges)
                        # Remove corner nodes with one edge
                        if n % 2 == 0:
                            G.remove_node((n, (M + 2)))
                            G.remove_node((n, 0))

                        # Add positions to the nodes
                        ii = (i for i in cols for j in rows)
                        jj = (j for i in cols for j in rows)
                        xx = (0.5 + i + i // 2 + (j % 2) * ((i % 2) - 0.5) for i in cols for j in rows)
                        h = np.sqrt(3) / 2
                        yy = (h * j for i in cols for j in rows)
                        pos = {(i, j): (x, y) for i, j, x, y in zip(ii, jj, xx, yy) if (i, j) in G}
                        nx.set_node_attributes(G, pos, 'pos')
                        pos = nx.get_node_attributes(G, 'pos')
                    
                    case 6: # hexagon case 1 into 3 parrelograms
                        G = nx.hexagonal_lattice_graph(m, n, with_positions=True, create_using=nx.DiGraph)
                        pos = nx.get_node_attributes(G, 'pos')
                    case 7: # hexagon case 2 into 3 parrelograms
                        G = nx.DiGraph() 
                        M = 2 * m  # twice as many nodes as hexagons vertically
                        rows = range(M + 3)
                        cols = range(n + 2)
                        # make lattice
                        col_edges = (((i, j), (i, j + 1)) for i in cols for j in rows[: M + 2])
                        row_edges = (((i, j), (i + 1, j)) for i in cols[:n+1] for j in rows if i % 2 == j % 2)
                        G.add_edges_from(col_edges)
                        G.add_edges_from(row_edges)
                        # Remove corner nodes with one edge
                        if (n + 1) % 2 == 0:
                            G.remove_node((n + 1, (M + 2)))
                            G.remove_node((n + 1, 0))
                        rmnodes = ((i, j) for i in cols for j in rows if i == 0)
                        G.remove_node((1,0))
                        G.remove_node((1,M+2))
                        G.remove_nodes_from(rmnodes)
                        # Translate and relabel node i by -1
                        relabel = {node: (node[0] - 1, node[1]) for node in G.nodes()}
                        G = nx.relabel_nodes(G, relabel)

                        # Add positions to the nodes
                        ii = (i for i in cols for j in rows)
                        jj = (j for i in cols for j in rows)
                        xx = (i  + (i + 1) // 2 + (j % 2) * (((i + 1) % 2) - 0.5) for i in cols for j in rows)
                        h = np.sqrt(3) / 2
                        yy = (h * j for i in cols for j in rows)
                        pos = {(i, j): (x, y) for i, j, x, y in zip(ii, jj, xx, yy) if (i, j) in G}
                        nx.set_node_attributes(G, pos, 'pos')
                        pos = nx.get_node_attributes(G, 'pos')
                    case 8: # hexagon case 3 into 3 parrelograms
                        G = nx.DiGraph() 
                        M = 2 * m  # twice as many nodes as hexagons vertically
                        rows = range(M + 3)
                        cols = range(n + 1)
                        # make lattice
                        col_edges = (((i, j), (i, j + 1)) for i in cols for j in rows[: M + 2])
                        row_edges = (((i, j), (i + 1, j)) for i in cols[:n] for j in rows if i % 2 == j % 2)
                        G.add_edges_from(col_edges)
                        G.add_edges_from(row_edges)
                        # Remove corner nodes with one edge
                        if n % 2 == 0:
                            G.remove_node((n, (M + 2)))
                            G.remove_node((n, 0))

                        # Add positions to the nodes
                        ii = (i for i in cols for j in rows)
                        jj = (j for i in cols for j in rows)
                        xx = (0.5 + i + i // 2 + (j % 2) * ((i % 2) - 0.5) for i in cols for j in rows)
                        h = np.sqrt(3) / 2
                        yy = (h * j for i in cols for j in rows)
                        pos = {(i, j): (x, y) for i, j, x, y in zip(ii, jj, xx, yy) if (i, j) in G}
                        nx.set_node_attributes(G, pos, 'pos')
                        pos = nx.get_node_attributes(G, 'pos')

        case "Arrays with Internal Hole":
            match casex:
                case 1:
                    G = nx.DiGraph() 
                    m = 3
                    n = 5
                    M = 2 * m  # twice as many nodes as hexagons vertically
                    rows = range(M + 3)
                    cols = range(n + 2)
                    # make lattice
                    col_edges = (((i, j), (i, j + 1)) for i in cols for j in rows[: M + 2])
                    row_edges = (((i, j), (i + 1, j)) for i in cols[:n+1] for j in rows if i % 2 == j % 2)
                    G.add_edges_from(col_edges)
                    G.add_edges_from(row_edges)

                    # Remove corner nodes with one edge
                    if (n + 1) % 2 == 0:
                        G.remove_node((n + 1, (M + 2)))
                        G.remove_node((n + 1, 0))
                    rmnodes = ((i, j) for i in cols for j in rows if i == 0)
                    G.remove_node((1,0))
                    G.remove_node((1,M+2))
                    G.remove_nodes_from(rmnodes)


                    # Translate and relabel node i by -1
                    relabel = {node: (node[0] - 1, node[1]) for node in G.nodes()}
                    G = nx.relabel_nodes(G, relabel)

                    G.add_edge((2,8), (2, 9))
                    G.add_edge((2,9), (3, 9)) 
                    G.add_edge((3,9), (3, 8))


                    G.add_edge((2,0), (2, -1))
                    G.add_edge((2,-1), (3, -1)) 
                    G.add_edge((3,-1), (3, 0))

                    # Add positions to the nodes
                    ii = (i for i in cols for j in rows)
                    jj = (j for i in cols for j in rows)
                    xx = (i  + (i + 1) // 2 + (j % 2) * (((i + 1) % 2) - 0.5) for i in cols for j in rows)
                    h = np.sqrt(3) / 2
                    yy = (h * j for i in cols for j in rows)


                    pos = {(i, j): (x, y) for i, j, x, y in zip(ii, jj, xx, yy) if (i, j) in G}
                    pos[(2, 9)] = (3.5, 9*h)  # Adjust position of the node (2,9)
                    pos[(3, 9)] = (4.5, 9*h)
                    pos[(2,-1)] = (3.5, -1*h)  # Adjust position of the node (2,-1)
                    pos[(3,-1)] = (4.5, -1*h)

                    nx.set_node_attributes(G, pos, 'pos')
                    pos = nx.get_node_attributes(G, 'pos')
                case 2:
                    m,n = m+1, n+1
                    c, d = 1, 1
                    G = nx.grid_2d_graph(n, m, create_using=nx.DiGraph)
                    node_mapping = {(x, y): ((d*x) ,(c*y)) for x, y in G.nodes()}
                    G = nx.relabel_nodes(G, node_mapping)
                    pos = {(x, y): (x, y) for x, y in G.nodes()}
                case 3:
                    G = nx.DiGraph()

    # Analyze graph
    match shape:
        case "Equilateral Triangle"| "Square and Rectangle"| "Regular Hexagon":
            analyzer = GraphAnalyzer(G, pos, geometry)

        case "Derived Geometries":
            match casex:
                case 3|4|5:
                    analyzer1 = GraphAnalyzer(G, pos, 6)
                    polygon_centers = analyzer1.polygon_centers
                    polygon_cycles = analyzer1.polygon_cycles
                    G = analyzer1.G1
                    pos = analyzer1.pos1

                    for cycle_id, verts in polygon_cycles.items():
                        polygon_cycles[cycle_id] = np.array(verts)
                        for i, center in polygon_centers.items():
                            if cycle_id == i:
                                for v in polygon_cycles[cycle_id]:
                                    G.add_edge(center, tuple(v))

                    pos = {node: (node[0], node[1]) for node in G.nodes()}

                    analyzer = GraphAnalyzer(G, pos, 3)

                case 6|7|8:
                    analyzer1 = GraphAnalyzer(G, pos, 6)
                    polygon_centers = analyzer1.polygon_centers
                    polygon_cycles = analyzer1.polygon_cycles
                    G = analyzer1.G1
                    pos = analyzer1.pos1
                    # Sort hexagon_centers and hexa_cycles by the position (x, y) of their centers
                    sorted_items = sorted(polygon_centers.items(), key=lambda item: (item[1][0], item[1][1]))
                    sorted_indices = [idx for idx, _ in sorted_items]

                    # Create new ordered dicts for centers and cycles
                    polygon_centers_sorted = {i: polygon_centers[idx] for i, idx in enumerate(sorted_indices)}
                    polygon_cycles_sorted = {i: polygon_cycles[idx] for i, idx in enumerate(sorted_indices)}

                    # Overwrite the originals if you want to use the sorted order everywhere
                    polygon_centers = polygon_centers_sorted
                    polygon_cycles = polygon_cycles_sorted

                    for cycle_id, verts in polygon_cycles.items():
                        polygon_cycles[cycle_id] = np.array(verts)
                        for i, center in polygon_centers.items():
                            if cycle_id == i:
                                for j, v in enumerate(polygon_cycles[cycle_id]):
                                    if j % 2 == 0:
                                        G.add_edge(center, tuple(v))

                    pos = {node: (node[0], node[1]) for node in G.nodes()}

                    analyzer = GraphAnalyzer(G, pos, 4)
                case _:
                    analyzer = GraphAnalyzer(G, pos, geometry)
                
        case "Arrays with Internal Hole":
            match casex:
                case 1|2:
                    analyzer = GraphAnalyzer(G, pos, geometry)
                    polygon_centers = analyzer.polygon_centers
                    polygon_cycles = analyzer.polygon_cycles

                    # Sort hexagon_centers and hexa_cycles by the position (x, y) of their centers
                    sorted_items = sorted(polygon_centers.items(), key=lambda item: (item[1][0], item[1][1]))
                    sorted_indices = [idx for idx, _ in sorted_items]

                    # Create new ordered dicts for centers and cycles
                    polygon_centers_sorted = {i: polygon_centers[idx] for i, idx in enumerate(sorted_indices)}
                    polygon_cycles_sorted = {i: polygon_cycles[idx] for i, idx in enumerate(sorted_indices)}

                    # Overwrite the originals if you want to use the sorted order everywhere
                    polygon_centers = polygon_centers_sorted
                    polygon_cycles = polygon_cycles_sorted

                    G2 = analyzer.G2
                    G2.remove_node(polygon_centers[len(polygon_centers)//2])
                    polygon_centers.pop(len(polygon_centers)//2)
                    polygon_cycles.pop(len(polygon_cycles)//2)

                    analyzer.G2 = G2
                    analyzer.polygon_centers = polygon_centers
                    analyzer.polygon_cycles = polygon_cycles


    # Prepare JSON data
    lattice_data = {
        "shape": shape,
        "geometry": geometry,
        "casex": casex, 
        "m": m,
        "n": n,
        "G1_nodes": [list(node) for node in analyzer.G1.nodes()],
        "G1_edges": [[list(e[0]), list(e[1])] for e in analyzer.G1.edges()],
        "G2_nodes": [list(node) for node in analyzer.G2.nodes()],
        "G2_edges": [[list(e[0]), list(e[1])] for e in analyzer.G2.edges()],
        "pos1": {str(list(node)): list(analyzer.pos1[node]) for node in analyzer.G1.nodes()},
        "pos2": {str(list(node)): list(analyzer.pos2[node]) for node in analyzer.G2.nodes()},
        "polygon_cycles": {str(k): [list(vv) for vv in v] for k, v in analyzer.polygon_cycles.items()},
        "polygon_centers": {str(k): list(v) for k, v in analyzer.polygon_centers.items()},
        "labels1": {str(k): v for k, v in analyzer.labels1.items()},
        "labels2": {str(k): v for k, v in analyzer.labels2.items()},    

    }
    return lattice_data, analyzer

if __name__ == "__main__":

    pyin = ast.literal_eval(sys.argv[1])
    if not (isinstance(pyin, (list, tuple)) and len(pyin) == 3):
        raise ValueError("First argument must be a list of three numbers: [m, n, geometry]")

    casex = int(sys.argv[2])
    temp_folder = sys.argv[4]
    shape = str(sys.argv[3])
    
    m, n, geometry = int(pyin[0]), int(pyin[1]), int(pyin[2])
    
    lattice_data, analyzer = create_lattice(m,n,geometry,shape,casex)
    with open(os.path.join(temp_folder, "lattice.json"), "w") as f:
        json.dump(lattice_data, f)