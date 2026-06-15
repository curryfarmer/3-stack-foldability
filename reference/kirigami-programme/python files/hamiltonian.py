import json
import networkx as nx
import numpy as np
from collections import defaultdict, deque
from concurrent.futures import ProcessPoolExecutor, as_completed
import os
import sys

# Precompute transformations once
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


def find_hamiltonian_circuits_worker(G2_nodes, G2_edges, start, first_neighbor):
    G2 = nx.Graph()
    G2.add_nodes_from([tuple(node) for node in G2_nodes])
    G2.add_edges_from([(tuple(e[0]), tuple(e[1])) for e in G2_edges])
    all_nodes = set(G2.nodes())
    neighbors = defaultdict(list, {node: list(G2.neighbors(node)) for node in G2.nodes()})
    path = deque([start, first_neighbor])
    visited = {start, first_neighbor}
    hamiltonian_circuits = []

    def backtrack():
        if len(path) == len(all_nodes):
            if start in neighbors[path[-1]]:
                circuit = list(path) + [start]
                hamiltonian_circuits.append([list(p) for p in circuit])
            return
        current = path[-1]
        for neighbor in neighbors[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                path.append(neighbor)
                backtrack()
                path.pop()
                visited.remove(neighbor)
    backtrack()
    return hamiltonian_circuits

def find_hamiltonian_circuits_parallel(G2_nodes, G2_edges, start):
    G2 = nx.Graph()
    G2.add_nodes_from([tuple(node) for node in G2_nodes])
    G2.add_edges_from([(tuple(e[0]), tuple(e[1])) for e in G2_edges])
    neighbors = list(G2.neighbors(start))
    results = []
    with ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(find_hamiltonian_circuits_worker, G2_nodes, G2_edges, start, neighbor)
            for neighbor in neighbors
        ]
        for future in as_completed(futures):
            results.extend(future.result())
    # Remove duplicates using normalization
    seen = set()
    unique_circuits = []
    for circuit in results:
        norm = normalize_circuit(circuit)
        if norm not in seen:
            seen.add(norm)
            unique_circuits.append(circuit)
    return unique_circuits

if __name__ == "__main__":
    temp_folder = sys.argv[1]
    with open(os.path.join(temp_folder, "lattice.json")) as f:
        lattice_data = json.load(f)
    start = tuple(lattice_data["polygon_centers"]["0"])
    circuits = find_hamiltonian_circuits_parallel(lattice_data["G2_nodes"], lattice_data["G2_edges"], start)
    with open(os.path.join(temp_folder, "hamiltonian_circuits.json"), "w") as f:
        json.dump(circuits, f)
