import type { Palette, Tone } from "./brand";
import { toVec3 } from "./brand";

export type LightsProps = { palette: Palette; tone: Tone; rimColor?: string; rimScale?: number };

export const Lights = ({ palette, tone, rimColor, rimScale = 1 }: LightsProps) => {
  const { fill, key, rim } = palette.three;
  const keyPosition = toVec3(key.position, "key.position");
  const rimPosition = toVec3(rim.position, "rim.position");
  const bounds = key.shadowBounds;
  return (
    <>
      <hemisphereLight args={[palette.color(fill.sky), palette.color(fill.ground), fill.intensity]} />
      <directionalLight
        position={keyPosition}
        intensity={key.intensity}
        castShadow
        shadow-mapSize={[key.shadowMapSize, key.shadowMapSize]}
        shadow-camera-left={-bounds}
        shadow-camera-right={bounds}
        shadow-camera-top={bounds}
        shadow-camera-bottom={-bounds}
        shadow-camera-near={0.5}
        shadow-camera-far={30}
        shadow-bias={key.shadowBias}
        shadow-normalBias={key.shadowNormalBias}
      />
      <directionalLight position={rimPosition} intensity={rim.intensity * rimScale} color={rimColor ?? palette.tone(tone)} />
    </>
  );
};
