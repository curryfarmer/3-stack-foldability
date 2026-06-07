import json
import numpy as np
import networkx as nx
import os
import sys

def angles_between_consecutive_edges(circuit):
    oddangles, evenangles = [], []
    edges = list(nx.utils.pairwise(circuit))
    n = len(edges)
    for i in range(n):
        p1, p2 = np.array(edges[i][0]), np.array(edges[i][1])
        p3 = np.array(edges[(i + 1) % n][1])
        v1, v2 = p2 - p1, p3 - p2
        mag_v1, mag_v2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if mag_v1 == 0 or mag_v2 == 0:
            angle = 0.0
        else:
            dot = np.dot(v1, v2)
            cross = np.cross([*v1, 0], [*v2, 0])[2]#type: ignore
            cos_theta = np.clip(dot / (mag_v1 * mag_v2), -1.0, 1.0)
            angle = np.round(np.degrees(np.arccos(cos_theta)))
            if cross < 0:
                angle = -angle
        angle = 2 * float(angle)
        (evenangles if i % 2 == 0 else oddangles).append(angle)
    return oddangles, evenangles

def check_valid_circuit(circuit):
    oddangles, evenangles = angles_between_consecutive_edges(circuit)
    return sum(oddangles) - sum(evenangles) == 0

if __name__ == "__main__":
    temp_folder = sys.argv[1]
    s = int(sys.argv[2])
    if s:
        with open(os.path.join(temp_folder, "foldable_circuits.json")) as f:
            circuits = json.load(f)

        valid_circuits = []

        for idx, circuit in enumerate(circuits):
            if check_valid_circuit(circuit["circuit"]):
                valid_circuits.append({
                    "circuit": circuit["circuit"],
                    "path1": circuit["path1"],
                    "path2": circuit["path2"]
                })
        
        #print(f"Found {len(valid_circuits)} valid circuits out of {len(circuits)} total circuits.")
        with open(os.path.join(temp_folder, "valid_circuits2.json"), "w") as f:
            json.dump(valid_circuits, f)
    else:
        with open(os.path.join(temp_folder, "hamiltonian_circuits.json")) as f:
            circuits = json.load(f)
        valid_circuits = [circuit for circuit in circuits if check_valid_circuit(circuit)]
        with open(os.path.join(temp_folder, "valid_circuits1.json"), "w") as f:
            json.dump(valid_circuits, f)



