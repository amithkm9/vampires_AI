"""Local TCP integration smoke test; NOT the supplied server or a strength benchmark."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import random
import socket
import subprocess
import sys
import tempfile
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vampires.model import Cell, Species, load_map
from vampires.protocol import recv_exact
from vampires.rules import Move, validate_moves
from vampires.simulation import single_moves, turn_outcomes


def updates(before, after):
    return tuple((x, y, cell.humans, cell.vampires, cell.werewolves)
                 for x, y in sorted(set(before) | set(after))
                 if (cell := after.get((x, y), Cell())) != before.get((x, y), Cell()))


def cell_packet(command, records):
    if len(records) > 255:
        raise ValueError("Harness packet exceeds one-byte record count")
    return command.encode("ascii") + bytes([len(records)]) + b"".join(bytes(row) for row in records)


def initial_packet(board, species):
    houses = [p for p, c in sorted(board.cells.items()) if c.humans]
    home = next(iter(board.groups(species)))
    return (b"SET" + bytes([board.rows, board.columns]) +
            b"HUM" + bytes([len(houses)]) + b"".join(bytes(p) for p in houses) +
            b"HME" + bytes(home) + cell_packet("MAP", updates({}, board.cells)))


def sampled_successor(board, species, moves, rng):
    # Exact support, seeded draw. The harness shares the transition model with
    # the agent, so it detects integration errors but cannot establish parity.
    outcomes = turn_outcomes(board, species, moves)
    draw, cumulative = rng.random(), 0.0
    for outcome in outcomes:
        cumulative += float(outcome.probability)
        if draw < cumulative:
            return outcome.board
    return outcomes[-1].board  # Floating-point cumulative rounding only.


def run_check(*, budget=.05, depth=2, max_plies=40, seed=20261009):
    if type(max_plies) is not int or max_plies < 2:
        raise ValueError("max_plies must be at least 2")
    started = monotonic()
    matches = []
    with tempfile.TemporaryDirectory(prefix="vampires-launch-") as cwd:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(10)
            port = listener.getsockname()[1]
            command = [sys.executable, str(ROOT / "run.py"), "--name", "SmokeTest",
                       "--budget", str(budget), "--depth", str(depth), "--quiet", "127.0.0.1", str(port)]
            process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(2)
                    if recv_exact(connection, 3) != b"NME":
                        raise AssertionError("Expected one initial NME")
                    name = recv_exact(connection, recv_exact(connection, 1)[0]).decode("ascii")
                    if name != "SmokeTest":
                        raise AssertionError("Incorrect player name")
                    for map_name in ("thetrap", "testmap2"):
                        path = ROOT / "maps" / (map_name + ".xml")
                        for species in Species:
                            match_seed = seed + len(matches)
                            rng = random.Random(match_seed)
                            board = load_map(path)
                            connection.sendall(initial_packet(board, species))
                            last_sent = dict(board.cells)
                            timings = []
                            current = Species.VAMPIRES
                            plies = 0
                            while plies < max_plies and all(board.groups(s) for s in Species):
                                if current == species:
                                    packet = cell_packet("UPD", updates(last_sent, board.cells))
                                    last_sent = dict(board.cells)
                                    turn_started = monotonic()
                                    connection.sendall(packet)
                                    if recv_exact(connection, 3) != b"MOV":
                                        raise AssertionError("Expected MOV on each UPD, with no extra NME after END")
                                    count = recv_exact(connection, 1)[0]
                                    body = recv_exact(connection, count * 5)
                                    elapsed = monotonic() - turn_started
                                    if elapsed >= 2:
                                        raise AssertionError(f"Response exceeded two seconds: {elapsed}")
                                    timings.append(elapsed)
                                    moves = tuple(Move(*body[i:i + 5]) for i in range(0, len(body), 5))
                                else:
                                    moves = (rng.choice(list(single_moves(board, current, whole_groups_only=True))),)
                                validate_moves(board, current, moves)
                                board = sampled_successor(board, current, moves, rng)
                                plies += 1
                                current = current.opponent
                            totals = {s.value: sum(board.groups(s).values()) for s in Species}
                            connection.sendall(b"END")
                            matches.append({"map": map_name, "map_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                            "species": species.value, "starting_species": "vampires", "seed": match_seed,
                                            "plies": plies, "ai_turns": len(timings), "populations": totals,
                                            "termination": "extinction" if not all(totals.values()) else "harness_ply_cap",
                                            "response_seconds": timings,
                                            "max_response_seconds": max(timings, default=0)})
                    connection.sendall(b"BYE")
                stdout, stderr = process.communicate(timeout=5)
                if process.returncode != 0:
                    raise AssertionError(f"Launcher exited {process.returncode}: {stderr}")
                if stdout or stderr:
                    raise AssertionError(f"Unexpected quiet-mode output: {stdout} {stderr}")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate()
    sources = sorted((ROOT / "src/vampires").glob("*.py")) + [ROOT / "run.py", Path(__file__)]
    return {"generated_utc": datetime.now(timezone.utc).isoformat(),
            "kind": "local_tcp_integration_smoke", "python": platform.python_version(),
            "platform": platform.platform(), "elapsed_seconds": monotonic() - started,
            "configuration": {"budget_seconds": budget, "max_depth": depth, "candidates": 64,
                              "max_plies": max_plies, "opponent": "seeded random whole-group single move",
                              "shared_target_battles": "rejected", "both_extinct": "neutral model convention"},
            "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
            "checks": {"different_working_directory": True, "persistent_connection": True,
                       "both_species_each_map": True, "legal_moves_only": True, "clean_bye_exit": True},
            "limitations": "Shares our simulator, not the official server; no CTI timing or playing-strength claim. "
                           "Wall-clock search limits can change actions despite fixed random seeds.",
            "matches": matches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=float, default=.05)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--max-plies", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20261009)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_check(budget=args.budget, depth=args.depth, max_plies=args.max_plies, seed=args.seed)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(f"Passed {len(result['matches'])} local TCP matches; saved {args.output}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
