import { camera as cameraTokens, layout } from "../theme";
import type { CameraKey, CueSegment, Cues, FaceBox } from "../types";

export type CameraState = { scale: number; tx: number; ty: number };

export type CameraTransform = CameraState & { rotateDeg: number };

export type KickOffset = { x: number; y: number; rollDeg: number };

type Point = { x: number; y: number };

const identity: CameraState = { scale: 1, tx: 0, ty: 0 };

const noKick: KickOffset = { x: 0, y: 0, rollDeg: 0 };

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const mix = (from: CameraState, to: CameraState, progress: number): CameraState => ({
  scale: from.scale + (to.scale - from.scale) * progress,
  tx: from.tx + (to.tx - from.tx) * progress,
  ty: from.ty + (to.ty - from.ty) * progress,
});

const keyFrame = (t: number, fps: number) => Math.round(t * fps);

export const smootherstep = (u: number) => {
  const x = clamp(u, 0, 1);
  return x * x * x * (x * (6 * x - 15) + 10);
};

export const glideFramesOf = (key: Pick<CameraKey, "frames">) =>
  clamp(Math.round(key.frames ?? cameraTokens.glideFrames), cameraTokens.glideFramesMin, cameraTokens.glideFramesMax);

export const kickFramesOf = (key: Pick<CameraKey, "frames">) => Math.max(2, Math.round(key.frames ?? cameraTokens.kickFrames));

export const keyStartFrame = (key: CameraKey, fps: number) =>
  key.ease === "glide" ? Math.round(key.t * fps - glideFramesOf(key) / 2) : keyFrame(key.t, fps);

const progressOf = (key: CameraKey, frame: number, fps: number, nextKeyFrame: number) => {
  const startFrame = keyStartFrame(key, fps);
  switch (key.ease) {
    case "cut":
      return 1;
    case "hold":
    case "kick":
      return 0;
    case "push":
      return cameraTokens.pushEase(clamp((frame - startFrame) / cameraTokens.pushFrames, 0, 1));
    case "glide":
      return smootherstep((frame - startFrame) / glideFramesOf(key));
    case "creep": {
      const span = Math.max(1, nextKeyFrame - startFrame);
      return cameraTokens.creepEase(clamp((frame - startFrame) / span, 0, 1));
    }
  }
};

export const sortCameraKeys = (keys: CameraKey[], fps: number) =>
  keys
    .filter((key) => key.ease !== "kick")
    .sort((a, b) => keyStartFrame(a, fps) - keyStartFrame(b, fps) || a.t - b.t);

export const kickKeys = (keys: CameraKey[]) => keys.filter((key) => key.ease === "kick").sort((a, b) => a.t - b.t);

export const sampleCamera = (sortedKeys: CameraKey[], frame: number, fps: number, totalFrames: number): CameraState => {
  const first = sortedKeys[0];
  if (!first) {
    return identity;
  }
  let segmentStart: CameraState = { scale: first.scale, tx: first.tx, ty: first.ty };
  let current = segmentStart;
  for (let index = 0; index < sortedKeys.length; index++) {
    const key = sortedKeys[index]!;
    const startFrame = keyStartFrame(key, fps);
    if (startFrame > frame) {
      break;
    }
    const next = sortedKeys[index + 1];
    const nextKeyFrame = next ? keyStartFrame(next, fps) : totalFrames;
    const target: CameraState = { scale: key.scale, tx: key.tx, ty: key.ty };
    const evaluateAt = Math.min(frame, nextKeyFrame);
    current = mix(segmentStart, target, progressOf(key, evaluateAt, fps, nextKeyFrame));
    segmentStart = current;
  }
  return current;
};

export const kickSignal = (n: number, frames: number) => (n % 2 === 0 ? 1 : -1) * Math.pow(Math.max(0, 1 - n / frames), 1.5);

export const kickOffsetAt = (kicks: CameraKey[], frame: number, fps: number): KickOffset => {
  let offset = noKick;
  for (const key of kicks) {
    const frames = kickFramesOf(key);
    const n = frame - keyFrame(key.t, fps);
    if (n < 0 || n >= frames) {
      continue;
    }
    const signal = kickSignal(n, frames);
    const px = key.px ?? cameraTokens.kickPx;
    const angle = ((key.angleDeg ?? cameraTokens.kickAngleDeg) * Math.PI) / 180;
    offset = {
      x: offset.x + px * signal * Math.cos(angle),
      y: offset.y + px * signal * Math.sin(angle),
      rollDeg: offset.rollDeg + (key.rollDeg ?? cameraTokens.kickRollDeg) * signal,
    };
  }
  return offset;
};

export type Shot = { startFrame: number; endFrame: number; face: FaceBox | null };

