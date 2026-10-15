"""Persistent tournament client and command-line entry point."""

import argparse
from dataclasses import dataclass
import logging
from math import isfinite
from time import monotonic

from .model import GameSession
from .engines import DEFAULT_ENGINE, ENGINE_NAMES, choose_engine, default_depth
from .history import PositionHistory
from .protocol import Client, ConnectionClosed, encode_name
from .search import SearchConfig

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionResult:
    turns: int
    games: int
    repeated_turns: int = 0
    trailing_repeated_turns: int = 0


def play(client, *, name="vampires_AI", budget=1.25, config=None, clock=monotonic, engine=DEFAULT_ENGINE):
    """Run until BYE; only authoritative MAP/UPD packets alter our game state.

    Timing starts when the first UPD byte is received, including header/payload parsing,
    updates, generation, search, validation, and transmission. Search reserves
    at least half a second of the brief's two-second limit for other work.
    This is cooperative timing, not a hard real-time or CTI guarantee.
    """
    if not isfinite(budget) or not 0 < budget <= 1.5:
        raise ValueError("Search budget must be finite and in (0, 1.5] seconds")
    if engine not in ENGINE_NAMES:
        raise ValueError(f"Unknown engine: {engine}")
    encode_name(name)
    config = config or SearchConfig(max_depth=default_depth(engine))
    if config.max_depth < 2:
        raise ValueError("The live player must consider opponent replies (depth >= 2)")
    client.send_name(name)
    session = GameSession()
    history = PositionHistory()
    turns = games = 0
    repeated_turns = trailing_repeated_turns = 0
    while not session.closed:
        message = client.receive()
        start = message.received_at if message.received_at is not None else clock()
        initialized = session.species is not None
        ready = session.apply(message)
        if message.command in ("END", "BYE"):
            history.clear()
        if message.command == "END":
            games += int(initialized)
            LOG.info("game ended; waiting for the next SET")
        if not ready:
            continue
        repetition = history.observe(session.board, session.species)
        repeated_turns += repetition.visits > 1
        trailing_repeated_turns += repetition.review_trailing_cycle
        decision = choose_engine(session.board, session.species, engine=engine, expires_at=start + budget,
                                 time_budget=budget, config=config, clock=clock)
        client.send_moves(session.board, session.species, decision.moves,
                          deadline=start + 2.0, clock=clock)
        turns += 1
        LOG.info("turn=%d species=%s engine=%s depth=%d selected_depth=%d nodes=%d selective=%d "
                 "unsupported=%d bounded=%d generation_partial=%d certificate=%s "
                 "value_bounds=[%.5f,%.5f] search_timeout=%s elapsed=%.4fs "
                 "visits=%d cycle_updates=%s standing=%s trailing_cycle=%s horizon=unknown "
                 "root_started=%d root_updates=%d moves=%s",
                 turns, session.species.value, engine, decision.completed_depth, decision.selected_depth,
                 decision.nodes, decision.selective_nodes, decision.unsupported_actions,
                 decision.bounded_actions, decision.truncated_generations, decision.preserved_dominance,
                 decision.value_lower, decision.value_upper,
                 decision.timed_out, clock() - start,
                 repetition.visits, repetition.cycle_updates, repetition.standing,
                 repetition.review_trailing_cycle,
                 getattr(decision, "root_started", decision.evaluated_root_actions),
                 getattr(decision, "root_updates", 0),
                 [move.as_tuple() for move in decision.moves])
    return SessionResult(turns, games, repeated_turns, trailing_repeated_turns)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Opponent-aware Vampires vs Werewolves player")
    parser.add_argument("--name", default="vampires_AI", help="ASCII team name (1..255 bytes)")
    parser.add_argument("--engine", choices=ENGINE_NAMES, default=DEFAULT_ENGINE,
                        help="search variant; default strategic is provisionally promoted")
    parser.add_argument("--budget", type=float, default=1.25, help="search seconds, >0 and <=1.5")
    parser.add_argument("--depth", type=int, help="maximum depth, 2..8 plies; per-engine default 3 or 5")
    parser.add_argument("--candidates", type=int, default=64, help="maximum retained turns per node")
    parser.add_argument("--quiet", action="store_true", help="only log errors")
    parser.add_argument("host", help="server IP address or hostname; penultimate argument")
    parser.add_argument("port", type=int, help="server port; final argument")
    args = parser.parse_args(argv)
    if args.depth is None:
        args.depth = default_depth(args.engine)
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
            result = play(client, name=args.name, budget=args.budget, config=config, engine=args.engine)
        LOG.info("BYE received: %d games, %d turns", result.games, result.turns)
        return 0
    except (ConnectionClosed, OSError, ValueError) as exc:
        LOG.error("Player stopped: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
