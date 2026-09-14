import * as Phaser from 'phaser';
import { sdk } from '@smoud/playable-sdk';
import {
  ART_SCALE,
  BOSS_AT,
  ENEMIES,
  EnemyDef,
  GEMS,
  IMAGES,
  SOUNDS,
  MINIBOSS_AT,
  PLAYER,
  MIN_ON_SCREEN,
  RUN_LIMIT,
  SKILLS,
  SHEETS,
  SPINE,
  SKILL_BY_ID,
  SkillDef,
  WAVES,
  XP_RATE,
  xpForLevel
} from './data';
import { Hud } from './Hud';

const DEPTH = { bg: 0, pickup: 5, enemy: 10, player: 20, proj: 30, fx: 40 };

/** The Phaser Spine plugin ships no types; this is the slice of SpineGameObject used here. */
interface SpineObject extends Phaser.GameObjects.GameObject {
  x: number;
  y: number;
  rotation: number;
  scaleY: number;
  skeleton: any;
  setDepth(v: number): SpineObject;
  setScale(x: number, y?: number): SpineObject;
  setSkinByName(name: string): SpineObject;
  setSlotsToSetupPose(): SpineObject;
  setMix(from: string, to: string, duration: number): SpineObject;
  play(name: string, loop?: boolean, ignoreIfPlaying?: boolean): SpineObject;
}

/** The real game answers a horizontal direction switch with the short `flip1` roll
 *  (PlayerMovement.CheckRotation); the plane is mirrored on the spot, never inverted. */
const FLIP = { anim: 'flip1', duration: 0.167, mix: 0.12 };
/** Neither Spine renderer reads Phaser's flipX/flipY flags - a SpineGameObject only
 *  mirrors on a negative scale, so facing left is a negative scaleY. */
const PLANE_SCALE = SPINE.scale * ART_SCALE;

interface Enemy {
  id: number;
  spr: Phaser.GameObjects.Sprite;
  def: EnemyDef;
  hp: number;
  maxHp: number;
  flash: number;
  knockX: number;
  knockY: number;
}

interface Proj {
  spr: Phaser.GameObjects.Image;
  vx: number;
  vy: number;
  dmg: number;
  life: number;
  pierce: number;
  kind: 'straight' | 'boomerang' | 'bounce' | 'orbit';
  spin: number;
  /** orbit params */
  orbitAngle?: number;
  orbitRadius?: number;
  orbitSpeed?: number;
  /** boomerang params */
  t?: number;
  /** per-enemy re-hit gate for multi-hit weapons */
  hits?: Record<number, number>;
}

interface Pickup {
  spr: Phaser.GameObjects.Image;
  xp: number;
  heal: number;
  vx: number;
  vy: number;
  drag: number;
  pulled: boolean;
}

/** One owned skill: level + accumulated cooldown timer. */
interface Owned {
  def: SkillDef;
  level: number;
  cd: number;
}

export class GameScene extends Phaser.Scene {
  // world
  private player!: SpineObject;
  private sky!: Phaser.GameObjects.Image;
  private cloudsFar!: Phaser.GameObjects.TileSprite;
  private cloudsNear!: Phaser.GameObjects.TileSprite;

  private enemies: Enemy[] = [];
  private projs: Proj[] = [];
  private pickups: Pickup[] = [];
  private enemyId = 0;

  // input
  private joyBase!: Phaser.GameObjects.Arc;
  private joyKnob!: Phaser.GameObjects.Arc;
  private joyPointer: number | null = null;
  private joyOrigin = new Phaser.Math.Vector2();
  private move = new Phaser.Math.Vector2();
  private vel = new Phaser.Math.Vector2();
  private faceLeft = false;
  private flipT = 0;

  // run state
  public state: 'intro' | 'play' | 'levelup' | 'over' = 'intro';
  public elapsed = 0;
  public kills = 0;
  public wave = 1;
  public level = 1;
  public xp = 0;
  public xpNeed = xpForLevel(1);
  public hp = PLAYER.health;
  public maxHp = PLAYER.health;

  private owned = new Map<string, Owned>();
  private spawnCd = 0;
  private miniBossSpawned = false;
  private bossSpawned = false;
  private boss: Enemy | null = null;
  private bossDefeated = false;
  private hurtCd = 0;
  /** Per-sound retrigger gate, keyed like SOUNDS; see `sfx`. */
  private sfxNext: Record<string, number> = {};
  private regen = 0;

  private hud!: Hud;

  constructor() {
    super({ key: 'GameScene' });
  }

  // ---------------------------------------------------------------- preload
  preload() {
    for (const key in IMAGES) this.load.image(key, IMAGES[key]);
    this.loadSounds();
    for (const key in SHEETS) {
      const sheet = SHEETS[key];
      this.load.spritesheet(key, sheet.url, {
        frameWidth: sheet.frameWidth,
        frameHeight: sheet.frameHeight
      });
    }
    this.loadPlayerSpine();
  }

