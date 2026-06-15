import json
import sys
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
import os

angles = [0, np.pi/6, np.pi/3, np.pi/2, 2*np.pi/3, np.pi, 4*np.pi/3, 3*np.pi/2, 5*np.pi/3]
rotation_matrices = [np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]) for angle in angles]
mirror_matrices = [
    np.array([[1, 0], [0, 1]]),    # identity (no mirror)
    np.array([[-1, 0], [0, 1]]),   # mirror x
    np.array([[1, 0], [0, -1]]),   # mirror y
    np.array([[-1, 0], [0, -1]])   # mirror x and y
]
TRANSFORMATIONS = []
for R in rotation_matrices:
    for M in mirror_matrices:
        TRANSFORMATIONS.append(np.dot(R, M))

def normalize_circuit(circuit):
    cycle = circuit[:-1]
    all_representations = []
    for matrix in TRANSFORMATIONS:
        transformed = [tuple(np.round(np.dot(matrix, point), 8)) for point in cycle]
        min_x = min(p[0] for p in transformed)
        min_y = min(p[1] for p in transformed)
        normalized = tuple((x - min_x, y - min_y) for x, y in transformed)
        for i in range(len(normalized)):
            rotated = normalized[i:] + normalized[:i]
            all_representations.append(rotated)
            all_representations.append(rotated[::-1])
    return min(all_representations)

def create_opposite_paths_from_circuits(circuits):
    results = {}
    for idx, circuit in enumerate(circuits):
        mid_index = len(circuit) // 2
        path1_list, path2_list = [], []
        seen = set()
        for i in range(mid_index):
            path1 = circuit[i:i + mid_index]
            path2 = (circuit[i + mid_index:-1] + circuit[0:i])[::-1]
            norm1 = normalize_circuit(path1+path2[::-1])
            norm2 = normalize_circuit(path2[::-1]+path1)
            if (norm1 or norm2) not in seen:
                seen.add(norm1)
                seen.add(norm2)
                path1_list.append(path1)
                path2_list.append(path2)
            
        results[idx] = {
            "path1list": path1_list,
            "path2list": path2_list,
        }
    return results

def edge_match(edge1, edge2):
    return np.allclose(edge1, edge2, atol=1e-4)

def reflect_point_about_line(point, line_start, line_end):
    x0, y0 = point
    x1, y1 = line_start
    x2, y2 = line_end
    a = y2 - y1
    b = x1 - x2
    c = - (a * x1 + b * y1)
    denom = a**2 + b**2
    x_reflected = x0 - 2 * a * (a * x0 + b * y0 + c) / denom
    y_reflected = y0 - 2 * b * (a * x0 + b * y0 + c) / denom
    return (x_reflected, y_reflected)

def reflect_edge_about_edge(edge_input, edge_mirror):
    reflected_start = reflect_point_about_line(edge_input[0], edge_mirror[0], edge_mirror[1])
    reflected_end = reflect_point_about_line(edge_input[1], edge_mirror[0], edge_mirror[1])
    return (reflected_start, reflected_end)

def reflect_edge_along_path(edge, path, edge_mid_lookup):
    edge_to_mirror = edge
    reflections = []
    for i in range(len(path) - 1):
        mirror_node = ((path[i][0]+path[i+1][0])/2, (path[i][1]+path[i+1][1])/2)
        g1_edge = edge_mid_lookup.get(tuple(np.round(mirror_node, 4)))
        if g1_edge is not None:
            v = reflect_edge_about_edge(edge_to_mirror, g1_edge)
            edge_to_mirror = v
            reflections.append(v)
    return (reflections[-1] if reflections else edge), (reflections if reflections else [])

def process_circuit(args):
    circuit_idx, paths, edge_mid_lookup = args
    foldable = []
    for i, (path1, path2) in enumerate(zip(paths["path1list"], paths["path2list"])):
        if not path1 or not path2:
            continue
        node1, node2 = path1[0], path1[-1]
        node3, node4 = path2[0], path2[-1]
        startnode_path = ((node1[0] + node3[0]) / 2, (node1[1] + node3[1]) / 2)
        endnode_path = ((node2[0] + node4[0]) / 2, (node2[1] + node4[1]) / 2)
        start_edge = edge_mid_lookup.get(tuple(np.round(startnode_path, 4)))
        target_edge = edge_mid_lookup.get(tuple(np.round(endnode_path, 4)))
        if start_edge is not None and target_edge is not None:
            reflected_edge1, _ = reflect_edge_along_path(start_edge, path1, edge_mid_lookup)
            reflected_edge2, _ = reflect_edge_along_path(start_edge, path2, edge_mid_lookup)
            if (edge_match(reflected_edge1, reflected_edge2) and
                edge_match(reflected_edge1, target_edge)):
                foldable.append((circuit_idx, i))
    return foldable

def find_foldable_circuits_parallel(results, G1_edges):
    edge_mid_lookup = {}
    for edge in G1_edges:
        edge_mid = ((edge[0][0] + edge[1][0]) / 2, (edge[0][1] + edge[1][1]) / 2)
        edge_mid_lookup[tuple(np.round(edge_mid, 4))] = edge

    # Prepare arguments for parallel processing
    args_list = [(circuit_idx, paths, edge_mid_lookup) for circuit_idx, paths in results.items()]

    foldable_circuits = []
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(process_circuit, args) for args in args_list]
        for future in as_completed(futures):
            foldable_circuits.extend(future.result())
    unique_foldable_circuits = list(set(foldable_circuits))
    return unique_foldable_circuits

if __name__ == "__main__":
    temp_folder = sys.argv[1]
    with open(os.path.join(temp_folder, "hamiltonian_circuits.json")) as f:
        ham_circuits = json.load(f)
    with open(os.path.join(temp_folder, "lattice.json")) as f:
        lattice_data = json.load(f)
    results = create_opposite_paths_from_circuits(ham_circuits)
    G1_edges = [(tuple(e[0]), tuple(e[1])) for e in lattice_data["G1_edges"]]
    foldable = find_foldable_circuits_parallel(results, G1_edges)
    foldable_map = []
    seen_combinations = set()  # Track unique combinations to avoid duplicates
    
    for circuit_idx, path_number in foldable:
        combination_id = (circuit_idx, path_number)
        if combination_id in seen_combinations:
            continue
        seen_combinations.add(combination_id)
        
        circuit = ham_circuits[circuit_idx]
        path1 = results[circuit_idx]["path1list"][path_number]
        path2 = results[circuit_idx]["path2list"][path_number]
        foldable_map.append({
            "circuit": circuit,
            "path1": path1,
            "path2": path2
        })

    with open(os.path.join(temp_folder, "foldable_circuits.json"), "w") as f:
        json.dump(foldable_map, f,)
