"""Launch from any working directory: python3 /path/to/run.py [options] IP PORT."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from vampires.player import main


if __name__ == "__main__":
    raise SystemExit(main())
