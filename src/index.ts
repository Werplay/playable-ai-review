import { sdk } from '@smoud/playable-sdk';
import { Game } from './Game';
import { FONT, FONT_URL } from './data';
import './index.css';

// The game's own typeface (Assets/GameFont/LuckiestGuy-Regular.ttf) is inlined by the
// bundler; register it before Phaser measures any text.
const font = new FontFace(FONT, `url(${FONT_URL})`);
const ready = font
  .load()
  .then((f) => {
    (document as any).fonts.add(f);
  })
  .catch(() => undefined);

sdk.init((width: number, height: number) => {
  ready.then(() => {
    const game = new Game(width, height);
    sdk.on('resize', game.resize, game);
    sdk.on('pause', game.pause, game);
    sdk.on('resume', game.resume, game);
    sdk.on('volume', game.volume, game);
    sdk.on('finish', game.finish, game);
  });
});
