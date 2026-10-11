"""Persistent tournament client and command-line entry point."""

import argparse
from dataclasses import dataclass
import logging
from math import isfinite
from time import monotonic

from .model import GameSession
from .protocol import Client, ConnectionClosed, encode_name
from .search import SearchConfig, choose_turn

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionResult:
    turns: int
    games: int


def play(client, *, name="vampires_AI", budget=1.25, config=None, clock=monotonic):
    """Run until BYE; only authoritative MAP/UPD packets alter our game state.

    Timing starts when the UPD header is recognized, including payload parsing,
    updates, generation, search, validation, and transmission. Search reserves
    at least half a second of the brief's two-second limit for other work.
    This is cooperative timing, not a hard real-time or CTI guarantee.
    """
    if not isfinite(budget) or not 0 < budget <= 1.5:
        raise ValueError("Search budget must be finite and in (0, 1.5] seconds")
    encode_name(name)
    config = config or SearchConfig()
    client.send_name(name)
    session = GameSession()
    turns = games = 0
    while not session.closed:
        message = client.receive()
        start = message.received_at if message.received_at is not None else clock()
        ready = session.apply(message)
        if message.command == "END":
            games += 1
            LOG.info("game ended; waiting for the next SET")
        if not ready:
            continue
        decision = choose_turn(session.board, session.species, expires_at=start + budget,
                               time_budget=budget, config=config, clock=clock)
        client.send_moves(session.board, session.species, decision.moves,
                          deadline=start + 2.0, clock=clock)
        turns += 1
        LOG.info("turn=%d species=%s depth=%d selected_depth=%d nodes=%d selective=%d "
                 "unsupported=%d search_timeout=%s elapsed=%.4fs moves=%s",
                 turns, session.species.value, decision.completed_depth, decision.selected_depth,
                 decision.nodes, decision.selective_nodes, decision.unsupported_actions,
                 decision.timed_out, clock() - start,
                 [move.as_tuple() for move in decision.moves])
    return SessionResult(turns, games)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Opponent-aware Vampires vs Werewolves baseline")
    parser.add_argument("--name", default="vampires_AI", help="ASCII team name (1..255 bytes)")
    parser.add_argument("--budget", type=float, default=1.25, help="search seconds, >0 and <=1.5")
    parser.add_argument("--depth", type=int, default=3, help="maximum depth, 2..8 player turns")
    parser.add_argument("--candidates", type=int, default=64, help="maximum retained turns per node")
    parser.add_argument("--quiet", action="store_true", help="only log errors")
    parser.add_argument("host", help="server IP address or hostname; penultimate argument")
    parser.add_argument("port", type=int, help="server port; final argument")
    args = parser.parse_args(argv)
    try:
        encode_name(args.name)
        if not 1 <= args.port <= 65535:
            raise ValueError("port must be in 1..65535")
        if not isfinite(args.budget) or not 0 < args.budget <= 1.5:
            raise ValueError("budget must be finite and in (0, 1.5] seconds")
        if not 2 <= args.depth <= 8:
            raise ValueError("depth must be in 2..8; the player must consider opponent replies")
        config = SearchConfig(max_depth=args.depth, candidates=args.candidates)
    except ValueError as exc:
        parser.error(str(exc))
    logging.basicConfig(level=logging.ERROR if args.quiet else logging.INFO,
                        format="%(levelname)s %(message)s")
    try:
        with Client.connect(args.host, args.port) as client:
            result = play(client, name=args.name, budget=args.budget, config=config)
        LOG.info("BYE received: %d games, %d turns", result.games, result.turns)
        return 0
    except (ConnectionClosed, OSError, ValueError) as exc:
        LOG.error("Player stopped: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
