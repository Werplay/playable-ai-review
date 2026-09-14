// Game data lifted from the Explottens-FtP Unity project (Survival mode).
// Skill names / descriptions: Assets/Prefabs/Skills/**.prefab
// XP curve + gem values: Assets/Scripts/GameplayScripts/InGameXpHandler.cs, Prefabs/Collectibles/XpItem.prefab
// Base stats: Assets/Scripts/Player/PlayerStats.cs, Resources/CSV/SurvivorData/SurvivorLevelUpData.csv

import fontUrl from 'assets/LuckiestGuy-Regular.woff2';

import spinePng from 'assets/spine_player.png';
import spineAtlas from 'assets/spine_player.atlas';
import spineJson from 'assets/spine_player.json';
import eFurry from 'assets/e_furry.png';
import eFeline from 'assets/e_feline.png';
import eSpeedbug from 'assets/e_speedbug.png';
import eLadybug from 'assets/e_ladybug.png';
import eHelmetbee from 'assets/e_helmetbee.png';
import eBomberkitty from 'assets/e_bomberkitty.png';
import eRazorclaw from 'assets/e_razorclaw.png';
import eHammerhead from 'assets/e_hammerhead.png';
import eBoss from 'assets/e_boss.png';
import hit from 'assets/hit.png';
import boom from 'assets/boom.png';

import sky from 'assets/sky.png';
import clouds1 from 'assets/clouds1.png';
import clouds2 from 'assets/clouds2.png';
import appicon from 'assets/appicon.png';

import gemGreen from 'assets/gem_green.png';
import gemBlue from 'assets/gem_blue.png';
import gemGold from 'assets/gem_gold.png';
import meat from 'assets/meat.png';

import bullet from 'assets/bullet.png';
import bulletLong from 'assets/bullet_long.png';
import wCroissant from 'assets/w_croissant.png';
import wYarnball from 'assets/w_yarnball.png';
import wPropeller from 'assets/w_propeller.png';
import wFish from 'assets/w_fish.png';
import wShield from 'assets/w_shield.png';

import iMulticanon from 'assets/i_multicanon.png';
import iCroissant from 'assets/i_croissant.png';
import iLightning from 'assets/i_lightning.png';
import iShield from 'assets/i_shield.png';
import iPropeller from 'assets/i_propeller.png';
import iYarnball from 'assets/i_yarnball.png';
import iRazorfin from 'assets/i_razorfin.png';
import iWarmachine from 'assets/i_warmachine.png';
import iAttack from 'assets/i_attack.png';
import iSpeed from 'assets/i_speed.png';
import iHealth from 'assets/i_health.png';
import iArmor from 'assets/i_armor.png';
import iMagnet from 'assets/i_magnet.png';
import iXp from 'assets/i_xp.png';
import iCooldown from 'assets/i_cooldown.png';
import iBulletspeed from 'assets/i_bulletspeed.png';

import hudTime from 'assets/hud_time.png';
import hudKills from 'assets/hud_kills.png';
import hudWave from 'assets/hud_wave.png';

export const FONT = 'LuckiestGuy';
export const FONT_URL = fontUrl;

/** The player runs the real Spine skeleton (see tools/build_spine.py); everyone else is
 *  baked out of their skeletons as horizontal strips playing `idle`.
 *
 *  The atlas ships as a data URL whose page line still names the loose PNG, so the page
 *  name is swapped for the inlined image before the loader ever sees it. */
export const SPINE = {
  key: 'player_spine',
  png: spinePng,
  atlas: spineAtlas,
  json: spineJson,
  skin: 'playerPlane1',
  page: 'spine_player.png',
  /** Draws the flying loop 67px wide - the width the old baked strip used. */
  scale: 0.1039
};

/** Character art is baked out of the Spine skeletons as horizontal strips playing
 *  `idle`, each at its own skeleton's rate. */
export interface Sheet {
  url: string;
  frameWidth: number;
  frameHeight: number;
  frames: number;
  fps: number;
}

export const SHEETS: Record<string, Sheet> = {
  e_furry: { url: eFurry, frameWidth: 44, frameHeight: 50, frames: 40, fps: 30.0 },
  e_feline: { url: eFeline, frameWidth: 48, frameHeight: 51, frames: 40, fps: 30.0 },
  e_bomberkitty: { url: eBomberkitty, frameWidth: 52, frameHeight: 61, frames: 15, fps: 30.0 },
  e_razorclaw: { url: eRazorclaw, frameWidth: 54, frameHeight: 56, frames: 40, fps: 30.0 },
  e_hammerhead: { url: eHammerhead, frameWidth: 81, frameHeight: 77, frames: 40, fps: 30.0 },
  e_speedbug: { url: eSpeedbug, frameWidth: 34, frameHeight: 24, frames: 10, fps: 30.0 },
  e_helmetbee: { url: eHelmetbee, frameWidth: 34, frameHeight: 28, frames: 20, fps: 30.0 },
  e_ladybug: { url: eLadybug, frameWidth: 36, frameHeight: 38, frames: 30, fps: 30.0 },
  e_boss: { url: eBoss, frameWidth: 150, frameHeight: 174, frames: 16, fps: 30.0 },
  boom: { url: boom, frameWidth: 80, frameHeight: 65, frames: 16, fps: 30.0 },
  hit: { url: hit, frameWidth: 30, frameHeight: 47, frames: 4, fps: 30.0 }
};

