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
| Hero plane, every enemy, the boss | Spine skeletons under `Assets/SpineObjects/**`, rendered to sprites |
| Gems, coins, meat, magnet | `Assets/Sprites/Collectibles/Collectible.png` |
| Sky gradient, cloud layers | `Assets/BG/BGDataNew/.../BG_Day_SpriteSheet.png`, `BGDataOld/.../clouds*.png` |
| HUD icons (time / kills / wave) | `Assets/Survival/*_Icon.png` |
| Font (Luckiest Guy) | `Assets/GameFont/LuckiestGuy-Regular.ttf` |
| Store package name | `Assets/google-services.json` |

Sprites were composed from the Spine skeletons' setup pose (bone hierarchy,
region + weighted-mesh attachments) rather than hand-cropped from the atlases, so
the planes match the shipped art.

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
