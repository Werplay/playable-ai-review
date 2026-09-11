# Explottens: Survival — Playable Ad

A playable ad that recreates the **Survival** mode of
[`Explottens-FtP`](../Explottens-FtP) (the Unity project) in Phaser 3 + TypeScript,
built on [`@smoud/playable-sdk`](https://github.com/smoudjs/playable-sdk) and
[`@smoud/playable-scripts`](https://github.com/smoudjs/playable-scripts).

Everything ships as a single self-contained HTML file (~2 MB) with all art, the
game's own font, and code inlined.

## The loop

Drag anywhere to fly. The plane auto-fires at the nearest enemy. Cat planes and
bug-bots close in from every side in timed waves; kills drop XP gems that magnet
in, the XP bar fills, and each level-up pauses the run for a pick of three
upgrades. A HammerHead mini-boss joins at 0:44 and the vaderboss closes the run
at 1:18. Win or die, the end card offers the store link.

## What came from the Unity project

| Playable | Source in `Explottens-FtP` |
|---|---|
| XP curve `40L² + 80L − 20` | `Assets/Scripts/GameplayScripts/InGameXpHandler.cs` |
| Gem values 10 / 40 / 100 / 2000 | `Assets/Prefabs/Collectibles/XpItem.prefab` |
| Base ATK 10 / HP 100 | `Assets/Scripts/Player/PlayerStats.cs`, `Resources/CSV/SurvivorData/SurvivorLevelUpData.csv` |
| Skill names, descriptions, icons | `Assets/Prefabs/Skills/**/*.prefab` (`title` / `description` / `mainSprite`) |
| Wave structure (start/end, pool, cap) | `Assets/Scripts/EnemyWaves/EnemyWaveData.cs`, `EnemyWaveController.cs` |
| Hero plane, every enemy, the boss | Spine skeletons under `Assets/SpineObjects/**`, baked to animated sprite strips |
| Gems, coins, meat, magnet | `Assets/Sprites/Collectibles/Collectible.png` |
| Sky gradient, cloud layers | `Assets/BG/BGDataNew/.../BG_Day_SpriteSheet.png`, `BGDataOld/.../clouds*.png` |
| HUD icons (time / kills / wave) | `Assets/Survival/*_Icon.png` |
| Font (Luckiest Guy) | `Assets/GameFont/LuckiestGuy-Regular.ttf`, subset to ASCII and re-encoded woff2 (58 KB → 11 KB) |
| Store package name | `Assets/google-services.json` |

### How the characters were made

There is no Spine runtime in the bundle — `player.json` alone is 3.2 MB, which is
larger than the whole ad budget. Instead the skeletons are evaluated offline and
baked to sprite strips:

1. Sample the skeleton's own animation at `duration x 30` evenly-spaced times (the
   player plays `flying1`, everyone else an `idle`), interpolating bone
   rotate/translate/scale through Spine's linear, stepped and cubic-bezier curves.
   30 is the authoring rate: every keyframe in this project lands on a 1/30 s
   boundary and every duration is an exact multiple of it, and Spine omits
   `skeleton.fps` from the export when it equals its 30 default.
2. Resolve each slot's attachment for that frame, then draw region attachments as
   affine quads and mesh attachments triangle-by-triangle through their UVs —
   including weighted meshes and per-frame deform offsets, which is what moves the
   pilot's scarf and the wings.
3. Pack the frames into one horizontal strip on a shared bounding box so the sprite
   never jitters between cells, then quantize to 48 colours.

Phaser loads each strip with `load.spritesheet` and loops it over the animation's real
duration, so every character plays back at the same 30 fps it does in Unity. Enemies
start at a random point in the loop so a wave doesn't flap in lockstep.

`tools/build_assets.py` writes the `SHEETS` table in `src/data.ts` itself — frame
sizes and counts are derived from the PNGs it just produced rather than kept in sync
by hand. `createAnims` also takes its frame count from the decoded texture, so a
stale entry degrades the loop instead of throwing.

Cells are baked 1:1 with their on-screen size. The game canvas is CSS-pixel sized
rather than device-pixel sized, so oversampling buys no sharpness and is paid for
twice — once in PNG bytes, again in base64 inflation. Dropping from 1.35x to 1:1 is
what paid for the jump from 12-15 fps to the full 30.

One deliberate substitution: vaderboss ships two idle loops and the strip uses the
shorter `idle2` (0.53 s) rather than `idle` (1.0 s). Same 30 fps, half the frames —
`idle` alone was 126 KB, which did not fit.

## Tuning that is *not* from the game

A real Survival run lasts 10–20 minutes; this ad has ~95 seconds. Three knobs are
deliberately different and are marked as such in `src/data.ts`:

- `XP_RATE` scales gem XP so level-ups land every ~8–10 s.
- `PLAYER.health` is 140 rather than 100.
- Enemy `speed` values are raised so the swarm can close on a 250 px/s plane in a
  camera-sized arena.

## Layout

- `src/index.ts` — SDK init, font registration, Phaser boot
- `src/Game.ts` — `Phaser.Game` shell wired to the SDK lifecycle
- `src/GameScene.ts` — arena, player, waves, weapons, pickups, level-ups
- `src/Hud.ts` — run stats, boss bar, level-up picker, end card
- `src/data.ts` — the tables above (assets, skills, enemies, waves)
- `assets/` — extracted art + the game font

## Build

```bash
npm install
npm run dev                 # dev server with HMR
npm run build               # dist/Explottens_Survival_v1_<date>_en_<network>.html
./build-all.sh              # one file per ad network (needs build.js)
```

`build.json` carries the store links. The Google Play URL is the real package
(`com.playdew.explottensurvivors`); **the iOS link is a placeholder** — the
numeric App Store ID is not in the Unity repo, so swap it before shipping.

`build.js` and `dev.js` wrap `playable-scripts` to add `target: ['web','es5']` plus
`exportsPresence: 'error'` — webpack otherwise only *warns* when a named import does
not exist and hands you `undefined` at runtime. `babel.config.json`
down-levels the rest (Phaser included) — Mintegral rejects bundles that are not ES5. Note `loose: true` must stay off in that preset: it makes
Babel assume every spread target is an array, which silently turns
`[...map.values()]` into `[].concat(mapIterator)`.

## Verification

`GameScene` exposes itself on `window.__scene` so a headless run can read live state
(`state`, `elapsed`, `kills`, `level`, `hp`, `enemies`, `projs`). The build was checked
that way at 400x720, 780x400, 768x1024, 1024x768 and 320x640 plus a mid-run rotation:
60 fps throughout, no console or page errors, and no network request of any kind
leaving the page.
