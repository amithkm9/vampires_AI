# Server protocol implementation

Source: [Projectv10.pdf](reference/Projectv10.pdf), pp. 5-9. Every command begins with three ASCII bytes. Every numeric field below is one unsigned byte; there is no newline, JSON envelope, or general packet-length prefix.

| Direction | Command | Payload |
| --- | --- | --- |
| Server to client | SET | rows, columns |
| Server to client | HUM | house count, then `(x,y)` for each house |
| Server to client | HME | our starting x, y |
| Server to client | MAP | cell count, then `(x,y,humans,vampires,werewolves)` records |
| Server to client | UPD | update count, then records with the same layout as MAP |
| Server to client | END | None; reset game state, keep connection |
| Server to client | BYE | None; finish connection |
| Client to server | NME | ASCII byte length, then name bytes |
| Client to server | MOV | move-record count, then `(source_x,source_y,count,target_x,target_y)` records |

The name and record counts fit within one byte. Coordinates are x before y; SET is rows before columns. `model.Board` explicitly handles rectangular maps to avoid mixing these conventions.

## Lifecycle

```text
connect -> NME -> SET -> HUM -> HME -> MAP
                                      |
                                      v
                    UPD -> decide -> validate -> MOV
                     ^                           |
                     +---------------------------+

END -> clear board/species/home/houses -> next SET on the same connection
BYE or socket EOF -> finish the connection
```

An empty initial UPD still signals our turn. MAP alone does not. Treat UPD entries as replacement populations: an all-zero entry removes an occupied cell. Do not apply our predicted result to the authoritative board and then add the server values; that would double-count changes.

## Implemented safeguards

- `protocol.recv_exact` handles partial TCP reads and detects EOF instead of looping forever.
- `protocol.read_message` reads only the required bytes, so coalesced packets remain aligned.
- `protocol.Client` uses `sendall` and validates moves before transmission.
- `model.GameSession.apply` enforces initialization order, identifies our species from HME/MAP, and handles multiple games.
- `ConnectionClosed`, `ProtocolError`, and state validation errors remain explicit. `player.main` logs them and exits nonzero; it does not silently reconnect into an unknown match.
- `read_message` timestamps the first `U` byte of UPD. The remaining header and payload fragments share one two-second absolute deadline; completed reads are also checked for lateness. Socket timeouts restore after success or failure. Non-UPD waiting is not charged as our turn.
- `player.play` includes update parsing in the search budget and passes the turn deadline to `Client.send_moves`. Late sends are rejected, and `sendall` has a remaining-time timeout. Waiting for other commands remains separate from our turn deadline.
- `run.py` launches from any working directory and accepts optional settings followed by the server IP and port. The client sends its name once per connection and preserves the connection across END.

## Integration still required

Socket-pair tests validate fragmented packets and game resets. `tools/check_player.py` additionally launches the real command in another directory, connects over loopback TCP, completes both species on both supplied maps, verifies legal MOV packets, and checks clean BYE exit. Its simulator is our own and cannot validate official-server parity. Official-server communication, TCP setup on CTI, and CTI end-to-end timing still need verification. Waiting for an opponent or a second player can legitimately take longer than two seconds.