  /** Decode the SFX straight into the audio cache instead of going through `load.audio`.
   *
   *  Phaser answers a data URL with a fake XHR carrying only `responseText` - a binary
   *  string from atob, never an ArrayBuffer (Loader/XHRLoader.js) - so `load.audio` hands
   *  decodeAudioData a string and it throws. Every asset here is inlined as a data URL,
   *  so that path is the only path. Decoding is fire-and-forget: `sfx` checks the cache,
   *  which also covers a device that gives us no Web Audio context at all. */
  private loadSounds() {
    const ctx = (this.sound as Phaser.Sound.WebAudioSoundManager).context;
    if (!ctx) return;
    for (const key in SOUNDS) {
      const bin = atob(SOUNDS[key].url.split(',')[1]);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      // callback form, not the promise: Safari only grew the promise overload in 14.1
      ctx.decodeAudioData(
        bytes.buffer,
        (audio) => this.cache.audio.add(key, audio),
        () => undefined
      );
    }
  }

  /** Register the player skeleton without going through `load.spine`.
   *
   *  Every asset in a playable is inlined as a data URL, and the Spine plugin bundles a
   *  copy of Phaser's loader that predates data-URL support - `load.spine` stalls the
   *  whole queue on the atlas page and the scene never reaches create(). The plugin only
   *  reads three things back out of the caches, so they go in directly; the page image
   *  goes through Phaser's own loader, which handles data URLs fine. */
  private loadPlayerSpine() {
    this.load.image(`${SPINE.key}:${SPINE.page}`, SPINE.png);
    this.cache.json.add(SPINE.key, JSON.parse(SPINE.json));
    (this.cache as any).custom.spine.add(SPINE.key, {
      preMultipliedAlpha: false,
      data: atob(SPINE.atlas.slice(SPINE.atlas.indexOf(',') + 1)),
      prefix: ''
    });
  }

  /** One plane skeleton, skinned and scaled to the size the old baked strip drew at. */
  private makeSkeleton(): SpineObject {
    const o = (this.add as any).spine(0, 0, SPINE.key, 'flying1', true) as SpineObject;
    o.setSkinByName(SPINE.skin).setSlotsToSetupPose();
    return o.setDepth(DEPTH.player).setScale(PLANE_SCALE);
  }

  /** One looping animation per baked strip, played at the skeleton's own rate.
   *  Frame count comes from the decoded texture, not the table, so a stale entry
   *  degrades the loop instead of throwing on a missing frame. */
  private createAnims() {
    for (const key in SHEETS) {
      const sheet = SHEETS[key];
      if (this.anims.exists(key)) continue;
      // Phaser adds a __BASE frame to every texture alongside the real ones
      const total = this.textures.get(key).frameTotal - 1;
      if (total !== sheet.frames && __DEV__) {
        console.warn(`${key}: sheet table says ${sheet.frames} frames, texture has ${total}`);
      }
      this.anims.create({
        key,
        frames: this.anims.generateFrameNumbers(key, { start: 0, end: Math.max(0, total - 1) }),
        frameRate: sheet.fps,
        // characters loop their idle; the hit spark and death burst are one-shots
        repeat: key.startsWith('e_') ? -1 : 0
      });
    }
  }

  // ----------------------------------------------------------------- create
  create() {
    const cam = this.cameras.main;

    this.sky = this.add.image(0, 0, 'sky').setOrigin(0.5).setScrollFactor(0).setDepth(DEPTH.bg);
    this.cloudsFar = this.add
      .tileSprite(0, 0, 10, 10, 'clouds1')
      .setOrigin(0.5)
      .setScrollFactor(0)
      .setAlpha(0.3)
      .setTileScale(0.45)
      .setDepth(DEPTH.bg + 1);
    this.cloudsNear = this.add
      .tileSprite(0, 0, 10, 10, 'clouds2')
      .setOrigin(0.5)
      .setScrollFactor(0)
      .setAlpha(0.5)
      .setTileScale(0.7)
      .setDepth(DEPTH.bg + 2);

    this.createAnims();
    // Spine's canvas renderer drops every mesh attachment unless triangle rendering is
    // switched on - on a device with no WebGL the plane would otherwise fly as a head and
    // a propeller. The WebGL renderer has no such flag and ignores this.
    const spineRenderer = (this as any).spine?.skeletonRenderer;
    if (spineRenderer && 'triangleRendering' in spineRenderer) spineRenderer.triangleRendering = true;

    this.player = this.makeSkeleton();
    this.player.setMix('flying1', FLIP.anim, FLIP.mix).setMix(FLIP.anim, 'flying1', FLIP.mix);
    this.player.play('flying1', true);
    cam.startFollow(this.player, false, 0.12, 0.12);
    cam.setBackgroundColor('#57bdf9');

    // virtual joystick — appears wherever the finger lands
    this.joyBase = this.add.circle(0, 0, 50, 0xffffff, 0.16).setScrollFactor(0).setDepth(90).setVisible(false);
    this.joyBase.setStrokeStyle(4, 0xffffff, 0.5);
    this.joyKnob = this.add.circle(0, 0, 22, 0xffffff, 0.55).setScrollFactor(0).setDepth(91).setVisible(false);

    this.input.addPointer(2);
    this.input.on('pointerdown', this.onDown, this);
    this.input.on('pointermove', this.onMove, this);
    this.input.on('pointerup', this.onUp, this);

    this.addSkill('multicanon');

    this.hud = new Hud(this);
    this.hud.showIntro();

    // Handle used by the headless QA harness to read run state; harmless in production.
    (window as any).__scene = this;
    this.resize(cam.width, cam.height);
    sdk.start();
  }

