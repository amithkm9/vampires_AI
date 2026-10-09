# Supplied material audit

Audit date: 2026-10-08. The original input consisted of one PDF and three ZIP archives. All extracted files were reviewed as text where applicable; executable files were identified by format and configuration, not executed or reverse engineered.

## Inventory

| Input | Bytes | Extracted content |
| --- | ---: | --- |
| Projectv10.pdf | 832453 | Nine pages; searchable text saved separately |
| starterkit.zip | 1569 | `client.py`, `main.py` |
| Server v3.2.1.zip | 150774 | Server EXE, configuration, `VVSW.Controls.dll`, `VVSW.Model.dll` |
| Map generator.zip | 3769 | Generator EXE, `testmap2.xml`, `thetrap.xml` |

The integrity manifest records hashes and original archive member names. The generator archive's extra top-level directory was flattened into `vendor/map-generator/`; no file contents changed. Working maps are byte-identical copies.

## Starter kit findings

| File | Finding | Working implementation response |
| --- | --- | --- |
| client.py | Imports `config`, which is absent | Require connection arguments explicitly in our client |
| client.py | `_get_message` asks for `1 - len(data)` bytes instead of the remaining requested length | Implement one reusable exact-length reader |
| client.py | Read loops do not break on an empty `recv` result | Raise `ConnectionClosed` on EOF |
| client.py | Uses `send`, which may send only part of a packet | Use `sendall` |
| client.py | Name encoding/length and moves are not fully validated | Enforce ASCII and one-byte bounds; validate legal turns before send |
| main.py | `UPDATE_GAME_STATE`, `COMPUTE_NEXT_MOVE`, and `GAME_STATE` are undefined placeholders | Add state model now; forward model and strategy remain planned |
| main.py | `play_game(strategy, args)` is called with no arguments | Build a clean CLI when strategy integration starts |
| main.py | END/BYE exceptions are not handled in the main loop | Model game reset and terminal shutdown explicitly |
| main.py | Records a timestamp but does not enforce a deadline | Add a measured monotonic deadline in the strategy/launcher milestone |

The `_get_message` length bug is latent for the supplied parser's one-byte calls, but the helper would fail for larger reads. The missing configuration and incorrect main call already prevent the unmodified kit from running as a complete player.

## Server and map generator

The EXE/DLL files are PE32 Intel 80386 .NET assemblies for Windows. The server EXE is a GUI application; the generator is a console application. The configuration requests .NET Framework 4.5. This environment is macOS, with no `dotnet`, `mono`, or `wine` command found. Compatibility and official-server behavior have not been validated.

The supplied server config sets:

| Key | Value | Consequence |
| --- | --- | --- |
| ServerIP | 127.0.0.1 | Local loopback default |
| ServerPort | 5555 | Example port; client must accept dynamic values |
| DebugMode | True | Supplied debug setting |
| PlayersCount | 1 | Prepare an appropriate separate config for two AI players |
| Map | testmap.xml | This map is not in any supplied archive |
| MaxGameDuration | 00:05:00 | Supplied five-minute game cap; not a confirmed tournament setting |
| MaxPlayDuration | 00:00:05 | Conflicts with the brief's two-second allowance; follow the brief |
| MaxPlays | 200 | Supplied ply cap; not a confirmed tournament setting |
| AutoRestart | False | Repeated-game behavior still needs an official-server check |

Do not treat this unmodified configuration as a ready tournament setup. Create a working copy with a valid supplied map when server access is available.

## Supplied maps

| Map | Dimensions | Humans | Starting populations |
| --- | --- | --- | --- |
| testmap2.xml | 15 rows, 29 columns | 32 across 5 houses | Werewolves 10 at (0,0); vampires 10 at (28,14) |
| thetrap.xml | 5 rows, 10 columns | 9 across 4 houses | Werewolves 4 at (4,1); vampires 4 at (4,3) |

The large map has distant opposing starts and a central group of 20 humans; it is useful for testing growth and travel decisions. The trap map places the species close together with a 4-human house at (2,2); it is useful for inspecting opponent-aware tactical choices. These are interpretations of map structure, not measured conclusions about winning strategies.
