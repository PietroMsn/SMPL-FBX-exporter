"""
attach_anim.py
Diagnostic script: loads a SURREAL info .mat file and prints the pose matrix.

Usage
-----
    python attach_anim.py
"""

import scipy.io as sio


MAT_FILE = "03_01_c0001_info.mat"


def main() -> None:
    mat_data = sio.loadmat(MAT_FILE)
    print(mat_data["pose"])


if __name__ == "__main__":
    main()
