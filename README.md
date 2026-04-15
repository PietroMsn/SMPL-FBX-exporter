Usage

    python main.py <pose_mat> <output_name> <mesh_mat> <scale>

    e.g. python main.py ./animations/bow_ext1.mat bow_ext1 ./meshes/MESH1Tpose.mat 5

Requirements:
Python 2.7

numpy>=1.24,<2.0
scipy>=1.10
transforms3d>=0.4.2
scikit-learn>=1.3
matplotlib>=3.7
chumpy


Add "models" directory in the root directory of the project and put the SMPL models (pkl files in it).