export const buildShots = (cues: Cues, fps: number, totalFrames: number): Shot[] => {
  const boundaries = [...new Set([0, ...cues.cuts.map((cut) => keyFrame(cut, fps)), totalFrames])]
    .filter((frame) => frame >= 0 && frame <= totalFrames)
    .sort((a, b) => a - b);
  return boundaries.slice(0, -1).map((startFrame, index) => {
    const endFrame = boundaries[index + 1]!;
    const overlap = (segment: CueSegment) =>
      Math.min(endFrame, keyFrame(segment.end, fps)) - Math.max(startFrame, keyFrame(segment.start, fps));
    const main = cues.segments
      .filter((segment) => segment.face && overlap(segment) > 0)
      .sort((a, b) => overlap(b) - overlap(a))[0];
    return { startFrame, endFrame, face: main?.face ?? null };
  });
};

export const shotAtFrame = (shots: Shot[], frame: number) =>
  shots.find((shot) => frame >= shot.startFrame && frame < shot.endFrame) ?? shots[shots.length - 1];

export const resolveTransform = (state: CameraState, origin: Point, maxScale: number = cameraTokens.maxScale): CameraState => {
  const scale = clamp(state.scale, cameraTokens.minScale, maxScale);
  const extra = scale - 1;
  const tx = clamp(state.tx, -extra * (layout.width - origin.x), extra * origin.x);
  const ty = clamp(state.ty, -extra * (layout.height - origin.y), extra * origin.y);
  return { scale, tx, ty };
};

const viewportCorners: Point[] = [
  { x: 0, y: 0 },
  { x: layout.width, y: 0 },
  { x: 0, y: layout.height },
  { x: layout.width, y: layout.height },
];

export const coversFrame = (transform: CameraTransform, origin: Point) => {
  const radians = (-transform.rotateDeg * Math.PI) / 180;
  const cos = Math.cos(radians);
  const sin = Math.sin(radians);
  const tolerance = 1e-6;
  return viewportCorners.every((corner) => {
    const dx = corner.x - origin.x - transform.tx;
    const dy = corner.y - origin.y - transform.ty;
    const x = origin.x + (dx * cos - dy * sin) / transform.scale;
    const y = origin.y + (dx * sin + dy * cos) / transform.scale;
    return x >= -tolerance && x <= layout.width + tolerance && y >= -tolerance && y <= layout.height + tolerance;
  });
};

const withKick = (base: CameraState, kick: KickOffset, amount: number, scale: number): CameraTransform => ({
  scale,
  tx: base.tx + kick.x * amount,
  ty: base.ty + kick.y * amount,
  rotateDeg: kick.rollDeg * amount,
});

const searchSteps = 24;

export const rollCoverScale = (rollDeg: number) => {
  const radians = (Math.abs(rollDeg) * Math.PI) / 180;
  return Math.cos(radians) + (layout.height / layout.width) * Math.sin(radians);
};

export const applyKick = (base: CameraState, kick: KickOffset, origin: Point, maxScale: number = cameraTokens.maxScale): CameraTransform => {
  if (kick.x === 0 && kick.y === 0 && kick.rollDeg === 0) {
    return { ...base, rotateDeg: 0 };
  }
  if (coversFrame(withKick(base, kick, 1, base.scale), origin)) {
    return withKick(base, kick, 1, base.scale);
  }
  const edgeDistance = Math.max(1, Math.min(origin.x, layout.width - origin.x, origin.y, layout.height - origin.y));
  const reach = Math.max(...viewportCorners.map((corner) => Math.hypot(corner.x - origin.x, corner.y - origin.y)));
  const rollRadians = (Math.abs(kick.rollDeg) * Math.PI) / 180;
  const headroomScale = base.scale * rollCoverScale(kick.rollDeg) + (Math.hypot(kick.x, kick.y) + reach * Math.sin(rollRadians)) / edgeDistance;
  const ceiling = Math.max(base.scale, Math.min(maxScale, headroomScale));
  if (coversFrame(withKick(base, kick, 1, ceiling), origin)) {
    let low = base.scale;
    let high = ceiling;
    for (let step = 0; step < searchSteps; step++) {
      const middle = (low + high) / 2;
      if (coversFrame(withKick(base, kick, 1, middle), origin)) {
        high = middle;
      } else {
        low = middle;
      }
    }
    return withKick(base, kick, 1, high);
  }
  let low = 0;
  let high = 1;
  for (let step = 0; step < searchSteps; step++) {
    const middle = (low + high) / 2;
    if (coversFrame(withKick(base, kick, middle, ceiling), origin)) {
      low = middle;
    } else {
      high = middle;
    }
  }
  return withKick(base, kick, low, ceiling);
};