  // ------------------------------------------------------------------ input
  private onDown(p: Phaser.Input.Pointer) {
    if (this.state === 'intro') this.begin();
    if (this.state !== 'play' || this.joyPointer !== null) return;
    this.joyPointer = p.id;
    this.joyOrigin.set(p.x, p.y);
    this.joyBase.setPosition(p.x, p.y).setVisible(true);
    this.joyKnob.setPosition(p.x, p.y).setVisible(true);
  }

  private onMove(p: Phaser.Input.Pointer) {
    if (p.id !== this.joyPointer) return;
    const d = new Phaser.Math.Vector2(p.x - this.joyOrigin.x, p.y - this.joyOrigin.y);
    const len = Math.min(d.length(), 50);
    if (d.length() > 0) d.normalize();
    this.move.copy(d).scale(Math.min(len / 38, 1));
    this.joyKnob.setPosition(this.joyOrigin.x + d.x * len, this.joyOrigin.y + d.y * len);
  }

  private onUp(p: Phaser.Input.Pointer) {
    if (p.id !== this.joyPointer) return;
    this.joyPointer = null;
    this.move.set(0, 0);
    this.joyBase.setVisible(false);
    this.joyKnob.setVisible(false);
  }

  private begin() {
    this.state = 'play';
    this.hud.hideIntro();
  }

  // ------------------------------------------------------------------ stats
  /** Stacking multiplier for a passive: (1 + step)^level, matching the in-game +X% per level. */
  private lvlOf(id: string) {
    return this.owned.get(id)?.level ?? 0;
  }

  private get atkMul() {
    return Math.pow(1.1, this.lvlOf('attack'));
  }
  private get speedMul() {
    return Math.pow(1.1, this.lvlOf('speed'));
  }
  private get armorMul() {
    return Math.pow(0.9, this.lvlOf('armor'));
  }
  private get magnetRadius() {
    return PLAYER.pickupRadius * (1 + this.lvlOf('magnet'));
  }
  private get xpMul() {
    return Math.pow(1.08, this.lvlOf('xp'));
  }
  private get cdMul() {
    return Math.pow(0.92, this.lvlOf('cooldown'));
  }
  private get projSpeedMul() {
    return Math.pow(1.1, this.lvlOf('bulletspeed'));
  }

  public addSkill(id: string) {
    const cur = this.owned.get(id);
    if (cur) {
      cur.level = Math.min(cur.level + 1, cur.def.max);
    } else {
      const def = SKILL_BY_ID.get(id)!;
      this.owned.set(id, { def, level: 1, cd: 0 });
    }
    if (id === 'health') {
      const before = this.maxHp;
      this.maxHp = PLAYER.health * Math.pow(1.2, this.lvlOf('health'));
      this.hp += this.maxHp - before;
    }
    if (id === 'shield' || id === 'propeller') this.buildOrbit(id);
  }

  /** Boss bar feed for the HUD. */
  public bossState() {
    return this.boss ? { ratio: this.boss.hp / this.boss.maxHp } : null;
  }

  public ownedList() {
    return [...this.owned.values()];
  }

  /** Three cards, at least one of them an active weapon while the loadout is thin. */
  public rollChoices(): { def: SkillDef; level: number }[] {
    const pool = SKILLS.filter((s) => (this.owned.get(s.id)?.level ?? 0) < s.max);
    const weapons = pool.filter((s) => s.kind === 'weapon');
    const out: SkillDef[] = [];
    const activeCount = [...this.owned.values()].filter((o) => o.def.kind === 'weapon').length;
    if (activeCount < 4 && weapons.length) out.push(Phaser.Utils.Array.GetRandom(weapons));
    const rest = Phaser.Utils.Array.Shuffle(pool.filter((s) => !out.includes(s)));
    while (out.length < 3 && rest.length) out.push(rest.pop()!);
    return out.map((def) => ({ def, level: (this.owned.get(def.id)?.level ?? 0) + 1 }));
  }

