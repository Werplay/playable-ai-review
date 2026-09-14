import * as Phaser from 'phaser';
import { sdk } from '@smoud/playable-sdk';
import { FONT, SkillDef } from './data';
import type { GameScene } from './GameScene';

const D = { hud: 100, overlay: 200 };
const GOLD = '#ffd34d';

/** Colours read off the in-game "Select a Skill" panel. Weapons glow green, passives
 *  blue; the wedge is the same hue painted behind the icon inside the card. */
const CARD = {
  /** Reference size every card is drawn at - 4:1, the aspect the real panel uses. The
   *  layout scales the whole container to fit instead of redrawing it, so a resize or a
   *  mid-run rotation only moves and rescales what is already on screen. */
  w: 520,
  h: 130,
  gap: 14,
  fill: 0x333d5c,
  radius: 16,
  weapon: { glow: 0x6cf542, wedge: 0x4bbf27, title: '#ffffff' },
  passive: { glow: 0x9fe8ff, wedge: 0x2f7fd4, title: '#ffffff' },
  slot: 0x1b2036,
  pipOn: 0xffc93c,
  pipOff: 0x8c93a8
};

/** A container's scrollFactor drives rendering but input hit-testing reads each
 *  child's own value — so pin the whole subtree or taps land camera-scroll away. */
function pin(root: Phaser.GameObjects.GameObject) {
  const anyRoot = root as any;
  if (anyRoot.setScrollFactor) anyRoot.setScrollFactor(0);
  if (anyRoot.list) for (const child of anyRoot.list) pin(child);
}

/** Everything drawn on top of the arena: run stats, level-up picker, end card. */
export class Hud {
  private s: GameScene;
  private w = 0;
  private h = 0;

  private root!: Phaser.GameObjects.Container;
  private xpBg!: Phaser.GameObjects.Rectangle;
  private xpFill!: Phaser.GameObjects.Rectangle;
  private lvlText!: Phaser.GameObjects.Text;
  private hpBg!: Phaser.GameObjects.Rectangle;
  private hpFill!: Phaser.GameObjects.Rectangle;
  private stats: { icon: Phaser.GameObjects.Image; label: Phaser.GameObjects.Text }[] = [];
  private loadout!: Phaser.GameObjects.Container;

  private intro!: Phaser.GameObjects.Container;
  private overlay?: Phaser.GameObjects.Container;
  private relayout?: () => void;
  private bannerText!: Phaser.GameObjects.Text;
  private bossBar!: Phaser.GameObjects.Container;
  private bossFill!: Phaser.GameObjects.Rectangle;

  constructor(scene: GameScene) {
    this.s = scene;
    this.build();
  }

  // ------------------------------------------------------------------ build
  private label(size: number, color = '#ffffff') {
    return {
      fontFamily: FONT,
      fontSize: `${size}px`,
      color,
      stroke: '#16283d',
      strokeThickness: Math.max(3, size * 0.16)
    } as Phaser.Types.GameObjects.Text.TextStyle;
  }

