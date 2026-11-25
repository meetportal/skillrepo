import { useMemo } from "react";
import * as THREE from "three";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { useTextWidths } from "../kit/assets";
import { Backdrop, ShadowCatcher } from "../kit/Backdrop";
import { BaseGlow } from "../kit/BaseGlow";
import { makePalette, type Palette, type Tone } from "../kit/brand";
import { CameraRig } from "../kit/CameraRig";
import { roundedSlab, useDisposable } from "../kit/geometry";
import type { InsertProps, Timeline } from "../kit/insert";
import { resolveBeatProps } from "../kit/insert";
import { Lights } from "../kit/Lights";
import { clay, tile } from "../kit/materials";
import { arrive, creep, deg, entrance, glide, holdSway, kickOffset, landFrameFor, progress } from "../kit/motion";
import { Scene3D } from "../kit/Scene3D";
import { SyncedText } from "../kit/SyncedText";

export type EnvelopeToSpamProps = {
  landFrame: number;
  label: string;
  fromSide: "left" | "right";
  tone: Tone;
};

export const envelopeToSpamDefaults: EnvelopeToSpamProps = { landFrame: 24, label: "Spam", fromSide: "left", tone: "danger" };

const entranceFrames = 12;

export const envelopeToSpamTimeline = (props: EnvelopeToSpamProps): Timeline & { land: number } => {
  const land = landFrameFor(props.landFrame, 1);
  return {
    land,
    events: [
      { id: "whoosh", frame: land - 1, kind: "whoosh" },
      { id: "land", frame: land, kind: "impact" },
    ],
  };
};

const envelopeScale = 0.7;
const body = { width: 3.2, height: 2.1, depth: 0.12, radius: 0.2 };
const folder = { x: 0.55, base: -1.15, width: 2.9, backHeight: 2.35, frontHeight: 1.55, gap: 0.36 };
const tray = { x: -1.5, y: 1.0, z: -0.7, width: 1.5, depth: 1.0, height: 0.34 };
const labelFont = 0.46;

const flapShape = (width: number, height: number) => {
  const shape = new THREE.Shape();
  shape.moveTo(-width / 2 + 0.12, height / 2 - 0.1);
  shape.lineTo(width / 2 - 0.12, height / 2 - 0.1);
  shape.lineTo(0, -0.12);
  shape.closePath();
  return shape;
};

const Envelope = ({ palette }: { palette: Palette }) => {
  const slab = useDisposable(() => roundedSlab(body.width, body.height, body.radius, { depth: body.depth, bevel: 0.05, bevelSegments: 4, curveSegments: 10 }), []);
  const flap = useDisposable(
    () =>
      new THREE.ExtrudeGeometry(flapShape(body.width, body.height), {
        depth: 0.02,
        bevelEnabled: true,
        bevelThickness: 0.015,
        bevelSize: 0.03,
        bevelSegments: 3,
      }),
    [],
  );
  const envelope = palette.three.envelope;
  return (
    <group>
      <mesh geometry={slab} castShadow receiveShadow>
        <meshStandardMaterial {...clay(palette, envelope.body)} />
      </mesh>
      <mesh geometry={flap} position={[0, 0, body.depth / 2 + 0.05]} castShadow receiveShadow>
        <meshStandardMaterial {...clay(palette, envelope.flap)} />
      </mesh>
      <mesh position={[0, -0.05, body.depth / 2 + 0.11]} rotation-x={Math.PI / 2} castShadow>
        <cylinderGeometry args={[0.22, 0.22, 0.05, 32]} />
        <meshStandardMaterial {...tile(palette, envelope.seal)} />
      </mesh>
    </group>
  );
};

const Folder = ({ palette, tone, label, labelWidth }: { palette: Palette; tone: Tone; label: string; labelWidth: number }) => {
  const back = useDisposable(() => roundedSlab(folder.width, folder.backHeight, 0.16, { depth: 0.08, bevel: 0.03 }), []);
  const tab = useDisposable(() => roundedSlab(1.1, 0.5, 0.14, { depth: 0.08, bevel: 0.03 }), []);
  const front = useDisposable(() => roundedSlab(folder.width + 0.1, folder.frontHeight, 0.16, { depth: 0.08, bevel: 0.03 }), []);
  const plateWidth = labelWidth * labelFont + 0.56;
  const plate = useDisposable(() => roundedSlab(plateWidth, 0.66, 0.14, { depth: 0.06, bevel: 0.02 }), [plateWidth]);
  const bottom = useDisposable(() => new THREE.BoxGeometry(folder.width, 0.08, folder.gap * 2), []);
  const slate = clay(palette, "muted");
  return (
    <group position={[folder.x, folder.base, 0]}>
      <mesh geometry={back} position={[0, folder.backHeight / 2, -folder.gap]} castShadow receiveShadow>
        <meshStandardMaterial {...slate} />
      </mesh>
      <mesh geometry={tab} position={[-folder.width / 2 + 0.62, folder.backHeight + 0.1, -folder.gap]} castShadow>
        <meshStandardMaterial {...slate} />
      </mesh>
      <mesh geometry={bottom} position={[0, 0.04, 0]} receiveShadow>
        <meshStandardMaterial {...slate} />
      </mesh>
      <group position={[0, 0, folder.gap]} rotation-x={deg(-7)}>
        <mesh geometry={front} position={[0, folder.frontHeight / 2, 0]} castShadow receiveShadow>
          <meshStandardMaterial {...slate} />
        </mesh>
        <mesh geometry={plate} position={[0, folder.frontHeight * 0.48, 0.08]} castShadow>
          <meshStandardMaterial {...tile(palette, palette.three.rim.meaning[tone])} />
        </mesh>
        <SyncedText
          font={palette.font(700)}
          fontSize={labelFont}
          color={palette.color("text")}
          position={[0, folder.frontHeight * 0.48 - 0.01, 0.18]}
          anchorX="center"
          anchorY="middle"
        >
          {label}
        </SyncedText>
      </group>
    </group>
  );
};