  // ------------------------------------------------------------------ update
  update(_time: number, deltaMs: number) {
    const dt = Math.min(deltaMs, 50) / 1000;
    this.drawBackground();
    if (this.state !== 'play') {
      this.hud.update(dt);
      return;
    }

    this.elapsed += dt;
    this.updatePlayer(dt);
    this.updateSpawner(dt);
    this.updateEnemies(dt);
    this.updateWeapons(dt);
    this.updateProjectiles(dt);
    this.updatePickups(dt);
    this.hud.update(dt);

    if (this.bossDefeated) this.finishRun(true);
    if (this.elapsed > RUN_LIMIT) this.finishRun(true);
  }

  private drawBackground() {
    const cam = this.cameras.main;
    this.sky.setPosition(cam.width / 2, cam.height / 2).setDisplaySize(cam.width, cam.height);
    for (const [layer, f] of [
      [this.cloudsFar, 0.12],
      [this.cloudsNear, 0.3]
    ] as [Phaser.GameObjects.TileSprite, number][]) {
      layer.setPosition(cam.width / 2, cam.height / 2).setSize(cam.width, cam.height);
      layer.tilePositionX = cam.scrollX * f;
      layer.tilePositionY = cam.scrollY * f;
    }
  }

  private updatePlayer(dt: number) {
    const target = this.move.clone().scale(PLAYER.speed * this.speedMul);
    this.vel.lerp(target, Math.min(1, PLAYER.accel * dt));
    this.player.x += this.vel.x * dt;
    this.player.y += this.vel.y * dt;

    // A horizontal input sign change starts the roll, at whatever speed the plane is at.
    const dir = Math.sign(this.move.x);
    if (dir !== 0 && dir < 0 !== this.faceLeft) {
      this.faceLeft = dir < 0;
      this.flipT = FLIP.duration;
      this.player.play(FLIP.anim, false);
    }
    if (this.vel.lengthSq() > 400) this.player.rotation = Math.atan2(this.vel.y, this.vel.x);
    // Mirroring follows the nose, so the plane reads right side up in either direction.
    this.player.scaleY = Math.abs(this.player.rotation) > Math.PI / 2 ? -PLANE_SCALE : PLANE_SCALE;
    if (this.flipT > 0 && (this.flipT -= dt) <= 0) this.player.play('flying1', true);
    this.player.y += Math.sin(this.elapsed * 3) * 0.25;

    this.hurtCd = Math.max(0, this.hurtCd - dt);
    const regenLvl = this.lvlOf('health');
    if (regenLvl) {
      this.regen += dt;
      if (this.regen >= 1) {
        this.regen = 0;
        this.hp = Math.min(this.maxHp, this.hp + regenLvl * 0.4);
      }
    }
  }

  // ---------------------------------------------------------------- spawning
  private updateSpawner(dt: number) {
    const wave = WAVES.find((w) => this.elapsed >= w.start && this.elapsed < w.end) ?? WAVES[WAVES.length - 1];
    this.wave = WAVES.indexOf(wave) + 1;

    if (!this.miniBossSpawned && this.elapsed >= MINIBOSS_AT) {
      this.miniBossSpawned = true;
      this.spawn('hammerhead');
      this.hud.banner('MINI BOSS INCOMING');
    }
    if (!this.bossSpawned && this.elapsed >= BOSS_AT) {
      this.bossSpawned = true;
      this.boss = this.spawn('boss');
      this.hud.banner('BOSS INCOMING');
    }

    this.spawnCd -= dt;
    if (this.enemies.length >= wave.cap) return;
    // top the arena straight back up when the loadout has cleared it out
    const starved = this.enemies.length < MIN_ON_SCREEN;
    if (this.spawnCd > 0 && !starved) return;
    this.spawnCd = wave.interval;
    const burst = starved ? wave.burst + 2 : wave.burst;
    for (let i = 0; i < burst; i++) {
      this.spawn(Phaser.Utils.Array.GetRandom(wave.pool), (i / burst) * Math.PI * 2);
    }
  }

