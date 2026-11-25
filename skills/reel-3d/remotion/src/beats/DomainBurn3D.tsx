import { useMemo } from "react";
import * as THREE from "three";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { useTextWidths } from "../kit/assets";
import { Backdrop, ShadowCatcher } from "../kit/Backdrop";
import { BaseGlow } from "../kit/BaseGlow";
import { hexToRgb, makePalette, type Palette, type Tone } from "../kit/brand";
import { CameraRig } from "../kit/CameraRig";
import { roundedSlab, useDisposable } from "../kit/geometry";
import type { InsertProps, Timeline } from "../kit/insert";
import { resolveBeatProps } from "../kit/insert";
import { Lights } from "../kit/Lights";
import { clay, glowTexture, glsl, patchStandard } from "../kit/materials";
import { arrive, creep, deg, entrance, glide, holdSway, kickOffset, landFrameFor, progress } from "../kit/motion";
import { hash01, range } from "../kit/random";
import { Scene3D } from "../kit/Scene3D";
import { SyncedText } from "../kit/SyncedText";

export type DomainBurnProps = {
  burnFrame: number;
  domain: string;
  tone: Tone;
  seed: number;
};

export const domainBurnDefaults: DomainBurnProps = { burnFrame: 14, domain: "yourbrand.com", tone: "danger", seed: 7 };

const spreadFrames = 18;
const entranceFrames = 12;
const entranceLead = 3;

export const domainBurnTimeline = (props: DomainBurnProps): Timeline & { land: number } => {
  const land = landFrameFor(props.burnFrame, 1);
  return {
    land,
    events: [
      { id: "ignite", frame: land - 1, kind: "whoosh" },
      { id: "burn", frame: land, kind: "impact" },
    ],
  };
};

const block = { width: 6.9, height: 1.7, depth: 0.5, radius: 0.32, y: -0.42 };
const cameraDistance = 5.6;
const maxLabelFont = 0.78;
const labelMaxWidth = 5.9;

const srgb = (hex: string) => {
  const [r, g, b] = hexToRgb(hex);
  return new THREE.Vector3(r / 255, g / 255, b / 255);
};

const useBurnMaterial = (palette: Palette) => {
  const uniforms = useMemo(
    () => ({
      uFront: { value: -10 },
      uHeat: { value: 0 },
      uTime: { value: 0 },
      uChar: { value: new THREE.Color(palette.color(palette.three.burnt)) },
      uEdge: { value: new THREE.Color(palette.color("accent")) },
    }),
    [palette],
  );
  const material = useDisposable(() => {
    const base = new THREE.MeshStandardMaterial(clay(palette, "border"));
    return patchStandard(
      base,
      {
        uniforms,
        vertexHead: "varying vec3 vR3dLocal;",
        vertexBody: "vR3dLocal = position;",
        fragmentHead: `varying vec3 vR3dLocal;\nuniform float uFront;\nuniform float uHeat;\nuniform float uTime;\nuniform vec3 uChar;\nuniform vec3 uEdge;\n${glsl.noise}`,
        afterColor: [
          "float r3dN = r3dFbm(vR3dLocal.xy * 1.7 + vec2(3.1, 7.7));",
          "float r3dD = vR3dLocal.x + (r3dN - 0.5) * 1.1 - uFront;",
          "float r3dBurnt = smoothstep(0.2, -0.3, r3dD);",
          "diffuseColor.rgb = mix(diffuseColor.rgb, uChar * 0.8, r3dBurnt);",
        ].join("\n"),
        afterEmissive: [
          "float r3dBand = exp(-pow(r3dD / 0.17, 2.0)) * uHeat;",
          "float r3dGrain = smoothstep(0.66, 0.92, r3dFbm(vR3dLocal.xy * 4.2 + vec2(uTime * 0.6, -uTime * 1.4)));",
          "totalEmissiveRadiance = mix(totalEmissiveRadiance, uChar * 0.05, r3dBurnt) + uEdge * (r3dBand * 2.4 + r3dBurnt * r3dGrain * uHeat * 0.4);",
        ].join("\n"),
      },
      "reel3d-burn",
    );
  }, [palette, uniforms]);
  return { material, uniforms };
};

