/**
 * Asserts assets/spine_player.* actually load in the Spine runtime Phaser ships.
 *
 * The source skeleton is a Spine 3.7 export and the plugin bundles 3.8.95, so this is
 * the check that build_spine.py's format conversion still holds. It runs the real
 * runtime - sliced straight out of the plugin bundle - rather than a reimplementation.
 *
 * Usage:  node tools/spine_check.js
 */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const ROOT = path.dirname(__dirname);
const A = path.join(ROOT, 'assets');
const DIST = path.join(ROOT, 'node_modules/phaser/plugins/spine/dist/SpinePlugin.js');

// The bundle needs a browser to boot; the spine namespace inside it does not, so lift
// just that webpack module out by its imports-loader/exports-loader markers.
const src = fs.readFileSync(DIST, 'utf8');
const start = src.indexOf('(function() {\nvar __extends');
const end = src.indexOf('}.call(window));', start);
assert.ok(start > 0 && end > start, 'could not locate the spine runtime inside SpinePlugin.js');
const modPath = path.join(require('os').tmpdir(), 'spine-runtime-slice.js');
fs.writeFileSync(modPath, src.slice(start, end + '}.call(window));'.length));

global.window = global;
global.document = { createElement: () => ({ style: {}, getContext: () => null }) };
global.navigator = { userAgent: 'node' };
const spine = require(modPath);

class HeadlessTexture extends spine.Texture {
  setFilters() {}
  setWraps() {}
  dispose() {}
}

const atlasText = fs.readFileSync(path.join(A, 'spine_player.atlas'), 'utf8');
const page = atlasText.match(/size:\s*(\d+),\s*(\d+)/);
const atlas = new spine.TextureAtlas(atlasText, () =>
  new HeadlessTexture({ width: +page[1], height: +page[2] })
);
const data = new spine.SkeletonJson(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(
  JSON.parse(fs.readFileSync(path.join(A, 'spine_player.json'), 'utf8'))
);

assert.ok(data.bones.length > 1, 'skeleton has no bones');
assert.ok(data.findSkin('playerPlane1'), 'playerPlane1 skin missing');

// Every animation GameScene plays must exist and pose without unresolved attachments.
const skeleton = new spine.Skeleton(data);
skeleton.setSkinByName('playerPlane1');
skeleton.setSlotsToSetupPose();
const state = new spine.AnimationState(new spine.AnimationStateData(data));

for (const name of ['flying1', 'idle1', 'flip1', 'dash1']) {
  const anim = data.findAnimation(name);
  assert.ok(anim, `animation ${name} missing`);
  assert.ok(anim.duration > 0, `animation ${name} has zero duration`);
  state.setAnimation(0, name, true);
  for (let i = 0; i < 8; i++) {
    state.update(anim.duration / 8);
    state.apply(skeleton);
    skeleton.updateWorldTransform();
    const offset = new spine.Vector2();
    const size = new spine.Vector2();
    skeleton.getBounds(offset, size, []);
    assert.ok(size.x > 0 && size.y > 0, `${name} posed to empty bounds at step ${i}`);
  }
}

console.log(
  `spine ok  ${data.bones.length} bones, ${data.slots.length} slots, ` +
    `${data.animations.map((a) => a.name).join('/')}`
);