  private spawn(type: string, spread = 0): Enemy {
    const def = ENEMIES[type];
    const cam = this.cameras.main;
    const dist = Math.hypot(cam.width, cam.height) / 2 + 30;
    const heading = this.vel.lengthSq() > 900 ? Math.atan2(this.vel.y, this.vel.x) : Math.random() * Math.PI * 2;
    const a = Math.random() < 0.8 ? heading + Phaser.Math.FloatBetween(-1.1, 1.1) : Math.random() * Math.PI * 2;
    const spr = this.add
      .sprite(this.player.x + Math.cos(a) * dist, this.player.y + Math.sin(a) * dist, def.key)
      .setDepth(DEPTH.enemy)
      .setScale(def.scale);
    // stagger the loop so a wave doesn't flap in lockstep
    spr.play(def.key);
    spr.anims.setProgress(Math.random());
    // difficulty ramps with elapsed time the way the stage timer does in-game
    const ramp = 1 + this.elapsed / 70;
    const e: Enemy = {
      id: ++this.enemyId,
      spr,
      def,
      hp: def.hp * ramp,
      maxHp: def.hp * ramp,
      flash: 0,
      knockX: 0,
      knockY: 0
    };
    this.enemies.push(e);
    return e;
  }

  private updateEnemies(dt: number) {
    const px = this.player.x;
    const py = this.player.y;
    this.separate();
    for (let i = this.enemies.length - 1; i >= 0; i--) {
      const e = this.enemies[i];
      const dx = px - e.spr.x;
      const dy = py - e.spr.y;
      const d = Math.hypot(dx, dy) || 1;

      e.knockX *= 0.86;
      e.knockY *= 0.86;
      e.spr.x += (dx / d) * e.def.speed * dt + e.knockX * dt;
      e.spr.y += (dy / d) * e.def.speed * dt + e.knockY * dt;
      e.spr.setFlipX(dx < 0);
      e.spr.setRotation(Phaser.Math.Clamp(dy / d, -0.5, 0.5) * (dx < 0 ? -0.35 : 0.35));

      if (e.flash > 0) {
        e.flash -= dt;
        if (e.flash <= 0) e.spr.clearTint();
      }

      if (d < e.def.radius + PLAYER.radius && this.hurtCd <= 0) {
        this.damagePlayer(e.def.damage);
        e.knockX = (-dx / d) * 150;
        e.knockY = (-dy / d) * 150;
      }
    }
  }

  /** Nudge overlapping enemies apart so a wave reads as a swarm, not one sprite.
   *  ponytail: O(n^2) over the live list; fine at the ~35 enemy cap, needs a grid above that. */
  private separate() {
    const list = this.enemies;
    for (let i = 0; i < list.length; i++) {
      const a = list[i];
      for (let j = i + 1; j < list.length; j++) {
        const b = list[j];
        const dx = b.spr.x - a.spr.x;
        const dy = b.spr.y - a.spr.y;
        const min = (a.def.radius + b.def.radius) * 1.05;
        const d2 = dx * dx + dy * dy;
        if (d2 > min * min || d2 < 0.01) continue;
        const d = Math.sqrt(d2);
        const push = ((min - d) / d) * 0.6;
        if (!a.def.boss) {
          a.spr.x -= dx * push;
          a.spr.y -= dy * push;
        }
        if (!b.def.boss) {
          b.spr.x += dx * push;
          b.spr.y += dy * push;
        }
      }
    }
  }

  /** One-shot SFX at the volume the Unity call site used, throttled by its own `gap`.
   *  The ad network's mute state arrives as sdk volume -> Game.volume, so nothing here
   *  needs to know about it. */
  public sfx(key: string, volume = SOUNDS[key].volume) {
    if (!this.cache.audio.exists(key)) return;
    if (this.time.now < (this.sfxNext[key] ?? 0)) return;
    this.sfxNext[key] = this.time.now + SOUNDS[key].gap * 1000;
    this.sound.play(key, { volume });
  }

  private damagePlayer(amount: number) {
    this.sfx('hurt');
    this.hurtCd = PLAYER.hurtCooldown;
    this.hp -= amount * this.armorMul;
    this.cameras.main.shake(120, 0.006);
    this.player.skeleton.color.set(1, 0.35, 0.3, 1);
    this.time.delayedCall(90, () => this.player.skeleton.color.set(1, 1, 1, 1));
    if (this.hp <= 0) {
      this.hp = 0;
      this.finishRun(false);
    }
  }

  private hurtEnemy(e: Enemy, dmg: number, fromX: number, fromY: number) {
    e.hp -= dmg;
    e.flash = 0.08;
    this.sfx('hit');
    e.spr.setTintFill(0xffffff);
    const dx = e.spr.x - fromX;
    const dy = e.spr.y - fromY;
    const d = Math.hypot(dx, dy) || 1;
    // Unity spawns PlayerBulletSplash at the bullet, rotated the way it was travelling.
    const spark = this.add.sprite(fromX, fromY, 'hit').setDepth(DEPTH.fx).setRotation(Math.atan2(dy, dx));
    spark.play('hit').once('animationcomplete', () => spark.destroy());
    if (!e.def.boss) {
      e.knockX += (dx / d) * 70;
      e.knockY += (dy / d) * 70;
    }
    if (e.hp <= 0) this.killEnemy(e);
  }

