import { Easing, interpolate } from "remotion";
import { colors, motion, surface } from "../../../theme";
import type { BeatContext } from "../../../types";
import { entranceProgress } from "../../ui";

export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const easeInOutCubic = Easing.bezier(0.65, 0, 0.35, 1);
export const easeInQuad = Easing.bezier(0.11, 0, 0.5, 0);
export const easeOutCubic = Easing.bezier(0.33, 1, 0.68, 1);

export const relFrame = (context: Pick<BeatContext, "beat" | "toFrame">, relativeSec: number) =>
  context.toFrame(context.beat.from + relativeSec);

export const ramp = (frame: number, start: number, frames: number, easing: (t: number) => number = motion.ease) =>
  interpolate(frame, [start, start + Math.max(1, frames)], [0, 1], { ...clamp, easing });

export const arrive = (frame: number, start: number) => {
  const progress = entranceProgress(frame, start);
  return {
    progress,
    opacity: interpolate(frame, [start, start + 3], [0, 1], clamp),
    scale: 1 + (1 - progress) * (motion.arriveFromScale - 1),
    rise: Math.round((1 - progress) * motion.arriveFromOffsetPx),
  };
};

export const leave = (frame: number, durationInFrames: number, enabled: boolean, distancePx = 24) => {
  if (!enabled) {
    return { opacity: 1, y: 0 };
  }
  const last = durationInFrames - 1;
  const progress = interpolate(frame, [last - motion.exitFrames, last], [0, 1], { ...clamp, easing: easeInOutCubic });
  return { opacity: 1 - progress, y: Math.round(progress * distancePx) };
};

export const rgba = (hex: string, alpha: number) => {
  const value = Number.parseInt(hex.replace("#", ""), 16);
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`;
};

export const capsEm = (word: string) =>
  Array.from(word).reduce(
    (sum, char) => sum + (char === " " ? 0.3 : /[IJ1.,':]/.test(char) ? 0.36 : /[MW]/.test(char) ? 0.98 : /[a-z]/.test(char) ? 0.62 : 0.76),
    0,
  );

export const fitFontPx = (words: string[], widthPx: number, maxPx: number, minPx: number) => {
  const widest = Math.max(...words.map(capsEm), 1);
  return Math.max(minPx, Math.min(maxPx, Math.floor(widthPx / widest)));
};

export const panelSurface = {
  background: `linear-gradient(180deg, ${colors.navyTile} 0%, ${colors.navyPanel} 100%)`,
  border: `1px solid ${rgba(colors.muted, 0.24)}`,
  highlight: "inset 0 1px 0 rgba(255,255,255,0.08)",
  shadow: surface.cardShadow,
};

export type Point = { x: number; y: number };

export const quadPoint = (p0: Point, control: Point, p1: Point, t: number): Point => {
  const u = 1 - t;
  return {
    x: u * u * p0.x + 2 * u * t * control.x + t * t * p1.x,
    y: u * u * p0.y + 2 * u * t * control.y + t * t * p1.y,
  };
};
