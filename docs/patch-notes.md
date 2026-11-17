# Patch implementation and address notes

[README](../README.md) · [Compatibility](compatibility.md) · [Build](build.md)

The native DLL changes one engine call site to bypass a reinforcement
arrival-capacity predicate. The addresses below apply to the supported engine.

## Address convention

The supported engine is PE32 x86 with SHA-256
`07cb2215b80591224a5f8889963344d560492f09c4d22696c988b957ca49b2b7`.

An RVA is relative to the module base. The analysis used image base `0x10000000`,
so the Ghidra and IDA VA equals `0x10000000 + RVA`. At runtime the DLL uses the
loaded `empire.retail.dll` base plus RVA. ASLR can change that base. A file offset
is obtained separately from the PE section mapping.

| Purpose | Engine RVA | Analysis VA |
| --- | --- | --- |
| Arrival signature guard | `0x2F65D0` | `0x102F65D0` |
| Arrival-capacity call | `0x2F65D2` | `0x102F65D2` |
| Capacity-result test | `0x2F65D7` | `0x102F65D7` |
| Capacity-dependent jump | `0x2F65D9` | `0x102F65D9` |
| Blocking branch destination | `0x2F6826` | `0x102F6826` |
| Batch-context signature guard | `0x2F681D` | `0x102F681D` |
| Original capacity predicate | `0x304520` | `0x10304520` |

## Capacity call

Original bytes at RVA `0x2F65D2` are

```text
E8 49 DF 00 00          CALL 0x10304520
```

The target RVA follows from `0x2F65D2 + 5 + 0xDF49 = 0x304520`. The predicate
checks capacity against the owner's unit count and pending group contribution.
The following `TEST AL,AL` and `JNZ` select the blocking path when AL is nonzero.

The replacement bytes are

```text
30 C0 90 90 90          XOR AL,AL followed by three NOPs
```

They supply zero in AL and bypass the capacity-dependent jump. Both sides use
this shared arrival path. Engine arrival scheduling, batch processing and the
existing reinforcement construction mechanism continue to run.

## Campaign lifecycle and automatic loading

`rdp_reinforcement_cap_v01_campaign.lua` requests `rrc_disable` on `PendingBattle`,
checks single-player mode and the presence of an attacker and defender, then
requests `rrc_install`. Every battle-type value is eligible. The main-force
factions may be human or AI, covering a player who participates as reinforcements
and AI-only pending battles.

`UICreated` requests a reset and re-evaluates an active pending battle.
`BattleCompleted` requests `rrc_disable`.

The loader reads generated `rdp_reinforcement_cap_v01_payload.lua`, checks its
length and MZ prefix, verifies extracted bytes and loads the selected native
export. The generated decimal-byte payload is produced from the compiled DLL.
The build tools pin the DLL hash and complete generated representation.

The on-disk runtime name is `rdp_rrc_sp01_63d42188045383cf.dll`. The build output
is `rdp_reinforcement_cap_v01.dll`. The mod DLL uses preferred image base
`0x62000000`.

## Replay frontend lifecycle

`frontend_scripted.lua` receives the matching DEI script followed by
`integration/frontend_bootstrap.lua`. The protected bootstrap starts
`rdp_rrc_replay_frontend_test01.lua`, which reuses the loader and native exports.

The frontend prepares the DLL and requests a reset on FrontEnd UI creation. Entry
to `sp_replays` requests `rrc_install`. Watch and Fight request installation again.
Replay entry retains the request while the frontend UI is destroyed. Menu return,
navigation away from the replay browser and recognized multiplayer screens
request a reset. Campaign UI creation releases frontend bookkeeping, and campaign
callbacks manage subsequent pending battles.

Callbacks retain a short-lived replay context to accept a queued Watch/Fight
event during the transition. Battle or campaign UI creation clears that context.
Re-registration retires the earlier callback closures. The diagnostic log records
up to 256 entries per module lifetime.

Campaign and frontend callbacks share process-wide native state. The native DLL
is the same 8,142-byte binary used by AllBattles01, with SHA-256
`63d42188045383cfa615f2165662902be92049dee70b0712176076456c41fcd2`.

## Native guards and restoration

Installation verifies the engine file SHA-256, a 15-byte arrival signature at
RVA `0x2F65D0`, a 9-byte batch signature at RVA `0x2F681D` and the original
five-byte call. It pins the mod DLL in the process before installation.

The patch uses `VirtualProtect`, writes the five bytes, flushes the instruction
cache, verifies the result and restores the page permissions. Failed updates
attempt to restore the prior bytes and permissions. Disabling checks for the
expected installed bytes before restoring the original call.

The Lua exports return zero Lua values. The campaign wrapper's `pcall` result
reports Lua invocation success. Actual installation also depends on the native
guards and memory operations.