export const IMAGES: Record<string, string> = {
  sky,
  clouds1,
  clouds2,
  appicon,
  gem_green: gemGreen,
  gem_blue: gemBlue,
  gem_gold: gemGold,
  meat,
  bullet,
  bullet_long: bulletLong,
  w_croissant: wCroissant,
  w_yarnball: wYarnball,
  w_propeller: wPropeller,
  w_fish: wFish,
  w_shield: wShield,
  i_multicanon: iMulticanon,
  i_croissant: iCroissant,
  i_lightning: iLightning,
  i_shield: iShield,
  i_propeller: iPropeller,
  i_yarnball: iYarnball,
  i_razorfin: iRazorfin,
  i_warmachine: iWarmachine,
  i_attack: iAttack,
  i_speed: iSpeed,
  i_health: iHealth,
  i_armor: iArmor,
  i_magnet: iMagnet,
  i_xp: iXp,
  i_cooldown: iCooldown,
  i_bulletspeed: iBulletspeed,
  hud_time: hudTime,
  hud_kills: hudKills,
  hud_wave: hudWave
};

// --- player ---------------------------------------------------------------
/** Strips are baked at exactly their on-screen size — the canvas is CSS-pixel sized,
 *  so anything larger is invisible — which makes one draw scale fit every character. */
export const ART_SCALE = 1;

export const PLAYER = {
  attack: 10, // PlayerStats.Default.Attack
  health: 140, // SurvivorLevelUpData BaseHP 100, padded for a ~90s ad run
  speed: 190, // px/s
  radius: 22,
  pickupRadius: 240,
  accel: 14, // how fast velocity chases the joystick vector
  hurtCooldown: 0.7 // i-frames after a collision
};

/** The real game paces a run over 10-20 minutes; this ad has ~95 seconds,
 *  so gem XP is scaled to keep the level-up cadence around 8-10 seconds. */
export const XP_RATE = 1.3;

/** InGameXpHandler.UpdateXpRequiredThisLevel */
export const xpForLevel = (level: number) => 40 * level * level + 80 * level - 20;

/** XpItem.prefab values: SmallGreen / BigGreen / Blue / Gold */
export const GEMS = [
  { key: 'gem_green', xp: 10, scale: 0.7 },
  { key: 'gem_green', xp: 40, scale: 0.95 },
  { key: 'gem_blue', xp: 100, scale: 0.95 },
  { key: 'gem_gold', xp: 2000, scale: 1.05 }
] as const;

// --- enemies --------------------------------------------------------------
export interface EnemyDef {
  key: string;
  hp: number;
  speed: number;
  damage: number;
  scale: number;
  radius: number;
  gem: number;
  boss?: boolean;
}

export const ENEMIES: Record<string, EnemyDef> = {
  furry: { key: 'e_furry', hp: 22, speed: 142, damage: 6, scale: ART_SCALE, radius: 18, gem: 0 },
  speedbug: { key: 'e_speedbug', hp: 14, speed: 178, damage: 5, scale: ART_SCALE, radius: 15, gem: 0 },
  ladybug: { key: 'e_ladybug', hp: 30, speed: 158, damage: 7, scale: ART_SCALE, radius: 16, gem: 1 },
  feline: { key: 'e_feline', hp: 46, speed: 148, damage: 9, scale: ART_SCALE, radius: 19, gem: 1 },
  helmetbee: { key: 'e_helmetbee', hp: 26, speed: 168, damage: 6, scale: ART_SCALE, radius: 15, gem: 0 },
  bomberkitty: { key: 'e_bomberkitty', hp: 78, speed: 132, damage: 12, scale: ART_SCALE, radius: 21, gem: 2 },
  razorclaw: { key: 'e_razorclaw', hp: 120, speed: 142, damage: 14, scale: ART_SCALE, radius: 21, gem: 2 },
  hammerhead: { key: 'e_hammerhead', hp: 420, speed: 128, damage: 18, scale: ART_SCALE, radius: 30, gem: 2, boss: true },
  boss: { key: 'e_boss', hp: 1600, speed: 152, damage: 24, scale: ART_SCALE, radius: 40, gem: 3, boss: true }
};

