# Asset pipeline

Regenerates everything in `../assets/` straight out of the Unity project. Run it
whenever the source art changes:

```bash
cd /path/to/Explottens-FtP/ExplottensUnityProject/Assets
python3 /path/to/playable-explottens-survivor/tools/build_assets.py
```

Needs Python 3 + Pillow. Paths to the Unity project and to `assets/` are constants
at the top of `build_assets.py`.

- `atlas.py` — parses libgdx/Spine `.atlas.txt` sheets (v3 and v4 layouts).
- `spineanim.py` — samples a Spine animation at time `t`: bone rotate/translate/scale
  with linear, stepped and cubic-bezier curves, slot attachment swaps, mesh deform.
- `spinestrip.py` — renders a posed skeleton (region quads + mesh triangles, weighted
  meshes included) and bakes N frames into one horizontal strip on a shared bounding box.
- `build_assets.py` — the manifest: which skeleton, which animation, how many frames,
  what cell width, plus the flat sprites (gems, projectiles, icons, HUD, background).
- `build_spine.py` — the player is the exception: it ships the live Spine skeleton rather
  than a baked strip, so the plane rolls through `flip1` on a direction switch the way the
  Unity build does. Trims the 3.2MB skeleton to plane 1, converts the 3.7 export to the 3.8
  shape Phaser's runtime wants, repacks the atlas at half resolution and centres the root
  bone on the flying pose. `--preview` renders the result for an eyeball check.
- `spine_check.js` — `node tools/spine_check.js`. Loads the generated files in the actual
  Spine runtime out of Phaser's plugin and poses every animation GameScene plays. Run it
  after `build_spine.py`; it is what catches a format regression.

Frame counts and cell sizes live in the `CHARS` table. If you change a cell size,
update the matching entry in `src/data.ts` → `SHEETS`.
