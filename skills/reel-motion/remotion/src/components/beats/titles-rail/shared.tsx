import { measureText } from "@remotion/layout-utils";
import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { continueRender, delayRender, Easing, interpolate, interpolateColors } from "remotion";
import { fontsReady } from "../../../fonts";
import type { RailState } from "../../../lib/rail";
import { colors, fontFamilies, layout, surface } from "../../../theme";
import { boxStyle, railSegmentRect, toneColor, type Box, type Tone } from "../../ui";

export const clampRange = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const easeInOutTravel = Easing.bezier(0.5, 0, 0.12, 1);

export const alpha = (hex: string, value: number) => {
  const raw = hex.replace("#", "");
  const full = raw.length === 3 ? raw.split("").map((c) => c + c).join("") : raw.slice(0, 6);
  const n = Number.parseInt(full, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${value})`;
};

export const mixHex = (a: string, b: string, t: number) => interpolateColors(t, [0, 1], [a, b]);

export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export const lerpBox = (a: Box, b: Box, t: number): Box => ({
  x0: lerp(a.x0, b.x0, t),
  x1: lerp(a.x1, b.x1, t),
  y0: lerp(a.y0, b.y0, t),
  y1: lerp(a.y1, b.y1, t),
});

export const useFontsLoaded = () => {
  const [handle] = useState(() => delayRender("Title layout waits for fonts"));
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    fontsReady.then(() => setLoaded(true));
  }, []);
  useEffect(() => {
    if (loaded) {
      continueRender(handle);
    }
  }, [loaded, handle]);
  return loaded;
};

type FitSpec = {
  text: string;
  maxWidth: number;
  maxSize: number;
  minSize: number;
  fontWeight: number;
  letterSpacingEm?: number;
  maxLines: number;
  ready: boolean;
};

const textWidth = (text: string, fontSize: number, fontWeight: number, letterSpacingEm: number) =>
  measureText({
    text,
    fontFamily: fontFamilies.sans,
    fontSize,
    fontWeight,
    letterSpacing: `${letterSpacingEm}em`,
    validateFontIsLoaded: true,
  }).width;

const wrapWords = (words: string[], fontSize: number, spec: FitSpec) => {
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (!current || textWidth(candidate, fontSize, spec.fontWeight, spec.letterSpacingEm ?? 0) <= spec.maxWidth) {
      current = candidate;
    } else {
      lines.push(current);
      current = word;
    }
  }
  if (current) {
    lines.push(current);
  }
  return lines;
};

const balancedTwoLines = (words: string[], fontSize: number, spec: FitSpec) => {
  let best: string[] | null = null;
  let bestWidest = Number.POSITIVE_INFINITY;
  for (let split = 1; split < words.length; split += 1) {
    const lines = [words.slice(0, split).join(" "), words.slice(split).join(" ")];
    const widest = Math.max(...lines.map((line) => textWidth(line, fontSize, spec.fontWeight, spec.letterSpacingEm ?? 0)));
    if (widest <= spec.maxWidth && widest < bestWidest) {
      best = lines;
      bestWidest = widest;
    }
  }
  return best;
};

export const fitLines = (spec: FitSpec): { fontSize: number; lines: string[] } => {
  const words = spec.text.split(/\s+/).filter(Boolean);
  if (!spec.ready) {
    return { fontSize: spec.maxSize, lines: [spec.text] };
  }
  for (let size = spec.maxSize; size >= spec.minSize; size -= 2) {
    const single = textWidth(spec.text, size, spec.fontWeight, spec.letterSpacingEm ?? 0);
    if (single <= spec.maxWidth) {
      return { fontSize: size, lines: [spec.text] };
    }
    if (spec.maxLines >= 2 && words.length > 1) {
      const balanced = balancedTwoLines(words, size, spec);
      if (balanced) {
        return { fontSize: size, lines: balanced };
      }
    }
    if (spec.maxLines > 2) {
      const lines = wrapWords(words, size, spec);
      if (lines.length <= spec.maxLines) {
        return { fontSize: size, lines };
      }
    }
  }
  return { fontSize: spec.minSize, lines: wrapWords(words, spec.minSize, spec).slice(0, spec.maxLines) };
};

export const measureWidth = (text: string, fontSize: number, fontWeight: number, letterSpacingEm = 0, ready = true) =>
  ready ? textWidth(text, fontSize, fontWeight, letterSpacingEm) : text.length * fontSize * 0.6;

export const hairline = `1px solid ${colors.border}`;

export const surfaceShadow = `inset 0 1px 0 ${alpha(colors.text, 0.07)}, ${surface.cardShadow}`;

export const panelBackground = `linear-gradient(180deg, ${colors.navyTop} 0%, ${colors.navyBottom} 100%)`;

export const SurfacePanel = ({
  box,
  borderColor = colors.border,
  glow,
  radius = surface.cardRadius,
  style,
  children,
}: {
  box: Box;
  borderColor?: string;
  glow?: string;
  radius?: number;
  style?: CSSProperties;
  children?: ReactNode;
}) => (
  <div
    style={{
      ...boxStyle(box),
      boxSizing: "border-box",
      borderRadius: radius,
      background: panelBackground,
      border: `1px solid ${borderColor}`,
      boxShadow: glow ? `${surfaceShadow}, ${glow}` : surfaceShadow,
      overflow: "hidden",
      ...style,
    }}
  >
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: `radial-gradient(120% 90% at 0% 0%, ${alpha(colors.text, 0.06)} 0%, ${alpha(colors.text, 0)} 55%)`,
      }}
    />
    {children}
  </div>
);

export type RailTones = { active: Tone; marked: Tone; fixed: Tone };

export const defaultRailTones: RailTones = { active: "accent", marked: "danger", fixed: "success" };

export const emptySegmentFill = alpha(colors.navyBottom, 0.62);

export const railStateColor = (state: RailState, tones: RailTones) =>
  state === "empty" ? colors.navyTile : toneColor(tones[state]);

export const railChipSize = Math.max(layout.rail.segmentH * 4, 40);

export const railChipRect = (index: number): Box => {
  const bar = railSegmentRect(index);
  const cx = (bar.x0 + bar.x1) / 2;
  return { x0: cx - railChipSize / 2, x1: cx + railChipSize / 2, y0: bar.y0, y1: bar.y0 + railChipSize };
};

export const CheckGlyph = ({ size, progress, color, strokeWidth = 3.2 }: { size: number; progress: number; color: string; strokeWidth?: number }) => {
  const length = 20;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ display: "block", overflow: "visible" }}>
      <path
        d="M5.5 12.5l4.2 4.2L18.5 7.8"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={length}
        strokeDashoffset={length * (1 - progress)}
        opacity={progress > 0.02 ? 1 : 0}
      />
    </svg>
  );
};

export const RailSegment = ({
  box,
  fill,
  borderColor,
  glowColor,
  glow,
  checkProgress,
  checkColor = colors.navyBottom,
  opacity = 1,
  transform,
}: {
  box: Box;
  fill: string;
  borderColor: string;
  glowColor: string;
  glow: number;
  checkProgress: number;
  checkColor?: string;
  opacity?: number;
  transform?: string;
}) => {
  const width = box.x1 - box.x0;
  const height = box.y1 - box.y0;
  const radius = Math.min(height / 2, Math.max(5, height * 0.28));
  return (
    <div
      style={{
        ...boxStyle(box),
        boxSizing: "border-box",
        borderRadius: radius,
        background: fill,
        border: `1px solid ${borderColor}`,
        boxShadow: `0 2px 8px ${alpha("#000000", 0.4)}, 0 0 ${Math.round(18 * glow)}px ${alpha(glowColor, 0.55 * glow)}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        opacity,
        transform,
      }}
    >
      {checkProgress > 0 && height > 16 ? (
        <CheckGlyph size={Math.min(width, height) * 0.78} progress={checkProgress} color={checkColor} />
      ) : null}
    </div>
  );
};

