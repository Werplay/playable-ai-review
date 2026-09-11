import * as Phaser from 'phaser';
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
      scale: { mode: Phaser.Scale.NONE, autoCenter: Phaser.Scale.CENTER_BOTH },
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