const flameVertex = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const flameFragment = `
varying vec2 vUv;
uniform float uTime;
uniform float uAmount;
uniform float uSeed;
uniform vec3 uOuter;
uniform vec3 uMid;
uniform vec3 uCore;
${glsl.noise}
void main() {
  vec2 uv = vUv;
  float n = r3dFbm(vec2(uv.x * 3.2 + uSeed, uv.y * 2.6 - uTime * 2.8));
  float sway = (r3dNoise(vec2(uSeed, uv.y * 1.5 - uTime * 1.6)) - 0.5) * 0.28 * uv.y;
  float dx = abs(uv.x - 0.5 - sway) * 2.0;
  float shape = pow(max(0.0, 1.0 - uv.y), 0.8) * max(0.0, 1.0 - pow(dx, 1.5));
  float flame = smoothstep(0.18, 0.7, shape * (0.55 + n * 0.95) * uAmount);
  vec3 color = mix(uOuter, uMid, smoothstep(0.25, 0.6, flame));
  color = mix(color, uCore, smoothstep(0.84, 1.0, flame));
  gl_FragColor = vec4(color * flame, flame);
}
`;

type Flame = { x: number; width: number; height: number; ignite: number; seed: number };

const Flames = ({ palette, flames, frame, fps, fade }: { palette: Palette; flames: Flame[]; frame: number; fps: number; fade: number }) => {
  const materials = useDisposable(() => {
    const list = flames.map(
      (flame) =>
        new THREE.ShaderMaterial({
          vertexShader: flameVertex,
          fragmentShader: flameFragment,
          uniforms: {
            uTime: { value: 0 },
            uAmount: { value: 0 },
            uSeed: { value: flame.seed },
            uOuter: { value: srgb(palette.color("danger")) },
            uMid: { value: srgb(palette.color("accent")) },
            uCore: { value: srgb(palette.color("warning")) },
          },
          transparent: true,
          depthWrite: false,
          blending: THREE.AdditiveBlending,
          toneMapped: false,
        }),
    );
    return { list, dispose: () => list.forEach((m) => m.dispose()) };
  }, [flames, palette]);
  const geometry = useDisposable(() => new THREE.PlaneGeometry(1, 1, 1, 1), []);
  return (
    <>
      {flames.map((flame, index) => {
        const material = materials.list[index];
        if (!material) {
          return null;
        }
        const amount = glide(progress(frame, flame.ignite, 6)) * fade;
        const uTime = material.uniforms.uTime;
        const uAmount = material.uniforms.uAmount;
        if (uTime && uAmount) {
          uTime.value = frame / fps + flame.seed;
          uAmount.value = amount;
        }
        return (
          <mesh
            key={flame.seed}
            geometry={geometry}
            material={material}
            visible={amount > 0}
            position={[flame.x, block.y + block.height / 2 + flame.height * 0.42 - 0.12, block.depth / 2 + 0.05]}
            scale={[flame.width, flame.height, 1]}
            renderOrder={2}
          />
        );
      })}
    </>
  );
};

const emberCount = 30;

const Embers = ({ palette, frame, land, seed, front }: { palette: Palette; frame: number; land: number; seed: number; front: (f: number) => number }) => {
  const texture = useDisposable(() => glowTexture(64, [1, 0.8, 0.3, 0]), []);
  const geometry = useDisposable(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(emberCount * 3), 3));
    g.setAttribute("color", new THREE.BufferAttribute(new Float32Array(emberCount * 3), 3));
    return g;
  }, []);
  const hot = new THREE.Color(palette.color("warning"));
  const warm = new THREE.Color(palette.color("accent"));
  const position = geometry.getAttribute("position");
  const color = geometry.getAttribute("color");
  for (let i = 0; i < emberCount; i += 1) {
    const birth = land + Math.floor(range(i, seed, 0, spreadFrames + 12));
    const life = Math.floor(range(i, seed + 1, 12, 22));
    const age = frame - birth;
    const alive = age >= 0 && age < life;
    const t = alive ? age / life : 0;
    const x0 = Math.min(front(birth), block.width / 2 - 0.2) - range(i, seed + 2, 0, 1.6);
    const x = x0 + 0.18 * Math.sin(t * 5 + i);
    const y = block.y + block.height / 2 + t * range(i, seed + 3, 0.7, 1.4);
    const z = block.depth / 2 + range(i, seed + 4, -0.1, 0.4);
    position.setXYZ(i, x, y, alive ? z : -50);
    const heat = (1 - t) * (alive ? 1 : 0);
    const mixed = warm.clone().lerp(hot, hash01(i, seed + 5));
    color.setXYZ(i, mixed.r * heat, mixed.g * heat, mixed.b * heat);
  }
  position.needsUpdate = true;
  color.needsUpdate = true;
  return (
    <points geometry={geometry} renderOrder={3}>
      <pointsMaterial
        map={texture}
        size={9}
        sizeAttenuation={false}
        vertexColors
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        toneMapped={false}
      />
    </points>
  );
};