  private killEnemy(e: Enemy) {
    const idx = this.enemies.indexOf(e);
    if (idx < 0) return;
    this.enemies.splice(idx, 1);
    this.kills++;
    this.sfx('boom');

    const gem = GEMS[e.def.gem];
    this.dropPickup(e.spr.x, e.spr.y, gem.key, gem.xp, 0, gem.scale);
    if (Math.random() < 0.04) this.dropPickup(e.spr.x, e.spr.y, 'meat', 0, 18, 0.8);
    if (e.def.boss) {
      for (let i = 0; i < 12; i++) {
        const g = GEMS[2];
        this.dropPickup(e.spr.x, e.spr.y, g.key, g.xp, 0, 1);
      }
      this.cameras.main.shake(400, 0.02);
    }

    // Unity despawns the plane and plays one `explosion` skeleton over it, at a random
    // roll and size (Enemy.SpawnExplosions -> Explosions.GenerateParticlesAt).
    const boom = this.add
      .sprite(e.spr.x, e.spr.y, 'boom')
      .setDepth(DEPTH.fx)
      .setRotation(Math.random() * Math.PI * 2)
      .setScale((e.def.radius / 18) * Phaser.Math.FloatBetween(0.9, 1.2));
    boom.play('boom').once('animationcomplete', () => boom.destroy());

    const spr = e.spr;
    spr.setTintFill(0xffffff);
    this.tweens.add({
      targets: spr,
      scale: spr.scale * 1.25,
      alpha: 0,
      duration: 150,
      onComplete: () => spr.destroy()
    });
    if (e === this.boss) {
      this.bossDefeated = true;
      this.boss = null;
    }
  }

  private dropPickup(x: number, y: number, key: string, xp: number, heal: number, scale: number) {
    const a = Math.random() * Math.PI * 2;
    const spr = this.add
      .image(x, y, key)
      .setDepth(DEPTH.pickup)
      .setScale(scale * 0.7);
    this.pickups.push({
      spr,
      xp,
      heal,
      vx: Math.cos(a) * 55,
      vy: Math.sin(a) * 55,
      drag: 6,
      pulled: false
    });
  }

  private updatePickups(dt: number) {
    const r = this.magnetRadius;
    for (let i = this.pickups.length - 1; i >= 0; i--) {
      const p = this.pickups[i];
      const dx = this.player.x - p.spr.x;
      const dy = this.player.y - p.spr.y;
      const d = Math.hypot(dx, dy) || 1;

      if (p.pulled || d < r) {
        p.pulled = true;
        const pull = 760;
        p.vx += (dx / d) * pull * dt;
        p.vy += (dy / d) * pull * dt;
        p.drag = 1.2;
      }
      p.vx -= p.vx * p.drag * dt;
      p.vy -= p.vy * p.drag * dt;
      p.spr.x += p.vx * dt;
      p.spr.y += p.vy * dt;

      if (d < 22) {
        if (p.xp) this.addXp(p.xp);
        if (p.heal) this.hp = Math.min(this.maxHp, this.hp + p.heal);
        p.spr.destroy();
        this.pickups.splice(i, 1);
      }
    }
  }

  private addXp(amount: number) {
    this.xp += amount * this.xpMul * XP_RATE;
    while (this.xp >= this.xpNeed) {
      this.xp -= this.xpNeed;
      this.level++;
      this.xpNeed = xpForLevel(this.level);
      this.levelUp();
    }
  }

  private levelUp() {
    if (this.state === 'over') return;
    this.state = 'levelup';
    this.move.set(0, 0);
    this.vel.set(0, 0);
    this.joyPointer = null;
    this.joyBase.setVisible(false);
    this.joyKnob.setVisible(false);
    this.hud.openLevelUp();
  }

  public closeLevelUp(id: string) {
    this.addSkill(id);
    this.state = this.hp > 0 ? 'play' : 'over';
  }

  // ---------------------------------------------------------------- weapons
  private nearestEnemy(maxDist = 1e9): Enemy | null {
    let best: Enemy | null = null;
    let bestD = maxDist * maxDist;
    for (const e of this.enemies) {
      const d = Phaser.Math.Distance.Squared(e.spr.x, e.spr.y, this.player.x, this.player.y);
      if (d < bestD) {
        bestD = d;
        best = e;
      }
    }
    return best;
  }

  private updateWeapons(dt: number) {
    for (const o of this.owned.values()) {
      if (o.def.kind !== 'weapon') continue;
      if (o.def.id === 'shield' || o.def.id === 'propeller') continue; // persistent orbits
      o.cd -= dt;
      if (o.cd > 0) continue;
      o.cd = this.fire(o) * this.cdMul;
    }
  }

