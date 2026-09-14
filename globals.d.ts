/// <reference types="@smoud/playable-sdk/defines" />
/// <reference types="@smoud/playable-scripts/defines" />
// webpack serves .json through asset/source (raw text), not resolveJsonModule's parsed
// object — declare the skeleton explicitly so its type matches what actually loads.
declare module 'assets/spine_player.json' {
  const src: string;
  export default src;
}
