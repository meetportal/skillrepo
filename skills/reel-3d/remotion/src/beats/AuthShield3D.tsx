import { useMemo } from "react";
import * as THREE from "three";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { useTextWidths } from "../kit/assets";
import { Backdrop, ShadowCatcher } from "../kit/Backdrop";
import { BaseGlow } from "../kit/BaseGlow";
import { makePalette, type Palette, type Tone } from "../kit/brand";
import { CameraRig } from "../kit/CameraRig";
import { roundedSlab, shieldHalf, useDisposable } from "../kit/geometry";
import type { Fit, InsertProps, Timeline } from "../kit/insert";
import { resolveBeatProps } from "../kit/insert";
import { Lights } from "../kit/Lights";
import { glsl, patchStandard, tile } from "../kit/materials";
import { creep, deg, entrance, glide, holdSway, kickOffset, landFrameFor, progress } from "../kit/motion";
import { Scene3D } from "../kit/Scene3D";
import { SyncedText } from "../kit/SyncedText";

export type AuthShieldProps = {
  lockFrame: number;
  labels: string[];
  fromTone: Tone;
  toTone: Tone;
};

export const authShieldDefaults: AuthShieldProps = { lockFrame: 30, labels: ["SPF", "DKIM", "DMARC"], fromTone: "warning", toTone: "success" };

const staggerFrames = 3;
const plateEntranceFrames = 12;
const slideFrames = 6;
const drawFrames = 8;

export const authShieldTimeline = (props: AuthShieldProps): Timeline & { land: number } => {
  const land = landFrameFor(props.lockFrame, 1);
  return {
    land,
    events: [
      ...props.labels.map((_, i) => ({ id: `plate${i + 1}`, frame: i * staggerFrames + 3, kind: "pop" as const })),
      { id: "slide", frame: land - 1, kind: "whoosh" as const },
      { id: "lock", frame: land, kind: "impact" as const },
      { id: "seal", frame: land + 6, kind: "glint" as const },
    ],
  };
};

type Plate = { label: string; width: number; height: number; lock: [number, number]; spread: [number, number]; from: [number, number, number] };

type Layout = {
  camera: { position: [number, number, number]; principal: [number, number]; creepRate: number };
  font: number;
  plates: Plate[];
  shield: { width: number; height: number; centerY: number; shoulder: number; tube: number };
  floor: number;
  spot: [number, number];
};

const plateHeightCard = 0.86;
const plateHeightTall = 1.0;
const pad = 0.24;

const cardLayout = (labels: string[], ems: number[], width: number, height: number): Layout => {
  const shieldWidth = 6.9;
  const gap = 0.08;
  const rowMax = shieldWidth - 0.7;
  const sumEm = ems.reduce((a, b) => a + b, 0);
  const font = Math.min(0.72, (rowMax - labels.length * pad * 2 - gap * (labels.length - 1)) / sumEm);
  const widths = ems.map((em) => em * font + pad * 2);
  const row = widths.reduce((a, b) => a + b, 0) + gap * (labels.length - 1);
  const plateY = 0.22;
  let x = -row / 2;
  const plates = labels.map((label, i) => {
    const w = widths[i] ?? 1;
    const cx = x + w / 2;
    x += w + gap;
    const spreadX = cx + (i - (labels.length - 1) / 2) * 0.34;
    return { label, width: w, height: plateHeightCard, lock: [cx, plateY] as [number, number], spread: [spreadX, plateY] as [number, number], from: [spreadX + 0.5, plateY - 0.9, -1.2] as [number, number, number] };
  });
  const top = plateY + plateHeightCard / 2 + 0.3;
  const tip = -1.28;
  const sideBottom = plateY - plateHeightCard / 2 - 0.14;
  return {
    camera: { position: [0, 0.7, 5.5], principal: [width / 2, height / 2 - 18], creepRate: 0.0015 },
    font,
    plates,
    shield: { width: shieldWidth, height: top - tip, centerY: (top + tip) / 2, shoulder: (top - sideBottom) / (top - tip), tube: 0.075 },
    floor: tip - 0.02,
    spot: [width / 2, height * 0.45],
  };
};

