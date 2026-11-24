"""
attach_anim.py
Diagnostic script: print the pose data stored in a SURREAL info .mat file.

Usage
-----
    python attach_anim.py <file_info.mat>
"""

import sys

import scipy.io as sio


def main():
    if len(sys.argv) != 2:
        print("Usage: python attach_anim.py <file_info.mat>")
        return 1

    pose = sio.loadmat(sys.argv[1])["pose"]
    print(f"pose array: shape {pose.shape} ({pose.shape[1]} frames x {pose.shape[0]} values)")
    print(pose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
