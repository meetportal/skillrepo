import * as THREE from "three";
import type { Palette } from "./brand";
import { useDisposable } from "./geometry";
import { glowTexture } from "./materials";

export type BaseGlowProps = { palette: Palette; color: string; radius: number; position: [number, number, number]; strength?: number; facing?: "up" | "camera" };

export const BaseGlow = ({ palette, color, radius, position, strength = 1, facing = "up" }: BaseGlowProps) => {
  const texture = useDisposable(() => glowTexture(), []);
  const opacity = Math.min(1, Math.max(0, palette.three.baseGlowOpacity * strength));
  return (
    <mesh position={position} rotation-x={facing === "up" ? -Math.PI / 2 : 0} renderOrder={-1}>
      <planeGeometry args={[radius * 2, radius * 2]} />
      <meshBasicMaterial
        map={texture}
        color={palette.color(color)}
        transparent
        opacity={opacity}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        toneMapped={false}
      />
    </mesh>
  );
};
