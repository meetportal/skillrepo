import type { CSSProperties } from "react";
import { interpolate } from "remotion";
import { colors, motion, surface } from "../../../theme";
import { entranceProgress, exitProgress } from "../../ui";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const secToFrame = (sec: number, fps: number) => Math.round(sec * fps);

export const hexAlpha = (hex: string, alpha: number) => {
  const value = Number.parseInt(hex.replace("#", ""), 16);
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`;
};

export const panelStyle: CSSProperties = {
  boxSizing: "border-box",
  background: `linear-gradient(180deg, ${colors.navyTop} 0%, ${colors.navyBottom} 100%)`,
  border: `1px solid ${hexAlpha(colors.muted, 0.22)}`,
  borderRadius: surface.cardRadius,
  boxShadow: `inset 0 1px 0 rgba(255,255,255,0.07), ${surface.cardShadow}`,
  overflow: "hidden",
};

export const sheenStyle: CSSProperties = {
  position: "absolute",
  inset: 0,
  background: "radial-gradient(120% 80% at 18% 0%, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0) 55%)",
  pointerEvents: "none",
};

export type Arrival = { opacity: number; dx: number; dy: number; scale: number };

export const arrival = (
  frame: number,
  durationInFrames: number,
  { start = 0, from = "up" as "up" | "left" | "none", exit = true } = {},
): Arrival => {
  const enter = entranceProgress(frame, start);
  const leave = exit ? exitProgress(frame, durationInFrames) : 0;
  const offset = Math.round((1 - enter) * motion.arriveFromOffsetPx);
  return {
    opacity: interpolate(enter, [0, 0.45], [0, 1], clamp) * (1 - leave),
    dx: from === "left" ? offset : 0,
    dy: from === "up" ? offset + Math.round(leave * 16) : Math.round(leave * 16),
    scale: 1,
  };
};

export const arrivalTransform = (value: Arrival, extraX = 0, extraY = 0) =>
  `translate(${value.dx + extraX}px, ${value.dy + extraY}px)`;

export const estimateCapsEm = (word: string) =>
  Array.from(word).reduce((sum, char) => sum + (char === " " ? 0.28 : /[IJ1.,']/.test(char) ? 0.34 : /[MW]/.test(char) ? 0.98 : 0.72), 0);

export const fitWordFontPx = (words: string[], widthPx: number, maxPx: number, minPx: number) => {
  const widestEm = Math.max(...words.map(estimateCapsEm), 1);
  return Math.max(minPx, Math.min(maxPx, Math.floor(widthPx / widestEm)));
};

export type ChainedMotion = { panel: Arrival; contentOpacity: number; contentDy: number };

export const chainedMotion = (frame: number, durationInFrames: number, chainIn: boolean, chainOut: boolean): ChainedMotion => {
  const enter = entranceProgress(frame, 0);
  const leave = exitProgress(frame, durationInFrames);
  const panel: Arrival = chainIn
    ? { opacity: chainOut ? 1 : 1 - leave, dx: 0, dy: chainOut ? 0 : Math.round(leave * 16), scale: 1 }
    : arrival(frame, durationInFrames, { from: "up", exit: !chainOut });
  return {
    panel,
    contentOpacity: (chainIn ? interpolate(enter, [0, 0.45], [0, 1], clamp) : 1) * (chainOut ? 1 - leave : 1),
    contentDy: chainIn ? Math.round((1 - enter) * 24) : 0,
  };
};