const Tray = ({ palette }: { palette: Palette }) => {
  const base = useDisposable(() => roundedSlab(tray.width, tray.depth, 0.12, { depth: 0.08, bevel: 0.02 }), []);
  const wall = useDisposable(() => new THREE.BoxGeometry(tray.width, tray.height, 0.08), []);
  const side = useDisposable(() => new THREE.BoxGeometry(0.08, tray.height, tray.depth), []);
  const material = tile(palette, "muted");
  return (
    <group position={[tray.x, tray.y, tray.z]} rotation-y={deg(18)} rotation-x={deg(16)}>
      <mesh geometry={base} rotation-x={-Math.PI / 2} castShadow receiveShadow>
        <meshStandardMaterial {...material} />
      </mesh>
      <mesh geometry={wall} position={[0, tray.height / 2, tray.depth / 2]} castShadow>
        <meshStandardMaterial {...material} />
      </mesh>
      <mesh geometry={wall} position={[0, tray.height / 2, -tray.depth / 2]} castShadow>
        <meshStandardMaterial {...material} />
      </mesh>
      <mesh geometry={side} position={[tray.width / 2, tray.height / 2, 0]} castShadow>
        <meshStandardMaterial {...material} />
      </mesh>
      <mesh geometry={side} position={[-tray.width / 2, tray.height / 2, 0]} castShadow>
        <meshStandardMaterial {...material} />
      </mesh>
    </group>
  );
};

const envelopePose = (frame: number, land: number, side: number) => {
  const start = new THREE.Vector3(-3.5 * side, 1.55, 0.1);
  const hover = new THREE.Vector3((tray.x + 0.1) * side, tray.y + 0.78, tray.z + 0.2);
  const rest = new THREE.Vector3(folder.x, folder.base + 1.62, -0.02);
  const enter = entrance(frame, 0, { frames: entranceFrames, turnDeg: 25 });
  if (frame <= entranceFrames) {
    const p = enter.p;
    return {
      position: new THREE.Vector3().lerpVectors(start, hover, p).add(new THREE.Vector3(0, 0.22 * Math.sin(Math.PI * p), 0)),
      rotation: new THREE.Euler(deg(6), enter.turn * side, deg(4) * side),
    };
  }
  const u = progress(frame, entranceFrames, land - entranceFrames);
  const x = hover.x + (rest.x - hover.x) * glide(u);
  const y = hover.y + 0.3 * Math.sin(Math.PI * u) * (1 - u) + (rest.y - hover.y) * u * u;
  const z = hover.z + (rest.z - hover.z) * arrive(u);
  return {
    position: new THREE.Vector3(x, y, z),
    rotation: new THREE.Euler(deg(6) - deg(4) * u, 0, deg(4) * side * (1 - u) - deg(5) * u),
  };
};

export const EnvelopeToSpam3D = (input: InsertProps<EnvelopeToSpamProps>) => {
  const frame = useCurrentFrame();
  const props = resolveBeatProps("EnvelopeToSpam3D", envelopeToSpamDefaults, input.beatProps);
  const palette = useMemo(() => makePalette(input.brand, input.assetBase), [input.brand, input.assetBase]);
  const widths = useTextWidths(palette.font(700), [props.label]);
  const { land } = envelopeToSpamTimeline(props);
  const side = props.fromSide === "left" ? 1 : -1;
  const pose = envelopePose(frame, land, side);
  const landed = progress(frame, land, 3);
  const shift = kickOffset(frame, land);
  const sway = holdSway(frame, land, 1.4, 64);
  return (
    <AbsoluteFill>
      {widths ? (
        <Scene3D palette={palette}>
          <Backdrop palette={palette} spot={[530, 720]} />
          <CameraRig palette={palette} position={[0, 3.2, 19.5]} target={[0, 0.2, 0]} principal={[530, 700]} shiftPx={shift} dolly={creep(frame, 0)} />
          <Lights palette={palette} tone={props.tone} rimScale={0.55 + 0.45 * landed} />
          <group rotation-y={sway} scale-x={side}>
            <Tray palette={palette} />
          </group>
          <group rotation-y={sway}>
            <Folder palette={palette} tone={props.tone} label={props.label} labelWidth={widths[0] ?? 2} />
            <group position={pose.position} rotation={pose.rotation} scale={envelopeScale}>
              <Envelope palette={palette} />
            </group>
            <BaseGlow palette={palette} color={palette.three.rim.meaning[props.tone]} radius={2.3} position={[folder.x, folder.base + 0.01, 0]} strength={0.5 + 0.5 * landed} />
          </group>
          <ShadowCatcher palette={palette} y={folder.base} />
        </Scene3D>
      ) : null}
    </AbsoluteFill>
  );
};
