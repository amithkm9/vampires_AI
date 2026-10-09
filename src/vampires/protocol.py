"""Binary TCP protocol from the brief, pages 5-8. No game strategy lives here."""

from dataclasses import dataclass
import socket
from .rules import Move, validate_moves


class ProtocolError(ValueError):
    pass


class ConnectionClosed(EOFError):
    pass


@dataclass(frozen=True)
class Message:
    command: str
    payload: tuple = ()


def recv_exact(connection, size):
    """TCP may split or combine packets; EOF must not create an infinite loop."""
    if type(size) is not int or size < 0:
        raise ValueError("Receive size must be a nonnegative integer")
    data = bytearray()
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise ConnectionClosed(f"Connection closed after {len(data)} of {size} bytes")
        data.extend(chunk)
    return bytes(data)


def read_message(connection):
    raw = recv_exact(connection, 3)
    try:
        command = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ProtocolError("Command must be ASCII") from exc
    if command in ("END", "BYE"):
        return Message(command)
    if command in ("SET", "HME"):
        return Message(command, tuple(recv_exact(connection, 2)))
    if command in ("HUM", "MAP", "UPD"):
        count = recv_exact(connection, 1)[0]
        width = 2 if command == "HUM" else 5
        body = recv_exact(connection, count * width)
        return Message(command, tuple(tuple(body[i:i + width])
                                      for i in range(0, len(body), width)))
    raise ProtocolError(f"Unknown command: {command!r}")


def encode_name(name):
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
        return read_message(self.connection)

    def send_name(self, name):
        self.connection.sendall(encode_name(name))

    def send_moves(self, board, species, moves):
        moves = validate_moves(board, species, moves)
        self.connection.sendall(encode_moves(moves))

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
