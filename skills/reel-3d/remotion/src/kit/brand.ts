import { staticFile } from "remotion";

export type Tone = "danger" | "success" | "accent" | "brand" | "warning";

export const tones: Tone[] = ["danger", "success", "accent", "brand", "warning"];

export type Vec3 = [number, number, number];

export type ThreeTokens = {
  backdrop: { top: string; bottom: string; spot: string; spotOpacity: number; spotRadius: number };
  fill: { sky: string; ground: string; intensity: number };
  key: { position: number[]; intensity: number; shadowMapSize: number; shadowBounds: number; shadowBias: number; shadowNormalBias: number };
  rim: { position: number[]; intensity: number; meaning: Record<Tone, string> };
  shadow: { color: string; opacity: number };
  baseGlowOpacity: number;
  materials: { clayRoughness: number; tileRoughness: number };
  envelope: { body: string; flap: string; seal: string };
  burnt: string;
  darkest: string;
  camera: { fov: number; near: number; far: number };
};

export type BrandInput = {
  colors: Record<string, string>;
  layout: { width: number; height: number; safe: { x0: number; x1: number; y0: number; y1: number } };
  three: ThreeTokens;
  logos: Record<string, string>;
  fonts: { sans: { files: Record<string, string> } };
};

export type Palette = {
  color: (token: string) => string;
  tone: (tone: Tone) => string;
  three: ThreeTokens;
  font: (weight: number) => string;
  logo: (key: string) => string;
  asset: (path: string) => string;
};

export const brandAssetFolder = ".reel-3d-brand";

const hexPattern = /^#[0-9a-fA-F]{6}$/;

const vec3 = (values: number[], name: string): Vec3 => {
  const [x, y, z] = values;
  if (values.length !== 3 || x === undefined || y === undefined || z === undefined) {
    throw new Error(`brand three.${name} must be [x, y, z]`);
  }
  return [x, y, z];
};

export const toVec3 = vec3;

export const makePalette = (brand: BrandInput, assetBase: string = brandAssetFolder): Palette => {
  if (!brand.three) {
    throw new Error("brand.json has no three block; see mailinfra-brand/brand.json");
  }
  const color = (token: string) => {
    if (hexPattern.test(token)) {
      return token.toUpperCase();
    }
    const value = brand.colors[token];
    if (value === undefined || !hexPattern.test(value)) {
      throw new Error(`brand colour token ${token} is not defined`);
    }
    return value.toUpperCase();
  };
  const asset = (path: string) => staticFile(`${assetBase}/${path.replace(/^assets\//, "")}`);
  return {
    color,
    tone: (tone) => color(brand.three.rim.meaning[tone]),
    three: brand.three,
    font: (weight) => {
      const file = brand.fonts.sans.files[String(weight)];
      if (!file) {
        throw new Error(`brand sans font has no weight ${weight}`);
      }
      return asset(file);
    },
    logo: (key) => {
      const file = brand.logos[key];
      if (!file) {
        throw new Error(`brand logo ${key} is not defined`);
      }
      return asset(file);
    },
    asset,
  };
};

export const hexToRgb = (hex: string): Vec3 => {
  const value = Number.parseInt(hex.replace("#", ""), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
};

export const rgba = (hex: string, alpha: number) => {
  const [r, g, b] = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};