  /** Fires one volley of the given weapon and returns its cooldown in seconds. */
  private fire(o: Owned): number {
    const lvl = o.level;
    const atk = PLAYER.attack * this.atkMul;
    const sp = this.projSpeedMul;
    const target = this.nearestEnemy(700);
    const aim = target
      ? Math.atan2(target.spr.y - this.player.y, target.spr.x - this.player.x)
      : this.player.rotation * (this.player.scaleY < 0 ? -1 : 1);

    switch (o.def.id) {
      case 'multicanon': {
        const n = 1 + Math.floor((lvl + 1) / 2);
        for (let i = 0; i < n; i++) {
          const a = aim + (i - (n - 1) / 2) * 0.16;
          this.shoot('bullet', a, 560 * sp, atk * (1.8 + lvl * 1.1), 1.2, 1, 0.85);
        }
        return 0.34 - lvl * 0.02;
      }
      case 'warmachine': {
        for (const off of [-12, 12]) {
          const a = aim + Phaser.Math.FloatBetween(-0.07, 0.07);
          const p = this.shoot('bullet_long', a, 720 * sp, atk * (1.1 + lvl * 0.6), 1.1, 1, 0.8);
          p.spr.x += Math.cos(aim + Math.PI / 2) * off * 0.6;
          p.spr.y += Math.sin(aim + Math.PI / 2) * off * 0.6;
        }
        return 0.14 - lvl * 0.012;
      }
      case 'razorfin': {
        const n = 1 + Math.floor((lvl - 1) / 2);
        for (let i = 0; i < n; i++) {
          const a = aim + (i - (n - 1) / 2) * 0.3;
          this.shoot('w_fish', a, 480 * sp, atk * (2.6 + lvl * 1.4), 1.6, 3 + lvl * 2, 0.8, 10);
        }
        return 0.85 - lvl * 0.07;
      }
      case 'croissant': {
        const n = 1 + Math.floor(lvl / 2);
        for (let i = 0; i < n; i++) {
          const a = aim + (i / n) * Math.PI * 2;
          const p = this.shoot('w_croissant', a, 360 * sp, atk * (2.2 + lvl * 1.1), 1.9, 999, 0.8, 9);
          p.kind = 'boomerang';
          p.t = 0;
          p.hits = {};
        }
        return 1.25 - lvl * 0.1;
      }
      case 'yarnball': {
        const n = 1 + Math.floor(lvl / 2);
        for (let i = 0; i < n; i++) {
          const a = Math.random() * Math.PI * 2;
          const p = this.shoot('w_yarnball', a, 300 * sp, atk * (2.4 + lvl * 1.2), 5, 999, 0.75, 6);
          p.kind = 'bounce';
          p.hits = {};
        }
        return 1.9 - lvl * 0.15;
      }
      case 'lightning': {
        const strikes = 1 + lvl;
        const dmg = atk * (4 + lvl * 2.2);
        for (let i = 0; i < strikes; i++) {
          this.time.delayedCall(i * 110, () => {
            if (this.state === 'over') return;
            const pick = Phaser.Utils.Array.GetRandom(
              this.enemies.filter((e) => Phaser.Math.Distance.Between(e.spr.x, e.spr.y, this.player.x, this.player.y) < 420)
            ) as Enemy | undefined;
            if (!pick) return;
            this.strike(pick.spr.x, pick.spr.y, dmg, 46 + lvl * 6);
          });
        }
        return 2.4 - lvl * 0.18;
      }
    }
    return 1;
  }

  private shoot(
    key: string,
    angle: number,
    speed: number,
    dmg: number,
    life: number,
    pierce: number,
    scale: number,
    spin = 0
  ): Proj {
    const spr = this.add.image(this.player.x, this.player.y, key).setDepth(DEPTH.proj).setScale(scale).setRotation(angle);
    const p: Proj = {
      spr,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      dmg,
      life,
      pierce,
      kind: 'straight',
      spin
    };
    this.projs.push(p);
    return p;
  }

  /** Shockwave Strike: instant AoE flash. */
  private strike(x: number, y: number, dmg: number, radius: number) {
    const ring = this.add.circle(x, y, radius, 0x9adcff, 0.55).setDepth(DEPTH.fx);
    ring.setStrokeStyle(6, 0xffffff, 0.9);
    this.tweens.add({
      targets: ring,
      scale: 1.5,
      alpha: 0,
      duration: 240,
      onComplete: () => ring.destroy()
    });
    for (const e of [...this.enemies]) {
      if (Phaser.Math.Distance.Between(e.spr.x, e.spr.y, x, y) < radius + e.def.radius) {
        this.hurtEnemy(e, dmg, x, y);
      }
    }
  }

