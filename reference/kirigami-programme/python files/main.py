import os
import subprocess
import json

CREATE_NO_WINDOW = 0x08000000
if __name__ == "__main__":

    script_dir = str(script_dir) #type: ignore
    #script_dir = os.path.dirname(os.path.abspath(__file__)) #Uncomment this line if you want to use the script directly from python
    temp_folder = os.path.join(script_dir, "temp")
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)

    """
    Example input:
    pyin = [4, 4, 6]  # m, n, Geometry
    casex = 1
    shape = "Regular Hexagon" 
    """
    
    m, n = int(pyin[0]),int(pyin[1]) # type: ignore
    Geometry = int(pyin[2]) # type: ignore
    casex = int(casex)  # type: ignore
    shape = str(shape)  # type: ignore
    
    # Step 1: Lattice creation
    subprocess.run(
        ["python", os.path.join(script_dir, "lattice.py"), json.dumps([m, n, Geometry]), str(casex), str(shape), temp_folder], #type: ignore
        check=True,creationflags=CREATE_NO_WINDOW
    )
    
    with open(os.path.join(temp_folder, "lattice.json"), "r") as f:
        lattice_data = json.load(f)
    LS = len(lattice_data["polygon_centers"])

    # Step 2: Condition 1 : Find all Hamiltonian circuits
    subprocess.run(
        ["python", os.path.join(script_dir, "hamiltonian.py"), temp_folder],
        check=True,creationflags=CREATE_NO_WINDOW
    )

    with open(os.path.join(temp_folder, "hamiltonian_circuits.json"), "r") as f:
        circuits = json.load(f)
    P = len(circuits)
    
    if P:
        # Step 3: Vector Reflection of Hamiltonian circuits
        subprocess.run(
            ["python", os.path.join(script_dir, "twostack.py"), temp_folder],
            check=True,creationflags=CREATE_NO_WINDOW
        )

        with open(os.path.join(temp_folder, "foldable_circuits.json"), "r") as f:
            foldable_circuits = json.load(f)
        Q = len(foldable_circuits)

        # Step 4: Flat foldability check of Hamiltonian circuits
        subprocess.run(
            ["python", os.path.join(script_dir, "notwist.py"), temp_folder, "0"],
            check=True,creationflags=CREATE_NO_WINDOW
        )

        with open(os.path.join(temp_folder, "valid_circuits1.json"), "r") as f:
            valid_circuits = json.load(f)
        R = len(valid_circuits)

        # Step 5: Flat foldability check of valid vector reflected circuits
        subprocess.run(
            ["python", os.path.join(script_dir, "notwist.py"), temp_folder, "1"],
            check=True,creationflags=CREATE_NO_WINDOW
        )

        with open(os.path.join(temp_folder, "valid_circuits2.json"), "r") as f:
            valid_circuits = json.load(f)
        S = len(valid_circuits)

    else:
        Q = 0
        R = 0
        S = 0


"""
print(f"Number of Polygons: {LS}")
print(f"Number of Hamiltonian circuits: {P}")
print(f"Number of foldable circuits is {Q}")
print(f"Number of valid Hamiltonian circuits: {R}")
print(f"Number of valid foldable circuits: {S}")
"""