const tallLayout = (labels: string[], ems: number[], width: number): Layout => {
  const font = 0.78;
  const plateWidth = Math.max(...ems) * font + pad * 2.4;
  const gap = 0.2;
  const stack = labels.length * plateHeightTall + gap * (labels.length - 1);
  const center = 0.55;
  const plates = labels.map((label, i) => {
    const cy = center + stack / 2 - plateHeightTall / 2 - i * (plateHeightTall + gap);
    const spreadY = cy + ((labels.length - 1) / 2 - i) * 0.45;
    const side = i % 2 === 0 ? -1 : 1;
    return { label, width: plateWidth, height: plateHeightTall, lock: [0, cy] as [number, number], spread: [side * 0.25, spreadY] as [number, number], from: [side * 2.2, spreadY - 0.4, -1.5] as [number, number, number] };
  });
  const top = center + stack / 2 + 0.45;
  const sideBottom = center - stack / 2 - 0.2;
  const tip = sideBottom - 1.75;
  return {
    camera: { position: [0, 1.7, 37], principal: [width / 2, 716], creepRate: 0.0025 },
    font,
    plates,
    shield: { width: plateWidth + 1.05, height: top - tip, centerY: (top + tip) / 2, shoulder: (top - sideBottom) / (top - tip), tube: 0.1 },
    floor: tip - 0.02,
    spot: [width / 2, 730],
  };
};

const useShieldMaterial = (palette: Palette) => {
  const uniforms = useMemo(() => ({ uSweep: { value: 10 }, uSweepGain: { value: 0 } }), []);
  const material = useDisposable(
    () =>
      patchStandard(
        new THREE.MeshStandardMaterial({ roughness: 0.32, metalness: 0.1 }),
        {
          uniforms,
          vertexHead: "varying vec3 vR3dLocal;",
          vertexBody: "vR3dLocal = position;",
          fragmentHead: `varying vec3 vR3dLocal;\nuniform float uSweep;\nuniform float uSweepGain;\n${glsl.noise}`,
          afterEmissive: "totalEmissiveRadiance *= 1.0 + uSweepGain * exp(-pow((vR3dLocal.y - uSweep) / 0.35, 2.0));",
        },
        "reel3d-shield",
      ),
    [palette, uniforms],
  );
  return { material, uniforms };
};

const ShieldHalf = ({ width, height, side, shoulder, tube, drawn, material }: { width: number; height: number; side: 1 | -1; shoulder: number; tube: number; drawn: number; material: THREE.Material }) => {
  const radial = 12;
  const tubular = 120;
  const geometry = useDisposable(() => new THREE.TubeGeometry(shieldHalf(width, height, side, shoulder), tubular, tube, radial, false), [width, height, side, shoulder, tube]);
  const segments = Math.round(tubular * drawn);
  geometry.setDrawRange(0, segments * radial * 6);
  return <mesh geometry={geometry} material={material} visible={segments > 0} castShadow />;
};

const PlateMesh = ({ palette, plate, font, color }: { palette: Palette; plate: Plate; font: number; color: string }) => {
  const geometry = useDisposable(() => roundedSlab(plate.width, plate.height, 0.16, { depth: 0.22, bevel: 0.04 }), [plate.width, plate.height]);
  return (
    <group>
      <mesh geometry={geometry} castShadow receiveShadow>
        <meshStandardMaterial {...tile(palette, "border")} />
      </mesh>
      <SyncedText font={palette.font(700)} fontSize={font} color={color} position={[0, -0.01, 0.16]} anchorX="center" anchorY="middle">
        {plate.label}
      </SyncedText>
    </group>
  );
};

