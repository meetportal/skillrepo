import * as THREE from "three";
import type { Palette } from "./brand";

export const clay = (palette: Palette, color: string) => ({
  color: palette.color(color),
  roughness: palette.three.materials.clayRoughness,
  metalness: 0,
  emissive: palette.color(palette.three.darkest),
  emissiveIntensity: 1,
});

export const tile = (palette: Palette, color: string) => ({
  color: palette.color(color),
  roughness: palette.three.materials.tileRoughness,
  metalness: 0.05,
  emissive: palette.color(palette.three.darkest),
  emissiveIntensity: 1,
});

export const glowTexture = (size = 256, falloff = [1, 0.55, 0.22, 0.06, 0]) => {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("2D canvas is not available");
  }
  const half = size / 2;
  const gradient = context.createRadialGradient(half, half, 0, half, half, half);
  falloff.forEach((alpha, index) => gradient.addColorStop(index / (falloff.length - 1), `rgba(255,255,255,${alpha})`));
  context.fillStyle = gradient;
  context.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
};

export type ShaderPatch = { uniforms: Record<string, THREE.IUniform>; vertexHead?: string; vertexBody?: string; fragmentHead?: string; afterColor?: string; afterEmissive?: string };

export const patchStandard = (material: THREE.MeshStandardMaterial, patch: ShaderPatch, cacheKey: string) => {
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, patch.uniforms);
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", `#include <common>\n${patch.vertexHead ?? ""}`)
      .replace("#include <worldpos_vertex>", `#include <worldpos_vertex>\n${patch.vertexBody ?? ""}`);
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", `#include <common>\n${patch.fragmentHead ?? ""}`)
      .replace("#include <color_fragment>", `#include <color_fragment>\n${patch.afterColor ?? ""}`)
      .replace("#include <emissivemap_fragment>", `#include <emissivemap_fragment>\n${patch.afterEmissive ?? ""}`);
  };
  material.customProgramCacheKey = () => cacheKey;
  return material;
};

export const glsl = {
  noise: `
float r3dHash(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float r3dNoise(vec2 p) {
  vec2 i = floor(p); vec2 f = fract(p);
  float a = r3dHash(i); float b = r3dHash(i + vec2(1.0, 0.0));
  float c = r3dHash(i + vec2(0.0, 1.0)); float d = r3dHash(i + vec2(1.0, 1.0));
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
float r3dFbm(vec2 p) {
  float v = 0.0; float amp = 0.5;
  for (int i = 0; i < 5; i++) { v += amp * r3dNoise(p); p = p * 2.03 + vec2(1.7, 9.2); amp *= 0.5; }
  return v;
}
`,
};