  private build() {
    const s = this.s;
    this.root = s.add.container(0, 0).setScrollFactor(0).setDepth(D.hud);

    this.xpBg = s.add.rectangle(0, 0, 100, 16, 0x0d2136, 0.72).setOrigin(0, 0.5);
    this.xpFill = s.add.rectangle(0, 0, 100, 16, 0x7ee04a).setOrigin(0, 0.5);
    this.lvlText = s.add.text(0, 0, 'Lv 1', this.label(20, GOLD)).setOrigin(0, 0.5);

    this.hpBg = s.add.rectangle(0, 0, 100, 12, 0x0d2136, 0.72).setOrigin(0, 0.5);
    this.hpFill = s.add.rectangle(0, 0, 100, 12, 0xff5a4d).setOrigin(0, 0.5);

    this.root.add([this.xpBg, this.xpFill, this.lvlText, this.hpBg, this.hpFill]);

    for (const key of ['hud_time', 'hud_kills', 'hud_wave']) {
      const icon = s.add.image(0, 0, key).setScale(0.5).setOrigin(0.5);
      const label = s.add.text(0, 0, '0', this.label(20)).setOrigin(0, 0.5);
      this.stats.push({ icon, label });
      this.root.add([icon, label]);
    }

    this.loadout = s.add.container(0, 0);
    this.root.add(this.loadout);

    this.bannerText = s.add.text(0, 0, '', this.label(30, '#ff6b6b')).setOrigin(0.5).setAlpha(0);
    this.root.add(this.bannerText);

    const bossBg = s.add.rectangle(0, 0, 260, 18, 0x0d2136, 0.8).setOrigin(0.5);
    bossBg.setStrokeStyle(3, 0xff6b6b);
    this.bossFill = s.add.rectangle(-128, 0, 256, 14, 0xff4438).setOrigin(0, 0.5);
    const bossName = s.add.text(0, -22, 'BOSS', this.label(18, '#ff9a8f')).setOrigin(0.5);
    this.bossBar = s.add.container(0, 0, [bossBg, this.bossFill, bossName]).setVisible(false);
    this.root.add(this.bossBar);

    // intro
    const tap = s.add.text(0, 0, 'DRAG TO FLY', this.label(38, GOLD)).setOrigin(0.5);
    const sub = s.add.text(0, 44, 'Survive the swarm', this.label(20)).setOrigin(0.5);
    const hand = s.add.circle(0, -70, 26, 0xffffff, 0.9);
    s.tweens.add({ targets: hand, x: 70, duration: 900, yoyo: true, repeat: -1, ease: 'Sine.easeInOut' });
    s.tweens.add({ targets: tap, scale: 1.08, duration: 700, yoyo: true, repeat: -1, ease: 'Sine.easeInOut' });
    this.intro = s.add.container(0, 0, [hand, tap, sub]).setScrollFactor(0).setDepth(D.overlay);
    pin(this.root);
    pin(this.intro);
  }

  showIntro() {
    this.intro.setVisible(true);
  }

  hideIntro() {
    this.s.tweens.add({
      targets: this.intro,
      alpha: 0,
      duration: 250,
      onComplete: () => this.intro.setVisible(false)
    });
  }

  banner(text: string) {
    this.bannerText.setText(text).setAlpha(1).setScale(0.6);
    this.s.tweens.add({ targets: this.bannerText, scale: 1, duration: 260, ease: 'Back.easeOut' });
    this.s.tweens.add({ targets: this.bannerText, alpha: 0, delay: 1400, duration: 500 });
  }

  // ----------------------------------------------------------------- update
  update(_dt: number) {
    const s = this.s;
    this.xpFill.width = this.xpBg.width * Phaser.Math.Clamp(s.xp / s.xpNeed, 0, 1);
    this.lvlText.setText(`Lv ${s.level}`);
    this.hpFill.width = this.hpBg.width * Phaser.Math.Clamp(s.hp / s.maxHp, 0, 1);

    const t = Math.floor(s.elapsed);
    this.stats[0].label.setText(`${Math.floor(t / 60)}:${`${t % 60}`.padStart(2, '0')}`);
    this.stats[1].label.setText(`${s.kills}`);
    this.stats[2].label.setText(`${s.wave}`);

    const boss = s.bossState();
    this.bossBar.setVisible(!!boss);
    if (boss) this.bossFill.width = 256 * Phaser.Math.Clamp(boss.ratio, 0, 1);

    this.syncLoadout();
  }

  private syncLoadout() {
    const list = this.s.ownedList();
    while (this.loadout.length < list.length * 3) {
      const i = this.loadout.length / 3;
      const bg = this.s.add.rectangle(i * 44, 0, 38, 38, 0x0d2136, 0.66).setOrigin(0, 0);
      const icon = this.s.add.image(i * 44 + 19, 19, list[i].def.icon).setScale(0.41);
      const pip = this.s.add.text(i * 44 + 34, 26, '1', this.label(14, GOLD)).setOrigin(0.5);
      this.loadout.add([bg, icon, pip]);
      pin(bg);
      pin(icon);
      pin(pip);
    }
    for (let i = 0; i < list.length; i++) {
      const icon = this.loadout.getAt(i * 3 + 1) as Phaser.GameObjects.Image;
      const pip = this.loadout.getAt(i * 3 + 2) as Phaser.GameObjects.Text;
      icon.setTexture(list[i].def.icon);
      pip.setText(`${list[i].level}`);
    }
  }