export type RailVisual = {
  box: Box;
  fill: string;
  borderColor: string;
  glowColor: string;
  glow: number;
  checkProgress: number;
  flipScaleY: number;
  shakeX: number;
  state: RailState;
};

const stateGlow: Record<RailState, number> = { empty: 0, active: 0.85, marked: 0.6, fixed: 0.7 };

export const railTransitionFrames = { color: 6, flip: 8, checkStart: 4, checkEnd: 11, flash: 12, shake: 4 };

const shakePattern = [0, 5, -4, 3, -2, 0];

export const railVisualAt = (
  segment: { state: RailState; since: number; previous: RailState },
  index: number,
  beatSec: number,
  fps: number,
  tones: RailTones,
): RailVisual => {
  const dtFrames = Number.isFinite(segment.since) ? Math.round((beatSec - segment.since) * fps) : Number.POSITIVE_INFINITY;
  const toColor = railStateColor(segment.state, tones);
  const fromColor = railStateColor(segment.previous, tones);
  const emptyBorder = alpha(colors.text, 0.38);
  const filledBorder = alpha(colors.text, 0.28);
  const flash = segment.state === "empty" ? 0 : interpolate(dtFrames, [0, 2, railTransitionFrames.flash], [0, 1, 0], clampRange);
  if (segment.state === "fixed" && segment.previous !== "fixed") {
    const flipP = interpolate(dtFrames, [0, railTransitionFrames.flip], [0, 1], { ...clampRange, easing: Easing.inOut(Easing.cubic) });
    const firstHalf = flipP < 0.5;
    const morph = interpolate(flipP, [0.5, 1], [0, 1], { ...clampRange, easing: Easing.out(Easing.cubic) });
    const bar = railSegmentRect(index);
    const box = firstHalf ? bar : lerpBox(bar, railChipRect(index), morph);
    return {
      box,
      fill: firstHalf ? (segment.previous === "empty" ? emptySegmentFill : fromColor) : toColor,
      borderColor: firstHalf && segment.previous === "empty" ? emptyBorder : filledBorder,
      glowColor: firstHalf ? fromColor : toColor,
      glow: firstHalf ? stateGlow[segment.previous] : stateGlow.fixed + flash * 0.6,
      checkProgress: interpolate(dtFrames, [railTransitionFrames.checkStart, railTransitionFrames.checkEnd], [0, 1], {
        ...clampRange,
        easing: Easing.inOut(Easing.cubic),
      }),
      flipScaleY: Math.max(0.08, Math.abs(Math.cos(Math.PI * flipP))),
      shakeX: 0,
      state: segment.state,
    };
  }
  const colorP = interpolate(dtFrames, [0, railTransitionFrames.color], [0, 1], { ...clampRange, easing: Easing.out(Easing.cubic) });
  const fill =
    segment.previous === segment.state
      ? segment.state === "empty"
        ? emptySegmentFill
        : toColor
      : segment.previous === "empty"
        ? interpolateColors(colorP, [0, 1], [emptySegmentFill, alpha(toColor, 1)])
        : segment.state === "empty"
          ? interpolateColors(colorP, [0, 1], [alpha(fromColor, 1), emptySegmentFill])
          : mixHex(fromColor, toColor, colorP);
  const borderColor =
    segment.state === "empty"
      ? emptyBorder
      : segment.previous === "empty"
        ? interpolateColors(colorP, [0, 1], [emptyBorder, filledBorder])
        : filledBorder;
  const shakeIndex = Math.floor(dtFrames);
  const shakeX = segment.state === "marked" && shakeIndex >= 0 && shakeIndex < shakePattern.length ? (shakePattern[shakeIndex] ?? 0) : 0;
  return {
    box: segment.state === "fixed" ? railChipRect(index) : railSegmentRect(index),
    fill,
    borderColor,
    glowColor: toColor,
    glow: lerp(stateGlow[segment.previous], stateGlow[segment.state], colorP) + flash * 0.7,
    checkProgress: segment.state === "fixed" ? 1 : 0,
    flipScaleY: 1,
    shakeX,
    state: segment.state,
  };
};
