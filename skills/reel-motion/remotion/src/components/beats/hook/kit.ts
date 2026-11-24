import { measureText } from "@remotion/layout-utils";
import { Easing, interpolate } from "remotion";
import { fontFamilies, motion } from "../../../theme";
import { parseAccentMarkup } from "../../ui";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const secondsToFrames = (seconds: number, fps: number) => Math.round(seconds * fps);

const settleTable = new Map<string, number[]>();

const buildSettleTable = (distancePx: number, frames: number) => {
  const sign = Math.sign(distancePx);
  const total = Math.abs(distancePx);
  const values: number[] = [];
  let previous = total;
  for (let step = 0; step <= frames; step += 1) {
    const ideal = total * (1 - motion.ease(step / frames));
    let value = step === 0 ? total : Math.min(Math.round(ideal), previous - 1);
    value = Math.max(0, value);
    if (previous === 0) {
      value = 0;
    }
    values.push(sign * value);
    previous = value;
  }
  return values;
};

export const settleOffset = (frame: number, start: number, distancePx: number, frames = motion.entranceFrames) => {
  const local = frame - start;
  if (local <= 0) {
    return distancePx;
  }
  if (local >= frames) {
    return 0;
  }
  const key = `${distancePx}|${frames}`;
  let table = settleTable.get(key);
  if (!table) {
    table = buildSettleTable(distancePx, frames);
    settleTable.set(key, table);
  }
  return table[local] ?? 0;
};

export const fadeIn = (frame: number, start: number, frames = motion.entranceFrames) =>
  interpolate(frame, [start, start + frames * 0.45], [0, 1], clamp);

export const exitAmount = (frame: number, exitEnd: number, frames = motion.exitFrames) =>
  interpolate(frame, [exitEnd - frames - 1, exitEnd - 1], [0, 1], { ...clamp, easing: motion.exitEase });

export const exitOpacity = (frame: number, exitEnd: number, frames = motion.exitFrames) =>
  interpolate(frame, [exitEnd - frames - 1, exitEnd - 1], [1, 0], { ...clamp, easing: Easing.in(Easing.quad) });

export const exitDrift = (amount: number, distancePx: number) => Math.round(amount * distancePx);

export type LineFont = { fontSize: number; fontWeight: number; uppercase: boolean; letterSpacingEm: number; accentScale: number };

export const measureMarkupLine = (markup: string, font: LineFont) =>
  parseAccentMarkup(markup).reduce((width, part) => {
    if (part.text.length === 0) {
      return width;
    }
    const measured = part.accent
      ? measureText({
          text: part.text,
          fontFamily: fontFamilies.accent,
          fontSize: font.fontSize * font.accentScale,
          fontWeight: 600,
          additionalStyles: { fontStyle: "italic" },
        })
      : measureText({
          text: font.uppercase ? part.text.toUpperCase() : part.text,
          fontFamily: fontFamilies.sans,
          fontSize: font.fontSize,
          fontWeight: font.fontWeight,
          letterSpacing: `${font.letterSpacingEm}em`,
        });
    return width + measured.width;
  }, 0);

export const fitMarkupLine = (markup: string, font: LineFont, maxWidthPx: number) => {
  const width = measureMarkupLine(markup, font);
  if (width <= maxWidthPx) {
    return font.fontSize;
  }
  return Math.floor((font.fontSize * maxWidthPx) / width);
};
