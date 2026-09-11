import * as Phaser from 'phaser';
import { sdk } from '@smoud/playable-sdk';
import { FONT, SkillDef } from './data';
import type { GameScene } from './GameScene';

const D = { hud: 100, overlay: 200 };
const GOLD = '#ffd34d';

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
      const icon = this.s.add.image(i * 44 + 19, 19, list[i].def.icon).setScale(0.34);
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
    const choices = s.rollChoices();
    const c = s.add.container(0, 0).setScrollFactor(0).setDepth(D.overlay);

    const dim = s.add.rectangle(0, 0, this.w, this.h, 0x04101d, 0.82).setOrigin(0);
    const title = s.add.text(0, 0, 'LEVEL UP!', this.label(40, GOLD)).setOrigin(0.5);
    c.add([dim, title]);

    // three across only when three actually fit; otherwise stack wide rows
    const narrow = this.w < 620;
    const cardW = narrow ? Math.min(this.w - 40, 400) : Math.min(260, (this.w - 88) / 3);
    const cardH = narrow ? Math.min(116, (this.h - 170) / 3) : Math.min(300, this.h - 170);

    choices.forEach((choice, i) => {
      const card = this.makeCard(choice.def, choice.level, cardW, cardH, narrow);
      card.setData('index', i);
      c.add(card);
      card.setAlpha(0);
      card.setData('slideFrom', 40);
      s.tweens.add({ targets: card, alpha: 1, duration: 200, delay: 60 * i });
      (card.getAt(0) as Phaser.GameObjects.Rectangle).setInteractive({ useHandCursor: true }).on('pointerdown', () => {
        this.closeLevelUp();
        s.closeLevelUp(choice.def.id);
      });
    });

    this.overlay = c;
    pin(c);
    this.relayout = () => this.layoutOverlay(cardW, cardH, narrow, title);
    this.relayout();
  }

  private makeCard(def: SkillDef, level: number, w: number, h: number, narrow: boolean) {
    const s = this.s;
    const isWeapon = def.kind === 'weapon';
    const bg = s.add.rectangle(0, 0, w, h, 0x11263d, 0.98).setOrigin(0.5);
    bg.setStrokeStyle(4, isWeapon ? 0xffb23d : 0x54c8ff);

    const icon = s.add
      .image(narrow ? -w / 2 + 56 : 0, narrow ? 0 : -h / 2 + h * 0.28, def.icon)
      .setScale(narrow ? 0.68 : 0.82);

    const textX = narrow ? -w / 2 + 112 : 0;
    const ox = narrow ? 0 : 0.5;
    const wrap = narrow ? w - 132 : w - 36;

    const name = s.add
      .text(textX, 0, def.title, this.label(narrow ? 22 : 24, isWeapon ? '#ffce5c' : '#8fe3ff'))
      .setOrigin(ox, 0);
    const desc = s.add
      .text(textX, 0, def.desc, {
        ...this.label(narrow ? 15 : 17),
        wordWrap: { width: wrap },
        align: narrow ? 'left' : 'center'
      })
      .setOrigin(ox, 0);
    const lv = s.add
      .text(textX, 0, level === 1 ? 'NEW!' : `Lv ${level}`, this.label(narrow ? 16 : 19, GOLD))
      .setOrigin(ox, 0);

    // One stacked text column in both layouts — pinning the level line to the card
    // bottom lets a three-line description run straight through it.
    const gap = narrow ? 4 : 8;
    const stack = name.height + desc.height + lv.height + gap * 2;
    let y = narrow ? -stack / 2 : Math.min(h * 0.06, h / 2 - stack - 12);
    for (const t of [name, desc, lv]) {
      t.y = y;
      y += t.height + gap;
    }

    return s.add.container(0, 0, [bg, icon, name, desc, lv]);
  }

  private layoutOverlay(cardW: number, cardH: number, narrow: boolean, title: Phaser.GameObjects.Text) {
    if (!this.overlay) return;
    const c = this.overlay;
    (c.getAt(0) as Phaser.GameObjects.Rectangle).setSize(this.w, this.h);

    const gap = narrow ? 14 : 22;
    const span = narrow ? 3 * cardH + 2 * gap : cardH;
    const titleY = Math.max(this.h * 0.12, 74);
    const top = titleY + title.height / 2 + (narrow ? 26 : 20);
    // centre the stack when there is room, but never let it ride up under the title
    const centre = Phaser.Math.Clamp(this.h / 2, top + span / 2, Math.max(top + span / 2, this.h - span / 2 - 12));

    title.setPosition(this.w / 2, titleY);

    for (let i = 2; i < c.length; i++) {
      const card = c.getAt(i) as Phaser.GameObjects.Container;
      const k = card.getData('index') as number;
      if (narrow) {
        card.setPosition(this.w / 2, centre - span / 2 + cardH / 2 + k * (cardH + gap));
      } else {
        const row = 3 * cardW + 2 * gap;
        card.setPosition(this.w / 2 - row / 2 + cardW / 2 + k * (cardW + gap), centre);
      }
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
