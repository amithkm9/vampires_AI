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
- `ConnectionClosed`, `ProtocolError`, and state validation errors remain explicit. The future launcher must catch and log them appropriately.

## Integration still required

The test fixture validates packet bytes and two game resets over a local socket pair. The official server, TCP connection setup on CTI, search/decision loop, command-line launcher, disconnect policy, and end-to-end two-second timing still need verification. The connection's read wait is separate from our computation deadline: waiting for an opponent or a second player can legitimately take longer than two seconds.
