import * as Phaser from 'phaser';
// Side-effect import: the bundle hangs the plugin class off window.SpinePlugin.
// It carries the Spine 3.8.95 runtime the player skeleton is converted for.
import 'phaser/plugins/spine/dist/SpinePlugin.min.js';
// Side-effect import: the bundle hangs the plugin class off window.SpinePlugin.
// It carries the Spine 3.8.95 runtime the player skeleton is converted for.
import { GameScene } from './GameScene';

export class Game extends Phaser.Game {
  constructor(width: number, height: number) {
    super({
      type: Phaser.AUTO,
      width,
      height,
      backgroundColor: '#57bdf9',
      parent: document.body,
      powerPreference: 'high-performance',
      render: { antialias: true, roundPixels: false },
      // Playables run in a cross-origin iframe where Phaser's window.top listeners
      // throw; the canvas listeners are all this game needs.
      input: { windowEvents: false },
      scale: { mode: Phaser.Scale.NONE, autoCenter: Phaser.Scale.CENTER_BOTH },
      plugins: {
        scene: [{ key: 'SpinePlugin', plugin: (window as any).SpinePlugin, mapping: 'spine' }]
      },
      scene: GameScene
    });
  }

  private get main(): GameScene | undefined {
    return this.scene.getScene('GameScene') as GameScene | undefined;
  }

  public resize(width: number, height: number): void {
    this.scale.resize(width, height);
    this.main?.resize(width, height);
  }

  public pause(): void {
    this.scene.pause('GameScene');
  }

  public resume(): void {
    this.scene.resume('GameScene');
  }

  public volume(value: number): void {
    this.sound.setVolume(value);
  }

  public finish(): void {
    /* ad network ended the placement — nothing to tear down */
  }
}
