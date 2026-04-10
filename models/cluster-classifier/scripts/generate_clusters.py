#!/usr/bin/env python3
"""
Generate a JSON dataset of 2D points in two clusters (left=0, right=1).

Usage:
    python generate_clusters.py --n-samples 200 --output dataset.json
"""

import argparse
import json
import sys

import numpy as np


def main():
    parser = argparse.ArgumentParser(description="Generate 2-cluster dataset")
    parser.add_argument("--n-samples", type=int, default=200, help="Total number of points (split evenly)")
    parser.add_argument("--output", type=str, default=None, help="Output file path (default: stdout)")
    parser.add_argument("--seed", type=int, default=123, help="Random seed")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    half = args.n_samples // 2

    left = rng.normal(loc=[-2.0, 0.0], scale=0.8, size=(half, 2))
    right = rng.normal(loc=[2.0, 0.0], scale=0.8, size=(args.n_samples - half, 2))

    dataset = []
    for point in left:
        dataset.append({"input": point.tolist(), "expected": 0})
    for point in right:
        dataset.append({"input": point.tolist(), "expected": 1})

    rng.shuffle(dataset)

    output = json.dumps(dataset, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Wrote {len(dataset)} samples to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