const Shield = ({ palette, layout, frame, land, tone }: { palette: Palette; layout: Layout; frame: number; land: number; tone: THREE.Color }) => {
  const { material, uniforms } = useShieldMaterial(palette);
  const drawn = glide(progress(frame, land - drawFrames, drawFrames));
  const settled = progress(frame, land, 4);
  material.color.copy(tone);
  material.emissive.copy(tone);
  material.emissiveIntensity = 0.12 + 0.22 * settled;
  const s = layout.shield;
  uniforms.uSweep.value = s.height / 2 + 0.6 - (s.height + 1.6) * progress(frame, land + 3, 18);
  uniforms.uSweepGain.value = settled * 1.4;
  return (
    <group position-y={s.centerY}>
      <ShieldHalf width={s.width} height={s.height} side={1} shoulder={s.shoulder} tube={s.tube} drawn={drawn} material={material} />
      <ShieldHalf width={s.width} height={s.height} side={-1} shoulder={s.shoulder} tube={s.tube} drawn={drawn} material={material} />
    </group>
  );
};

export const AuthShield3D = (input: InsertProps<AuthShieldProps>) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const props = resolveBeatProps("AuthShield3D", authShieldDefaults, input.beatProps);
  const palette = useMemo(() => makePalette(input.brand, input.assetBase), [input.brand, input.assetBase]);
  const ems = useTextWidths(palette.font(700), props.labels);
  const fit: Fit = input.fit ?? (height > width ? "full" : "card");
  const layout = useMemo(
    () => (ems ? (fit === "full" ? tallLayout(props.labels, ems, width) : cardLayout(props.labels, ems, width, height)) : null),
    [ems, fit, props.labels, width, height],
  );
  const { land } = authShieldTimeline(props);
  const toneMix = glide(progress(frame, land, 3));
  const tone = new THREE.Color(palette.tone(props.fromTone)).lerp(new THREE.Color(palette.tone(props.toTone)), toneMix);
  const toneHex = `#${tone.getHexString()}`;
  const slide = glide(progress(frame, land - slideFrames, slideFrames));
  const sway = holdSway(frame, land, fit === "full" ? 2.2 : 0.8, 72);
  return (
    <AbsoluteFill>
      {layout ? (
        <Scene3D palette={palette}>
          <Backdrop palette={palette} spot={layout.spot} />
          <CameraRig
            palette={palette}
            position={layout.camera.position}
            target={[0, 0, 0]}
            principal={layout.camera.principal}
            shiftPx={kickOffset(frame, land)}
            dolly={creep(frame, 0, layout.camera.creepRate)}
          />
          <Lights palette={palette} tone={props.toTone} rimColor={toneHex} rimScale={0.75 + 0.25 * toneMix} />
          <group rotation-y={sway}>
            {layout.plates.map((plate, i) => {
              const enter = entrance(frame, i * staggerFrames, { frames: plateEntranceFrames, turnDeg: 30 });
              const sx = plate.spread[0] + (plate.lock[0] - plate.spread[0]) * slide;
              const sy = plate.spread[1] + (plate.lock[1] - plate.spread[1]) * slide;
              const x = plate.from[0] + (sx - plate.from[0]) * enter.p;
              const y = plate.from[1] + (sy - plate.from[1]) * enter.p;
              const z = plate.from[2] * (1 - enter.p);
              return (
                <group key={plate.label} position={[x, y, z]} rotation-y={(i % 2 === 0 ? -1 : 1) * enter.turn} rotation-x={deg(-8) * (1 - enter.p)}>
                  <PlateMesh palette={palette} plate={plate} font={layout.font} color={palette.color("text")} />
                </group>
              );
            })}
            <Shield palette={palette} layout={layout} frame={frame} land={land} tone={tone} />
            <BaseGlow palette={palette} color={toneHex} radius={fit === "full" ? 3.2 : 4.4} position={[0, layout.floor + 0.005, 0]} strength={0.4 + 0.6 * toneMix} />
          </group>
          <ShadowCatcher palette={palette} y={layout.floor} />
        </Scene3D>
      ) : null}
    </AbsoluteFill>
  );
};