export const DomainBurn3D = (input: InsertProps<DomainBurnProps>) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const props = resolveBeatProps("DomainBurn3D", domainBurnDefaults, input.beatProps);
  const palette = useMemo(() => makePalette(input.brand, input.assetBase), [input.brand, input.assetBase]);
  const widths = useTextWidths(palette.font(700), [props.domain]);
  const { land } = domainBurnTimeline(props);
  const { material, uniforms } = useBurnMaterial(palette);
  const slab = useDisposable(() => roundedSlab(block.width, block.height, block.radius, { depth: block.depth, bevel: 0.06, bevelSegments: 5 }), []);
  const left = -block.width / 2 - 0.6;
  const right = block.width / 2 + 0.9;
  const front = (f: number) => left + (right - left) * glide(progress(f, land, spreadFrames));
  const flames = useMemo<Flame[]>(() => {
    const count = 6 + Math.floor(hash01(0, props.seed) * 5);
    return Array.from({ length: count }, (_, i) => {
      const x = -block.width / 2 + 0.5 + ((block.width - 1.0) * (i + range(i, props.seed + 9, 0.2, 0.8))) / count;
      const share = (x - left) / (right - left);
      return {
        x,
        width: range(i, props.seed + 10, 0.8, 1.2),
        height: range(i, props.seed + 11, 0.85, 1.2),
        ignite: land + Math.round(share * spreadFrames * 0.9),
        seed: range(i, props.seed + 12, 0, 40),
      };
    });
  }, [props.seed, land, left, right]);
  const enter = entrance(frame, -entranceLead, { frames: entranceFrames, turnDeg: 20 });
  const slideX = (1 - enter.p) * 0.55;
  uniforms.uFront.value = front(frame);
  uniforms.uHeat.value = glide(progress(frame, land, 4));
  uniforms.uTime.value = frame / fps;
  const burnt = glide(progress(frame, land, spreadFrames));
  const fade = 1 - 0.35 * glide(progress(frame, land + spreadFrames + 4, durationInFrames - land - spreadFrames - 4));
  const labelWidth = widths?.[0] ?? 1;
  const labelFont = Math.min(maxLabelFont, labelMaxWidth / labelWidth);
  const textColor = new THREE.Color(palette.color("text")).lerp(new THREE.Color(palette.color("muted")), burnt * 0.35);
  const sway = holdSway(frame, entranceFrames, 1.2, 70);
  return (
    <AbsoluteFill>
      {widths ? (
        <Scene3D palette={palette}>
          <Backdrop palette={palette} spot={[width / 2, height * 0.55]} />
          <CameraRig
            palette={palette}
            position={[0, 0.9, cameraDistance]}
            target={[0, 0, 0]}
            principal={[width / 2, height / 2 + 6]}
            shiftPx={kickOffset(frame, land)}
            dolly={creep(frame, 0, 0.0015)}
          />
          <Lights palette={palette} tone={props.tone} rimScale={0.6 + 0.4 * burnt} />
          <group position-x={slideX} rotation-y={-enter.turn + sway} rotation-x={deg(-4) * (1 - enter.p)}>
            <mesh geometry={slab} material={material} position-y={block.y} castShadow receiveShadow />
            <SyncedText
              font={palette.font(700)}
              fontSize={labelFont}
              color={`#${textColor.getHexString()}`}
              position={[0, block.y - 0.02, block.depth / 2 + 0.07]}
              anchorX="center"
              anchorY="middle"
            >
              {props.domain}
            </SyncedText>
            <Flames palette={palette} flames={flames} frame={frame} fps={fps} fade={fade} />
            <Embers palette={palette} frame={frame} land={land} seed={props.seed} front={front} />
            <BaseGlow
              palette={palette}
              color={palette.three.rim.meaning[props.tone]}
              radius={4.2}
              position={[0, block.y - block.height / 2 + 0.005, 0]}
              strength={arrive(progress(frame, land, 6))}
            />
          </group>
          <ShadowCatcher palette={palette} y={block.y - block.height / 2} />
        </Scene3D>
      ) : null}
    </AbsoluteFill>
  );
};

