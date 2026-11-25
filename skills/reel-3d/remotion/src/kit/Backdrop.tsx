import * as THREE from "three";
import { useVideoConfig } from "remotion";
import { rgba, type Palette } from "./brand";
import { useDisposable } from "./geometry";
import { rng } from "./random";

export type BackdropProps = { palette: Palette; spot?: [number, number] | null; top?: string; bottom?: string };

export const Backdrop = ({ palette, spot = null, top, bottom }: BackdropProps) => {
  const { width, height } = useVideoConfig();
  const tokens = palette.three.backdrop;
  const topColor = palette.color(top ?? tokens.top);
  const bottomColor = palette.color(bottom ?? tokens.bottom);
  const spotColor = palette.color(tokens.spot);
  const spotX = spot?.[0] ?? -1;
  const spotY = spot?.[1] ?? -1;
  const texture = useDisposable(() => {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("2D canvas is not available");
    }
    const gradient = context.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, topColor);
    gradient.addColorStop(1, bottomColor);
    context.fillStyle = gradient;
    context.fillRect(0, 0, width, height);
    if (spotX >= 0) {
      const radius = tokens.spotRadius * Math.max(width, height);
      const glow = context.createRadialGradient(spotX, spotY, 0, spotX, spotY, radius);
      glow.addColorStop(0, rgba(spotColor, tokens.spotOpacity));
      glow.addColorStop(0.45, rgba(spotColor, tokens.spotOpacity * 0.42));
      glow.addColorStop(1, rgba(spotColor, 0));
      context.fillStyle = glow;
      context.fillRect(0, 0, width, height);
    }
    const pixels = context.getImageData(0, 0, width, height);
    const noise = rng(1709);
    const data = pixels.data;
    for (let i = 0; i < data.length; i += 4) {
      const offset = noise() - noise();
      data[i] = (data[i] ?? 0) + offset;
      data[i + 1] = (data[i + 1] ?? 0) + offset;
      data[i + 2] = (data[i + 2] ?? 0) + offset;
    }
    context.putImageData(pixels, 0, 0);
    const result = new THREE.CanvasTexture(canvas);
    result.colorSpace = THREE.SRGBColorSpace;
    result.minFilter = THREE.NearestFilter;
    result.magFilter = THREE.NearestFilter;
    result.generateMipmaps = false;
    return result;
  }, [width, height, topColor, bottomColor, spotColor, spotX, spotY, tokens.spotOpacity, tokens.spotRadius]);
  return <primitive attach="background" object={texture} />;
};

export const ShadowCatcher = ({ palette, y, size = 40 }: { palette: Palette; y: number; size?: number }) => (
  <mesh rotation-x={-Math.PI / 2} position-y={y} receiveShadow>
    <planeGeometry args={[size, size]} />
    <shadowMaterial color={palette.color(palette.three.shadow.color)} opacity={palette.three.shadow.opacity} transparent depthWrite={false} />
  </mesh>
);
