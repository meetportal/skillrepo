import { Easing } from "remotion";
import brand from "../../../mailinfra-brand/brand.json";

export const colors = brand.colors;

export const layout = {
  width: brand.layout.width,
  height: brand.layout.height,
  safe: brand.layout.safe,
  cardBox: brand.layout.cardBox,
  captionY: brand.layout.captionY,
  rail: brand.layout.rail,
  bottomReservedPx: 420,
  rightReservedPx: 130,
};

export const fontFamilies = {
  sans: brand.fonts.sans.family,
  accent: brand.fonts.accent.family,
  mono: "ui-monospace, DejaVu Sans Mono, monospace",
};

export const type = {
  caption: {
    fontFamily: fontFamilies.sans,
    fontWeight: 700,
    fontSize: 68,
    lineHeight: 1.18,
    color: colors.text,
    textShadow: "0 4px 16px rgba(0,0,0,0.6)",
  },
  captionAccent: {
    fontFamily: fontFamilies.accent,
    fontStyle: "italic" as const,
    fontWeight: 600,
    scale: 1.08,
    color: colors.accent,
  },
  hook: { fontFamily: fontFamilies.sans, fontWeight: 800, fontSize: 120 },
  slam: { fontFamily: fontFamilies.sans, fontWeight: 800, fontSize: 76 },
  kicker: { fontFamily: fontFamilies.sans, fontWeight: 500, fontSize: 36, letterSpacing: "0.2em", color: colors.accent },
  cardMinPx: 44,
  numeralMinPx: 140,
  monoMinPx: 36,
};

export const easeOutExpo = Easing.bezier(0.16, 1, 0.3, 1);
export const easeInExit = Easing.bezier(0.7, 0, 0.84, 0);
export const easeInOutSine = Easing.bezier(0.37, 0, 0.63, 1);

export const motion = {
  ease: easeOutExpo,
  easeCss: "cubic-bezier(0.16,1,0.3,1)",
  exitEase: easeInExit,
  entranceFrames: 8,
  exitFrames: 5,
  staggerFrames: 3,
  arriveFromScale: 1.15,
  arriveFromOffsetPx: 40,
  overshootMaxRatio: 0.06,
  stampFromScale: 1.4,
  stampFrames: 6,
  maxSpringsPerBeat: 1,
  textLeadFramesMin: 0,
  textLeadFramesMax: 2,
  holdPerWordSec: 0.3,
  holdBaseSec: 0.5,
};

export const camera = {
  maxScale: 1.2,
  minScale: 1.0,
  pushFrames: 8,
  pushAmountMin: 0.04,
  pushAmountMax: 0.06,
  pushLeadFramesMin: 3,
  pushLeadFramesMax: 6,
  pushMinGapSec: 3,
  creepAmount: 0.03,
  creepEase: easeInOutSine,
  pushEase: easeOutExpo,
};

export const captionRules = {
  leadFrames: 1,
  revealFrames: 4,
  risePx: 6,
  hookMaxWords: 3,
  bodyMaxWords: 4,
  maxLines: 2,
  maxCharsPerLine: 22,
  minPageSec: 0.35,
  phrasePauseSec: 0.25,
  holdAfterLastWordSec: 0.6,
  maxLineWidthPx: brand.layout.safe.x1 - brand.layout.safe.x0,
  centerX: (brand.layout.safe.x0 + brand.layout.safe.x1) / 2,
};
