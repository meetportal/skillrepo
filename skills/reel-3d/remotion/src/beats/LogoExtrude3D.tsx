import { useMemo } from "react";
import * as THREE from "three";
import { AbsoluteFill, Img, useCurrentFrame, useVideoConfig } from "remotion";
import { useAssetText } from "../kit/assets";
import { Backdrop } from "../kit/Backdrop";
import { makePalette, type Palette } from "../kit/brand";
import { CameraRig, pxPerUnit } from "../kit/CameraRig";
import { svgToParts, svgViewBox, useDisposable, type SvgBox } from "../kit/geometry";
import type { InsertProps, Timeline } from "../kit/insert";
import { resolveBeatProps } from "../kit/insert";
import { Lights } from "../kit/Lights";
import { glsl, patchStandard } from "../kit/materials";
import { deg, glide, progress } from "../kit/motion";
import { Scene3D } from "../kit/Scene3D";

export type LogoCard = "navy" | "cream";

export type LogoExtrudeProps = {
  card: LogoCard;
  logo: string | null;
  widthPx: number;
  centerY: number;
  yawDeg: number;
};

export const logoExtrudeDefaults: LogoExtrudeProps = { card: "navy", logo: null, widthPx: 800, centerY: 870, yawDeg: 35 };

export const logoForCard = (card: LogoCard) => (card === "navy" ? "white" : "color");

export const logoPopMarkWidth = (widthPx: number) => widthPx - 2 * Math.round(widthPx * 0.1);

export const logoDepth = 0.12;
export const logoBevel = 0.012;
const handoffFrames = 4;
const glintFrames = 9;
const cameraDistance = 20;

export const logoExtrudeTimeline = (_props: LogoExtrudeProps, frames: number): Timeline & { turnFrames: number; glintStart: number; handoffStart: number } => {
  const turnFrames = Math.min(24, Math.max(14, frames - handoffFrames));
  const glintStart = Math.max(2, turnFrames - glintFrames - 1);
  return {
    turnFrames,
    glintStart,
    handoffStart: frames - handoffFrames,
    events: [
      { id: "turn", frame: turnFrames - 1, kind: "whoosh" as const },
      { id: "glint", frame: glintStart + Math.floor(glintFrames / 2), kind: "glint" as const },
      { id: "front", frame: turnFrames, kind: "pop" as const },
    ],
  };
};

const useLogoMaterial = (palette: Palette, color: string, key: string) => {
  const uniforms = useMemo(() => ({ uGlint: { value: -100 }, uGlintColor: { value: new THREE.Color("#FFFFFF") } }), []);
  const material = useDisposable(() => {
    const base = new THREE.MeshStandardMaterial({ color, roughness: 0.5, metalness: 0, emissive: color, emissiveIntensity: 0.04 });
    return patchStandard(
      base,
      {
        uniforms,
        vertexHead: "varying vec2 vR3dSweep;\nvarying float vR3dFront;\nvarying float vR3dFacing;",
        vertexBody: "vR3dSweep = position.xy;\nvR3dFront = step(0.5, normal.z);\nvR3dFacing = normal.z;",
        fragmentHead: `varying vec2 vR3dSweep;\nvarying float vR3dFront;\nvarying float vR3dFacing;\nuniform float uGlint;\nuniform vec3 uGlintColor;\n${glsl.noise}`,
        afterColor: "diffuseColor.rgb *= mix(0.12, 1.0, smoothstep(0.15, 0.6, vR3dFacing));",
        afterEmissive: "totalEmissiveRadiance *= mix(0.2, 1.0, vR3dFront);\ntotalEmissiveRadiance += uGlintColor * vR3dFront * 0.85 * exp(-pow((vR3dSweep.x + vR3dSweep.y * 0.55 - uGlint) / 0.09, 2.0));",
      },
      `reel3d-logo-${key}`,
    );
  }, [color, uniforms]);
  return { material, uniforms };
};

const LogoPart = ({ palette, geometry, color, glint, visible, index }: { palette: Palette; geometry: THREE.BufferGeometry; color: string; glint: number; visible: boolean; index: number }) => {
  const { material, uniforms } = useLogoMaterial(palette, color, String(index));
  uniforms.uGlint.value = glint;
  return <mesh geometry={geometry} material={material} visible={visible} castShadow receiveShadow />;
};

const LogoMesh = ({ palette, svg, box, scale, glint, visible }: { palette: Palette; svg: string; box: SvgBox; scale: number; glint: number; visible: boolean }) => {
  const parts = useDisposable(() => {
    const list = svgToParts(svg, logoDepth, logoBevel, scale);
    return { list, dispose: () => list.forEach((part) => part.geometry.dispose()) };
  }, [svg, scale]);
  const offset: [number, number, number] = [-(box.minX + box.width / 2) * scale, (box.minY + box.height / 2) * scale, 0];
  return (
    <group position={offset}>
      {parts.list.map((part, index) => (
        <LogoPart key={part.color} palette={palette} geometry={part.geometry} color={part.color} glint={glint - offset[0] - offset[1] * 0.55} visible={visible} index={index} />
      ))}
    </group>
  );
};

export const LogoExtrude3D = (input: InsertProps<LogoExtrudeProps>) => {
  const frame = useCurrentFrame();
  const { height, durationInFrames } = useVideoConfig();
  const props = resolveBeatProps("LogoExtrude3D", logoExtrudeDefaults, input.beatProps);
  const palette = useMemo(() => makePalette(input.brand, input.assetBase), [input.brand, input.assetBase]);
  const src = palette.logo(props.logo ?? logoForCard(props.card));
  const centerX = (input.brand.layout.safe.x0 + input.brand.layout.safe.x1) / 2;
  const markWidth = logoPopMarkWidth(props.widthPx);
  const svg = useAssetText(src);
  const box = useMemo(() => (svg ? svgViewBox(svg) : null), [svg]);
  const timeline = logoExtrudeTimeline(props, durationInFrames);
  const unit = pxPerUnit(palette, height, cameraDistance);
  const scale = box ? markWidth / box.width / unit : 1;
  const yaw = deg(props.yawDeg) * (1 - glide(progress(frame, 0, timeline.turnFrames)));
  const halfWidth = box ? (box.width * scale) / 2 : 1;
  const glint = -halfWidth * 1.6 + halfWidth * 3.2 * progress(frame, timeline.glintStart, glintFrames);
  const handoff = frame < timeline.handoffStart ? 0 : (frame - timeline.handoffStart + 1) / handoffFrames;
  const heightPx = box ? (markWidth * box.height) / box.width : 0;
  const backdrop = props.card === "cream" ? { top: "cream", bottom: "cream" } : {};
  return (
    <AbsoluteFill>
      {svg && box ? (
        <>
          <Scene3D palette={palette}>
            <Backdrop palette={palette} spot={props.card === "cream" ? null : [centerX, props.centerY]} {...backdrop} />
            <CameraRig palette={palette} position={[0, 0, cameraDistance]} target={[0, 0, 0]} principal={[centerX, props.centerY]} />
            <Lights palette={palette} tone="brand" />
            <group rotation-y={yaw}>
              <LogoMesh palette={palette} svg={svg} box={box} scale={scale} glint={glint} visible={handoff < 1} />
            </group>
          </Scene3D>
          <Img
            src={src}
            style={{
              position: "absolute",
              left: centerX - markWidth / 2,
              top: props.centerY - heightPx / 2,
              width: markWidth,
              height: heightPx,
              opacity: handoff,
            }}
          />
        </>
      ) : null}
    </AbsoluteFill>
  );
};
