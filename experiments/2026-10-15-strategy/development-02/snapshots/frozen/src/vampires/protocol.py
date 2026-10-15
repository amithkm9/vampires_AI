"""Binary TCP protocol from the brief, pages 5-8. No game strategy lives here."""

from dataclasses import dataclass, field
from math import isfinite
import socket
from time import monotonic
from .rules import Move, validate_moves


class ProtocolError(ValueError):
    pass


class ConnectionClosed(EOFError):
    pass


@dataclass(frozen=True)
class Message:
    command: str
    payload: tuple = ()
    received_at: float | None = field(default=None, compare=False)


def _finite_time(value, label, *, positive=False):
    valid = type(value) in (int, float)
    if valid:
        try:
            valid = isfinite(value) and (not positive or value > 0)
        except OverflowError:  # An integer too large for socket/clock floats.
            valid = False
    if not valid:
        suffix = "positive and finite" if positive else "finite"
        raise ValueError(f"{label} must be {suffix}")


def recv_exact(connection, size, *, deadline=None, clock=monotonic):
    """TCP may split or combine packets; EOF must not create an infinite loop."""
    if type(size) is not int or size < 0:
        raise ValueError("Receive size must be a nonnegative integer")
    if deadline is not None:
        _finite_time(deadline, "Receive deadline")
    original_timeout = connection.gettimeout() if deadline is not None else None
    data = bytearray()
    try:
        while len(data) < size:
            if deadline is not None:
                remaining = deadline - clock()
                if remaining <= 0:
                    raise TimeoutError("Turn deadline expired while receiving UPD")
                connection.settimeout(remaining if original_timeout is None else min(remaining, original_timeout))
            chunk = connection.recv(size - len(data))
            if not chunk:
                raise ConnectionClosed(f"Connection closed after {len(data)} of {size} bytes")
            data.extend(chunk)
            if deadline is not None and clock() >= deadline:
                raise TimeoutError("Turn deadline expired while receiving UPD")
        return bytes(data)
    finally:
        if deadline is not None:
            connection.settimeout(original_timeout)


def read_message(connection, *, turn_timeout=None, clock=monotonic):
    if turn_timeout is not None:
        _finite_time(turn_timeout, "Turn timeout", positive=True)
    # Waiting for an opponent is unbounded. Once U arrives, however, this is
    # already our UPD: header fragmentation must consume the same turn budget
    # as its payload. U is unique among all protocol command prefixes.
    first = recv_exact(connection, 1)
    received_at = clock() if first == b"U" else None
    deadline = (received_at + turn_timeout
                if received_at is not None and turn_timeout is not None else None)
    raw = first + recv_exact(connection, 2, deadline=deadline, clock=clock)
    try:
        command = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ProtocolError("Command must be ASCII") from exc
    if command in ("END", "BYE"):
        return Message(command)
    if command in ("SET", "HME"):
        return Message(command, tuple(recv_exact(connection, 2)))
    if command in ("HUM", "MAP", "UPD"):
        count = recv_exact(connection, 1, deadline=deadline, clock=clock)[0]
        width = 2 if command == "HUM" else 5
        body = recv_exact(connection, count * width, deadline=deadline, clock=clock)
        return Message(command, tuple(tuple(body[i:i + width])
                                      for i in range(0, len(body), width)), received_at)
    raise ProtocolError(f"Unknown command: {command!r}")


def encode_name(name):
    if not isinstance(name, str):
        raise ProtocolError("AI name must be a string")
    try:
        encoded = name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ProtocolError("AI name must be ASCII") from exc
    if not 1 <= len(encoded) <= 255:
        raise ProtocolError("AI name must occupy 1..255 bytes")
    return b"NME" + bytes([len(encoded)]) + encoded


def encode_moves(moves):
    """Encode byte layout only; use Client.send_moves for full rules validation."""
    moves = tuple(moves)
    if not 1 <= len(moves) <= 255:
        raise ProtocolError("MOV requires 1..255 move records")
    if not all(isinstance(move, Move) for move in moves):
        raise ProtocolError("MOV requires Move values")
    return b"MOV" + bytes([len(moves)]) + b"".join(bytes(m.as_tuple()) for m in moves)


class Client:
    def __init__(self, connection):
        self.connection = connection

    @classmethod
    def connect(cls, host, port, *, connect_timeout=10.0):
        connection = socket.create_connection((host, port), timeout=connect_timeout)
        # Opponent turns and waiting for a second player are not our move deadline.
        connection.settimeout(None)
        return cls(connection)

    def receive(self):
        return read_message(self.connection, turn_timeout=2.0)

    def send_name(self, name):
        self.connection.sendall(encode_name(name))

    def send_moves(self, board, species, moves, *, deadline=None, clock=monotonic):
        if deadline is not None:
            _finite_time(deadline, "Send deadline")
        moves = validate_moves(board, species, moves)
        packet = encode_moves(moves)
        if deadline is None:
            self.connection.sendall(packet)
            return
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError("Turn deadline expired before sending MOV")
        original_timeout = self.connection.gettimeout()
        try:
            self.connection.settimeout(remaining if original_timeout is None else min(remaining, original_timeout))
            self.connection.sendall(packet)
        finally:
            self.connection.settimeout(original_timeout)

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
