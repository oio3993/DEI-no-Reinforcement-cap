# DEI No Reinforcement Cap

Allows supporting armies and fleets to arrive beyond the reinforcement
arrival-capacity limit in **Total War Rome II** with **Divide et Impera**.

## Features

- Reinforcement arrival-capacity bypass for both sides.
- All battle-type values are eligible in supported single-player campaigns.
- Supports battles with AI main forces when the player joins as reinforcements.
  AI-only pending battles are also eligible.
- Automatic DLL loading from the pack.

## Requirements

- [Total War Rome II](https://store.steampowered.com/app/214950/Total_War_ROME_II__Emperor_Edition/) on Windows.
- [Divide et Impera](https://divideetimperamod.com/).
- A supported single-player campaign and engine build.

Supporting forces use the game's reinforcement arrival mechanism. See
[compatibility](docs/compatibility.md) for campaigns, conflicts and loading
requirements.

## Install

1. Close the game.
2. Copy `rdp_reinforcement_cap_v01_singlepack_all_battles01.pack` into the game's
   `data` folder and enable it in your mod manager.
3. Set its load priority above DEI so its campaign scripts take precedence.

The pack automatically creates `rdp_rrc_sp01_63d42188045383cf.dll` in the game
folder when a campaign loads. Choose one mod when using this pack or an initial
deployment mod that patches the same arrival-capacity call.

## Remove

Close the game and disable or remove the pack. You may also remove
`rdp_rrc_sp01_63d42188045383cf.dll` from the game folder.

## Source and development

Native C and campaign Lua sources are in `src/native/` and `src/lua/`.
Building the pack requires your own matching DEI campaign scripts.

- [Build and test](docs/build.md)
- [Patch implementation](docs/patch-notes.md)
- [Changelog](CHANGELOG.md)

## Author and license

By [oio3993](https://github.com/oio3993) (Steam / GitHub / Discord).

Copyright (c) 2026 oio3993. [MIT License](LICENSE).
Game and DEI assets remain subject to their own terms.
