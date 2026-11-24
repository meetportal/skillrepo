import { camera as cameraTokens, layout } from "../theme";
import type { CameraKey, CueSegment, Cues, FaceBox } from "../types";

export type CameraState = { scale: number; tx: number; ty: number };

const identity: CameraState = { scale: 1, tx: 0, ty: 0 };

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const mix = (from: CameraState, to: CameraState, progress: number): CameraState => ({
  scale: from.scale + (to.scale - from.scale) * progress,
  tx: from.tx + (to.tx - from.tx) * progress,
  ty: from.ty + (to.ty - from.ty) * progress,
});

const keyFrame = (t: number, fps: number) => Math.round(t * fps);

const progressOf = (key: CameraKey, frame: number, fps: number, nextKeyFrame: number) => {
  const startFrame = keyFrame(key.t, fps);
  if (key.ease === "cut") {
    return 1;
  }
  if (key.ease === "hold") {
    return 0;
  }
  if (key.ease === "push") {
    return cameraTokens.pushEase(clamp((frame - startFrame) / cameraTokens.pushFrames, 0, 1));
  }
  const span = Math.max(1, nextKeyFrame - startFrame);
  return cameraTokens.creepEase(clamp((frame - startFrame) / span, 0, 1));
};

export const sortCameraKeys = (keys: CameraKey[]) => [...keys].sort((a, b) => a.t - b.t);

export const sampleCamera = (sortedKeys: CameraKey[], frame: number, fps: number, totalFrames: number): CameraState => {
  const first = sortedKeys[0];
  if (!first) {
    return identity;
  }
  let segmentStart: CameraState = { scale: first.scale, tx: first.tx, ty: first.ty };
  let current = segmentStart;
  for (let index = 0; index < sortedKeys.length; index++) {
    const key = sortedKeys[index]!;
    const startFrame = keyFrame(key.t, fps);
    if (startFrame > frame) {
      break;
    }
    const next = sortedKeys[index + 1];
    const nextKeyFrame = next ? keyFrame(next.t, fps) : totalFrames;
    const target: CameraState = { scale: key.scale, tx: key.tx, ty: key.ty };
    const evaluateAt = Math.min(frame, nextKeyFrame);
    current = mix(segmentStart, target, progressOf(key, evaluateAt, fps, nextKeyFrame));
    segmentStart = current;
  }
  return current;
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

export const resolveTransform = (state: CameraState, origin: { x: number; y: number }) => {
  const scale = clamp(state.scale, cameraTokens.minScale, cameraTokens.maxScale);
  const extra = scale - 1;
  const tx = clamp(state.tx, -extra * (layout.width - origin.x), extra * origin.x);
  const ty = clamp(state.ty, -extra * (layout.height - origin.y), extra * origin.y);
  return { scale, tx, ty };
};
