import { Easing, interpolate, useCurrentFrame } from "remotion";
import { motion } from "../../theme";

export type EntranceFrom = "scale" | "up" | "down" | "left" | "right" | "none";

export type MotionStyle = { opacity: number; transform: string };

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const staggerStart = (start: number, index: number) => start + index * motion.staggerFrames;

export const entranceProgress = (frame: number, start = 0, frames = motion.entranceFrames) =>
  interpolate(frame, [start, start + frames], [0, 1], { ...clamp, easing: motion.ease });

export const exitProgress = (frame: number, endFrame: number, frames = motion.exitFrames) =>
  interpolate(frame, [endFrame - frames, endFrame], [0, 1], { ...clamp, easing: motion.exitEase });

const offsetTransform = (from: EntranceFrom, amount: number) => {
  switch (from) {
    case "up":
      return `translateY(${amount * motion.arriveFromOffsetPx}px)`;
    case "down":
      return `translateY(${-amount * motion.arriveFromOffsetPx}px)`;
    case "left":
      return `translateX(${amount * motion.arriveFromOffsetPx}px)`;
    case "right":
      return `translateX(${-amount * motion.arriveFromOffsetPx}px)`;
    case "scale":
      return `scale(${1 + amount * (motion.arriveFromScale - 1)})`;
    case "none":
      return "none";
  }
};

export const entranceStyle = (frame: number, { start = 0, from = "scale" as EntranceFrom, index = 0 } = {}): MotionStyle => {
  const progress = entranceProgress(frame, staggerStart(start, index));
  return {
    opacity: interpolate(progress, [0, 0.45], [0, 1], clamp),
    transform: offsetTransform(from, 1 - progress),
  };
};

export const exitStyle = (frame: number, endFrame: number, { to = "scale" as EntranceFrom } = {}): MotionStyle => {
  const progress = exitProgress(frame, endFrame);
  const transform =
    to === "scale" ? `scale(${1 - progress * 0.04})` : to === "none" ? "none" : offsetTransform(to, progress * 0.6);
  return { opacity: 1 - progress, transform };
};

export const combineMotion = (...styles: MotionStyle[]): MotionStyle => ({
  opacity: styles.reduce((value, style) => value * style.opacity, 1),
  transform: styles.map((style) => style.transform).filter((value) => value !== "none").join(" ") || "none",
});

export const enterExitStyle = (
  frame: number,
  durationInFrames: number,
  { start = 0, from = "scale" as EntranceFrom, index = 0, exit = true, exitTo = "scale" as EntranceFrom } = {},
): MotionStyle =>
  combineMotion(entranceStyle(frame, { start, from, index }), exit ? exitStyle(frame, durationInFrames, { to: exitTo }) : { opacity: 1, transform: "none" });

export const useEntrance = (options: { start?: number; from?: EntranceFrom; index?: number } = {}) =>
  entranceStyle(useCurrentFrame(), options);

export const useExit = (durationInFrames: number, options: { to?: EntranceFrom } = {}) =>
  exitStyle(useCurrentFrame(), durationInFrames, options);

export const useEnterExit = (
  durationInFrames: number,
  options: { start?: number; from?: EntranceFrom; index?: number; exit?: boolean; exitTo?: EntranceFrom } = {},
) => enterExitStyle(useCurrentFrame(), durationInFrames, options);

export const stampScale = (frame: number, start: number) =>
  interpolate(
    frame,
    [start, start + motion.stampFrames - 2, start + motion.stampFrames],
    [motion.stampFromScale, 1 - motion.overshootMaxRatio / 2, 1],
    { ...clamp, easing: Easing.bezier(0.33, 1, 0.68, 1) },
  );

export const stampStyle = (frame: number, start: number, rotateDeg = 0): MotionStyle => ({
  opacity: interpolate(frame, [start, start + 2], [0, 1], clamp),
  transform: `rotate(${rotateDeg}deg) scale(${stampScale(frame, start)})`,
});

export const useStamp = (start: number, rotateDeg = 0) => stampStyle(useCurrentFrame(), start, rotateDeg);

export const shakeOffset = (frame: number, start: number, frames = 2, amplitudePx = 4) => {
  const local = frame - start;
  if (local < 0 || local >= frames) {
    return { x: 0, y: 0 };
  }
  const direction = local % 2 === 0 ? 1 : -1;
  return { x: direction * amplitudePx, y: -direction * amplitudePx * 0.5 };
};

export const holdFramesFor = (words: number, fps: number) => Math.ceil((words * motion.holdPerWordSec + motion.holdBaseSec) * fps);
