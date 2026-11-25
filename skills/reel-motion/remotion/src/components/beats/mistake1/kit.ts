import { Easing, interpolate } from "remotion";
import { motion } from "../../../theme";
import type { BeatContext } from "../../../types";
import { entranceProgress, exitProgress } from "../../ui";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const fadeInFrames = 4;

export const relFrame = (context: Pick<BeatContext, "beat" | "toFrame">, relativeSec: number) => context.toFrame(relativeSec);

export const riseIn = (frame: number, start: number, distancePx = motion.arriveFromOffsetPx) => {
  const progress = entranceProgress(frame, start);
  return {
    progress,
    opacity: interpolate(frame + 1, [start, start + fadeInFrames], [0, 1], clamp),
    y: Math.round((1 - progress) * distancePx),
  };
};

export const sinkOut = (frame: number, durationInFrames: number, distancePx = 24) => {
  const progress = exitProgress(frame, durationInFrames);
  const fade = interpolate(frame, [durationInFrames - motion.exitFrames, durationInFrames], [0, 1], { ...clamp, easing: Easing.in(Easing.quad) });
  return { progress, opacity: 1 - fade, y: Math.round(progress * distancePx) };
};

export const drawOn = (frame: number, start: number, frames = motion.entranceFrames) =>
  interpolate(frame, [start, start + frames], [0, 1], { ...clamp, easing: motion.ease });

export const dashStyle = (progress: number, length = 100) => ({
  strokeDasharray: `${length} ${length}`,
  strokeDashoffset: length * (1 - progress),
});

export const seeded = (seed: number) => {
  let state = (seed * 2654435761) >>> 0 || 1;
  return () => {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return ((state >>> 0) % 10000) / 10000;
  };
};