  // -------------------------------------------------------------- level up
  openLevelUp() {
    const s = this.s;
    const c = s.add.container(0, 0).setScrollFactor(0).setDepth(D.overlay);
    const dim = s.add.rectangle(0, 0, this.w, this.h, 0x04101d, 0.82).setOrigin(0);
    const header = this.makeHeader();
    const refresh = this.makeRefresh();
    c.add([dim, header, refresh]);

    // Cards are rebuilt in place so Refresh can reroll without tearing the panel down.
    const deal = () => {
      for (let i = c.length - 1; i >= 3; i--) c.getAt(i).destroy();
      s.rollChoices().forEach((choice, i) => {
        const card = this.makeCard(choice.def, choice.level, () => {
          this.closeLevelUp();
          s.closeLevelUp(choice.def.id);
        });
        card.setData('index', i).setAlpha(0);
        c.add(card);
        s.tweens.add({ targets: card, alpha: 1, duration: 200, delay: 60 * i });
      });
      pin(c);
      this.relayout?.();
    };

    (refresh.getAt(0) as Phaser.GameObjects.Rectangle)
      .setInteractive({ useHandCursor: true })
      .on('pointerdown', deal);

    this.overlay = c;
    this.relayout = () => this.layoutOverlay(header, refresh);
    deal();
  }

  /** "◆ ——  SELECT A SKILL  —— ◆" */
  private makeHeader() {
    const s = this.s;
    const text = s.add.text(0, 0, 'SELECT A SKILL', this.label(28)).setOrigin(0.5);
    const rule = s.add.graphics();
    const half = text.width / 2;
    for (const dir of [-1, 1]) {
      const near = dir * (half + 18);
      const far = dir * (half + 86);
      rule.lineStyle(4, 0xffffff, 0.9).beginPath().moveTo(near, 0).lineTo(far, 0).strokePath();
      this.diamond(rule, dir * (half + 104), 0, 7, 0xffffff, 1);
    }
    return s.add.container(0, 0, [rule, text]);
  }

  private makeRefresh() {
    const s = this.s;
    const w = 260;
    const h = 62;
    const g = s.add.graphics();
    g.fillStyle(0xe09b00, 1).fillRoundedRect(-w / 2, -h / 2 + 6, w, h, 12);
    g.fillStyle(0xffc83d, 1).fillRoundedRect(-w / 2, -h / 2, w, h - 4, 12);
    const text = s.add.text(0, 0, 'Refresh', this.label(28)).setOrigin(0.5);
    const hit = s.add.rectangle(0, 0, w, h, 0x000000, 0).setOrigin(0.5);
    return s.add.container(0, 0, [hit, g, text]);
  }

