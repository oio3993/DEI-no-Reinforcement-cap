# Compatibility

[README](../README.md) · [Build](build.md) · [Patch implementation](patch-notes.md)

## Requirements

Windows with Total War Rome II and Divide et Impera. The campaign integration
targets single-player campaign battles with an attacker and defender present.

The native patch supports the x86 `empire.retail.dll` with this SHA-256.

```text
07cb2215b80591224a5f8889963344d560492f09c4d22696c988b957ca49b2b7
```

The DLL checks the engine hash and patch-location bytes before applying changes.
A game update that changes this engine file requires a corresponding mod update.

## Battle types

| Condition | Arrival-capacity patch |
| --- | --- |
| Any battle-type value in a supported single-player campaign | Both sides |
| AI main forces with the player joining as reinforcements | Both sides |
| AI-only pending battle | Both sides |

The campaign module requests `rrc_install` for all battle-type values, including
sallies, relief battles, forts, ambushes, coastal battles and naval battles.
Eligibility depends on the single-player campaign callbacks and the presence of
both main sides. Standalone custom and historical battles use separate entry
points from this campaign integration.

## Replays

The single-player replay browser requests the same arrival-capacity patch when
opened from the main menu. Watch and Fight repeat the request, including after a
fresh game launch. Use recordings made with the corresponding mod settings.

Frontend callbacks handle replay entry, menu return and campaign handoff. They
share the native patch state with campaign callbacks, which reset and install
the patch before a pending campaign battle.

Supporting forces follow the game's reinforcement arrival process. The native
patch bypasses one arrival-capacity predicate call. Other arrival conditions,
batch processing, battlefield constraints and practical performance limits
continue to apply.

## Campaigns

The pack includes these campaign entry points.

```text
main_3c          main_emperor     main_gaul
main_greek       main_invasion    main_punic
main_rome        prologue_01      prologue_02
```

Other campaign folders require their own integration. The pack uses the recorded
DEI campaign scripts. Source builds check their hashes as described in the
[build guide](build.md#supply-local-dei-inputs-and-build-the-pack).

## Mod conflicts

This pack's campaign `scripting.lua` and `lua_scripts/frontend_scripted.lua`
entries must take priority over DEI's entries. Another mod replacing those same
scripts needs a combined integration.
Mods patching the same engine call can also conflict.

Initial deployment mods can include this same capacity bypass. Choose one active
implementation when both mods patch RVA `0x2F65D2`.

## Loading problems

- The game must use its normal working directory containing `Rome2.exe`.
- The loader needs permission to create its mod DLL in that directory. An
  identical existing DLL is reused.
- A different or unreadable file named `rdp_rrc_sp01_63d42188045383cf.dll` prevents
  loading. Close the game and check that specific mod file if loading fails.
- Security software and application-control policies can block DLL creation or
  loading. The game may continue running while the mod has no effect.

Frontend event and loading diagnostics are written to
`rdp_rrc_replay_frontend_test01.log` in the game working directory.
`native_call_returned` records a completed Lua invocation. Installation also
depends on the native guards and memory update operations.

When reporting an issue, include the campaign, battle situation, engine version
and other active mods.
