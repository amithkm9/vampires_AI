"""Inspect a supplied XML map without the Windows map generator."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vampires.model import Species, load_map


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map", type=Path)
    args = parser.parse_args()
    board = load_map(args.map)
    print(f"{args.map.name}: {board.rows} rows x {board.columns} columns")
    houses = {p: c.humans for p, c in board.cells.items() if c.humans}
    print(f"Humans: {sum(houses.values())} across {len(houses)} houses")
    for species in Species:
        groups = board.groups(species)
        print(f"{species.value.title()}: {sum(groups.values())}; groups={groups}")


if __name__ == "__main__":
    main()