  /** One full-width skill row: glow border, tinted wedge, framed icon, rarity pips. */
  private makeCard(def: SkillDef, level: number, onPick: () => void) {
    const s = this.s;
    const w = CARD.w;
    const h = CARD.h;
    const tone = def.kind === 'weapon' ? CARD.weapon : CARD.passive;
    const x0 = -w / 2;
    const y0 = -h / 2;

    const g = s.add.graphics();
    // outer glow: the same rounded outline stroked wider and fainter each pass
    for (let i = 3; i >= 1; i--) {
      g.lineStyle(3 + i * 3, tone.glow, 0.1 * i).strokeRoundedRect(x0, y0, w, h, CARD.radius + i);
    }
    g.fillStyle(CARD.fill, 1).fillRoundedRect(x0, y0, w, h, CARD.radius);

    // Wedge. Its two left corners are the card's own rounded corners, drawn into the
    // path - a geometry mask would have to track the card's world position and does not.
    const wedgeW = h * 1.28;
    const slant = h * 0.34;
    const r = CARD.radius;
    const wedge = s.add.graphics();
    wedge.fillStyle(tone.wedge, 1).beginPath();
    wedge.moveTo(x0 + r, y0);
    wedge.lineTo(x0 + wedgeW, y0);
    wedge.lineTo(x0 + wedgeW - slant, y0 + h);
    wedge.lineTo(x0 + r, y0 + h);
    wedge.arc(x0 + r, y0 + h - r, r, Math.PI / 2, Math.PI);
    wedge.lineTo(x0, y0 + r);
    wedge.arc(x0 + r, y0 + r, r, Math.PI, Math.PI * 1.5);
    wedge.closePath();
    wedge.fillPath();

    g.lineStyle(4, tone.glow, 1).strokeRoundedRect(x0, y0, w, h, CARD.radius);

    // icon slot
    const pad = h * 0.1;
    const slot = h - pad * 2;
    const sx = x0 + pad;
    const frame = s.add.graphics();
    frame.fillStyle(CARD.slot, 1).fillRoundedRect(sx, y0 + pad, slot, slot, 12);
    frame.lineStyle(4, 0xdfe7f5, 1).strokeRoundedRect(sx, y0 + pad, slot, slot, 12);
    const icon = s.add.image(sx + slot / 2, y0 + pad + slot / 2, def.icon);
    icon.setScale(Math.min(1, (slot - 16) / Math.max(icon.width, icon.height)));

    // rarity pips along the bottom of the wedge, gold up to the level being offered
    const pips = s.add.graphics();
    const total = Math.min(def.max, 5);
    const step = Math.min(18, (wedgeW - slant - pad * 2) / total);
    for (let i = 0; i < total; i++) {
      const on = i < level;
      this.diamond(pips, sx + step / 2 + i * step, y0 + h - pad * 0.9, 7, on ? CARD.pipOn : CARD.pipOff, 1);
    }

    const textX = x0 + pad * 2 + slot;
    const wrap = w - (textX - x0) - pad * 2;
    const title = s.add.text(textX, 0, def.title, this.label(26, tone.title)).setOrigin(0, 1);
    const desc = s.add
      .text(textX, 0, def.desc, { ...this.label(17, '#cdd4e4'), wordWrap: { width: wrap } })
      .setOrigin(0, 0);

    // Title sits just above the description block, the pair centred in the card.
    const stack = title.height + 6 + desc.height;
    title.y = -stack / 2 + title.height;
    desc.y = title.y + 6;

    const badge = s.add
      .text(x0 + w - pad, y0 + pad, level === 1 ? 'NEW!' : `Lv ${level}`, this.label(16, GOLD))
      .setOrigin(1, 0);

    const hit = s.add.rectangle(0, 0, w, h, 0x000000, 0).setOrigin(0.5);
    hit.setInteractive({ useHandCursor: true }).on('pointerdown', onPick);

    return s.add.container(0, 0, [g, wedge, frame, icon, pips, title, desc, badge, hit]);
  }

  private diamond(g: Phaser.GameObjects.Graphics, x: number, y: number, r: number, color: number, alpha: number) {
    g.fillStyle(color, alpha).fillPoints(
      [
        new Phaser.Geom.Point(x, y - r),
        new Phaser.Geom.Point(x + r, y),
        new Phaser.Geom.Point(x, y + r),
        new Phaser.Geom.Point(x - r, y)
      ],
      true
    );
  }

  /** Header tucks in on a short screen so three cards still fit under it. */
  private headerY() {
    return Phaser.Math.Clamp(this.h * 0.14, 40, 110);
  }

  /** Uniform scale that fits the card to the width and the stack to the height. */
  private cardScale() {
    const room = this.h - this.headerY() - 40 - 96; // header rule above, Refresh below
    const perCard = (room - 2 * CARD.gap) / 3;
    return Phaser.Math.Clamp(Math.min((this.w - 32) / CARD.w, perCard / CARD.h), 0.35, 1);
  }

  private layoutOverlay(header: Phaser.GameObjects.Container, refresh: Phaser.GameObjects.Container) {
    if (!this.overlay) return;
    const c = this.overlay;
    (c.getAt(0) as Phaser.GameObjects.Rectangle).setSize(this.w, this.h);

    const k = this.cardScale();
    const cardH = CARD.h * k;
    const gap = CARD.gap * k;
    const span = 3 * cardH + 2 * gap;
    const headerY = this.headerY();
    const top = headerY + 40 * k;
    const centre = Phaser.Math.Clamp(
      this.h / 2,
      top + span / 2,
      Math.max(top + span / 2, this.h - span / 2 - 84 * k)
    );

    header.setPosition(this.w / 2, headerY).setScale(k);
    refresh.setPosition(this.w / 2, Math.min(centre + span / 2 + 48 * k, this.h - 38 * k)).setScale(k);

    for (let i = 3; i < c.length; i++) {
      const card = c.getAt(i) as Phaser.GameObjects.Container;
      const idx = card.getData('index') as number;
      card.setPosition(this.w / 2, centre - span / 2 + cardH / 2 + idx * (cardH + gap)).setScale(k);
    }
  }