// --- waves (EnemyWaveData-style: start/end time, pool, spawn interval) -----
export interface Wave {
  start: number;
  end: number;
  pool: string[];
  interval: number;
  burst: number;
  cap: number;
}

export const WAVES: Wave[] = [
  { start: 0, end: 16, pool: ['furry', 'speedbug'], interval: 0.5, burst: 2, cap: 20 },
  { start: 16, end: 34, pool: ['furry', 'speedbug', 'ladybug'], interval: 0.42, burst: 2, cap: 30 },
  { start: 34, end: 52, pool: ['feline', 'helmetbee', 'ladybug'], interval: 0.36, burst: 3, cap: 40 },
  { start: 52, end: 72, pool: ['feline', 'bomberkitty', 'helmetbee'], interval: 0.3, burst: 3, cap: 50 },
  { start: 72, end: 92, pool: ['razorclaw', 'bomberkitty', 'speedbug'], interval: 0.26, burst: 4, cap: 60 }
];

export const MINIBOSS_AT = 44; // HammerHead joins mid-run
export const BOSS_AT = 78; // vaderboss closes the run
export const RUN_LIMIT = 110; // hard stop so the ad always reaches its end card

/** Keep at least this many in play; a strong loadout otherwise empties the sky. */
export const MIN_ON_SCREEN = 10;

// --- skills ---------------------------------------------------------------
export type SkillKind = 'weapon' | 'passive';

export interface SkillDef {
  id: string;
  title: string; // exact in-game title
  desc: string; // exact in-game description line
  icon: string;
  kind: SkillKind;
  max: number;
}

export const SKILLS: SkillDef[] = [
  // actives — Assets/Prefabs/Skills/Actives
  { id: 'multicanon', title: 'Multi Canon', desc: 'Damage Up, Radius Up', icon: 'i_multicanon', kind: 'weapon', max: 5 },
  { id: 'croissant', title: 'Croissant', desc: "That's one delicious attack", icon: 'i_croissant', kind: 'weapon', max: 5 },
  {
    id: 'lightning',
    title: 'Shockwave Strike',
    desc: "That's one flashy attack.",
    icon: 'i_lightning',
    kind: 'weapon',
    max: 5
  },
  {
    id: 'shield',
    title: 'Protective Shield',
    desc: 'Hold these pesky kitties back!',
    icon: 'i_shield',
    kind: 'weapon',
    max: 5
  },
  {
    id: 'propeller',
    title: 'Fiesty Propeller',
    desc: "Shouldn't these be attached to the plane?",
    icon: 'i_propeller',
    kind: 'weapon',
    max: 5
  },
  { id: 'yarnball', title: 'Yarnball', desc: 'Things are about to get fluffy', icon: 'i_yarnball', kind: 'weapon', max: 5 },
  { id: 'razorfin', title: 'Razor Fin', desc: 'One sharp fish!', icon: 'i_razorfin', kind: 'weapon', max: 5 },
  {
    id: 'warmachine',
    title: 'War Machine',
    desc: 'Nothing beats good old guns!',
    icon: 'i_warmachine',
    kind: 'weapon',
    max: 5
  },
  // passives — Assets/Prefabs/Skills/Passives
  { id: 'attack', title: 'Purrfect Claws', desc: 'ATK +10%', icon: 'i_attack', kind: 'passive', max: 5 },
  { id: 'speed', title: 'Paw Speeders', desc: 'Movement Speed +10%', icon: 'i_speed', kind: 'passive', max: 5 },
  { id: 'health', title: 'Nine Lives Doc', desc: 'Max HP +20%', icon: 'i_health', kind: 'passive', max: 5 },
  { id: 'armor', title: 'Furmidable Armor', desc: 'Recieved Damage -10%', icon: 'i_armor', kind: 'passive', max: 5 },
  { id: 'magnet', title: 'Catnip Magnet', desc: 'Item loot range +100%', icon: 'i_magnet', kind: 'passive', max: 5 },
  { id: 'xp', title: 'Meow Manual', desc: 'EXP gain +8%', icon: 'i_xp', kind: 'passive', max: 5 },
  { id: 'cooldown', title: 'Catnip Core', desc: 'All attack CD -8%', icon: 'i_cooldown', kind: 'passive', max: 5 },
  {
    id: 'bulletspeed',
    title: 'Cheese Chaser',
    desc: 'Bullet Flight Speed +10%',
    icon: 'i_bulletspeed',
    kind: 'passive',
    max: 5
  }
];

export const SKILL_BY_ID = new Map(SKILLS.map((s) => [s.id, s]));