  /** (Re)build the orbiting weapons so their count/radius match the current level. */
  private buildOrbit(id: string) {
    for (let i = this.projs.length - 1; i >= 0; i--) {
      const p = this.projs[i];
      if (p.kind === 'orbit' && p.spr.texture.key === (id === 'shield' ? 'w_shield' : 'w_propeller')) {
        p.spr.destroy();
        this.projs.splice(i, 1);
      }
    }
    const lvl = this.lvlOf(id);
    if (!lvl) return;
    const count = id === 'shield' ? 1 : 1 + lvl;
    for (let i = 0; i < count; i++) {
      const spr = this.add
        .image(this.player.x, this.player.y, id === 'shield' ? 'w_shield' : 'w_propeller')
        .setDepth(DEPTH.proj - 1)
        .setScale(id === 'shield' ? 0.55 + lvl * 0.1 : 0.75);
      if (id === 'shield') spr.setAlpha(0.85);
      this.projs.push({
        spr,
        vx: 0,
        vy: 0,
        dmg: 0,
        life: 1e9,
        pierce: 999,
        kind: 'orbit',
        spin: id === 'shield' ? 1.4 : 14,
        orbitAngle: (i / count) * Math.PI * 2,
        orbitRadius: id === 'shield' ? 0 : 58 + lvl * 4,
        orbitSpeed: id === 'shield' ? 0 : 3.1,
        hits: {}
      });
    }
  }

  private updateProjectiles(dt: number) {
    const atk = PLAYER.attack * this.atkMul;
    const now = this.elapsed;

    for (let i = this.projs.length - 1; i >= 0; i--) {
      const p = this.projs[i];

      if (p.kind === 'orbit') {
        const isShield = p.spr.texture.key === 'w_shield';
        const lvl = this.lvlOf(isShield ? 'shield' : 'propeller');
        p.orbitAngle! += p.orbitSpeed! * dt;
        p.spr.x = this.player.x + Math.cos(p.orbitAngle!) * p.orbitRadius!;
        p.spr.y = this.player.y + Math.sin(p.orbitAngle!) * p.orbitRadius!;
        p.spr.rotation += p.spin * dt;
        p.dmg = atk * (isShield ? 1.2 + lvl * 0.8 : 2 + lvl * 1.2);
      } else {
        if (p.kind === 'boomerang') {
          // out-and-back arc, then it returns to the plane and expires
          p.t! += dt;
          const k = 1 - p.t! / p.life;
          p.spr.x += p.vx * k * dt;
          p.spr.y += p.vy * k * dt;
          const back = 1 - k;
          p.spr.x += (this.player.x - p.spr.x) * back * 2.4 * dt;
          p.spr.y += (this.player.y - p.spr.y) * back * 2.4 * dt;
        } else {
          p.spr.x += p.vx * dt;
          p.spr.y += p.vy * dt;
        }
        if (p.spin) p.spr.rotation += p.spin * dt;
        p.life -= dt;
        if (p.life <= 0) {
          p.spr.destroy();
          this.projs.splice(i, 1);
          continue;
        }
      }

      // hit test
      for (const e of [...this.enemies]) {
        const hitR = e.def.radius + 10;
        if (Phaser.Math.Distance.Squared(e.spr.x, e.spr.y, p.spr.x, p.spr.y) > hitR * hitR) continue;
        if (p.hits) {
          if ((p.hits[e.id] ?? 0) > now) continue;
          p.hits[e.id] = now + 0.3;
        }
        this.hurtEnemy(e, p.dmg, p.spr.x, p.spr.y);
        if (p.kind === 'bounce') {
          const a = Math.atan2(p.spr.y - e.spr.y, p.spr.x - e.spr.x);
          const s = Math.hypot(p.vx, p.vy);
          p.vx = Math.cos(a) * s;
          p.vy = Math.sin(a) * s;
        }
        if (!p.hits) {
          p.pierce--;
          if (p.pierce <= 0) {
            p.spr.destroy();
            this.projs.splice(i, 1);
            break;
          }
        }
      }
    }
  }

  // ------------------------------------------------------------------- end
  private finishRun(won: boolean) {
    if (this.state === 'over') return;
    this.state = 'over';
    this.move.set(0, 0);
    this.joyBase.setVisible(false);
    this.joyKnob.setVisible(false);
    this.hud.showEnd(won);
    sdk.finish();
  }

  // ---------------------------------------------------------------- resize
  public resize(width: number, height: number) {
    this.cameras.resize(width, height);
    // The SDK resizes on its own schedule and can beat create() to the punch - loading
    // the player skeleton keeps the scene in preload noticeably longer than it used to.
    // create() ends by calling this again, so an early call has nothing to do here.
    if (!this.hud) return;
    this.drawBackground();
    this.hud.resize(width, height);
  }
}