  private closeLevelUp() {
    this.overlay?.destroy(true);
    this.overlay = undefined;
    this.relayout = undefined;
  }

  // --------------------------------------------------------------- end card
  showEnd(won: boolean) {
    const s = this.s;
    this.closeLevelUp();
    const c = s.add.container(0, 0).setScrollFactor(0).setDepth(D.overlay);
    const dim = s.add.rectangle(0, 0, this.w, this.h, 0x04101d, 0.9).setOrigin(0);

    const icon = s.add.image(0, 0, 'appicon').setScale(0.42);
    const title = s.add.text(0, 0, won ? 'SKY CLEARED!' : 'SHOT DOWN!', this.label(40, GOLD)).setOrigin(0.5);
    const score = s.add
      .text(0, 0, `${s.kills} KILLS   ·   Lv ${s.level}   ·   WAVE ${s.wave}`, this.label(20))
      .setOrigin(0.5);
    const sub = s.add.text(0, 0, 'Explottens: Survival', this.label(22, '#8fe3ff')).setOrigin(0.5);

    const btnBg = s.add.rectangle(0, 0, 300, 84, 0x35c93f).setOrigin(0.5);
    btnBg.setStrokeStyle(5, 0x1c6d22);
    const btnText = s.add.text(0, 0, 'PLAY NOW', this.label(34)).setOrigin(0.5);
    const btn = s.add.container(0, 0, [btnBg, btnText]);
    s.tweens.add({ targets: btn, scale: 1.07, duration: 620, yoyo: true, repeat: -1, ease: 'Sine.easeInOut' });
    btnBg.setInteractive({ useHandCursor: true }).on('pointerdown', () => sdk.install());

    c.add([dim, icon, title, sub, score, btn]);
    this.overlay = c;
    pin(c);
    c.setData('end', true);
    this.layoutEnd();
  }

  private layoutEnd() {
    const c = this.overlay;
    if (!c || !c.getData('end')) return;
    const cx = this.w / 2;
    const cy = this.h / 2;
    const k = Math.min(1, Math.min(this.w / 420, this.h / 640));
    (c.getAt(0) as Phaser.GameObjects.Rectangle).setSize(this.w, this.h);
    (c.getAt(1) as Phaser.GameObjects.Image).setPosition(cx, cy - 190 * k).setScale(0.42 * k);
    (c.getAt(2) as Phaser.GameObjects.Text).setPosition(cx, cy - 50 * k).setScale(k);
    (c.getAt(3) as Phaser.GameObjects.Text).setPosition(cx, cy - 6 * k).setScale(k);
    (c.getAt(4) as Phaser.GameObjects.Text).setPosition(cx, cy + 40 * k).setScale(k);
    (c.getAt(5) as Phaser.GameObjects.Container).setPosition(cx, cy + 150 * k).setScale(k);
  }

  // ----------------------------------------------------------------- resize
  resize(width: number, height: number) {
    this.w = width;
    this.h = height;
    const pad = 14;
    const barW = width - pad * 2 - 74;

    this.xpBg.setPosition(pad, 24).setSize(barW, 16);
    this.xpFill.setPosition(pad, 24).setSize(barW, 16);
    this.lvlText.setPosition(pad + barW + 10, 24);

    this.hpBg.setPosition(pad, 48).setSize(barW, 12);
    this.hpFill.setPosition(pad, 48).setSize(barW, 12);

    this.stats.forEach((st, i) => {
      const x = pad + 16 + i * Math.min(110, (width - pad * 2) / 3);
      st.icon.setPosition(x, 84);
      st.label.setPosition(x + 18, 84);
    });

    this.loadout.setPosition(pad, height - 54);
    this.bannerText.setPosition(width / 2, height * 0.26);
    this.bossBar.setPosition(width / 2, 132);

    this.intro.setPosition(width / 2, height * 0.62);

    if (this.overlay?.getData('end')) {
      this.layoutEnd();
    } else if (this.overlay) {
      this.relayout?.();
    }
  }
}
