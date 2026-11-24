import { Easing } from "remotion";
import { brand } from "./lib/brand";

export const colors = brand.colors;

export const layout = {
  width: brand.layout.width,
  height: brand.layout.height,
  safe: brand.layout.safe,
  cardBox: brand.layout.cardBox,
  captionY: brand.layout.captionY,
  rail: brand.layout.rail,
  topLogo: brand.layout.topLogo,
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
    textShadow: "0 2px 4px rgba(0,0,0,0.85), 0 0 2px rgba(0,0,0,0.9), 0 4px 14px rgba(0,0,0,0.55)",
    strokeColor: "rgba(8,16,36,0.75)",
    strokePx: 5,
  },
  captionAccent: {
    fontFamily: fontFamilies.accent,
    fontStyle: "italic" as const,
    fontWeight: 600,
    scale: 1.08,
    color: colors.accent,
    textShadow: "0 2px 3px rgba(0,0,0,0.95), 0 0 2px rgba(0,0,0,1), 0 0 10px rgba(8,16,36,0.75), 0 4px 14px rgba(0,0,0,0.6)",
    strokeColor: "rgba(8,16,36,0.9)",
    strokePx: 6,
  },
  hook: { fontFamily: fontFamilies.sans, fontWeight: 800, fontSize: 120 },
  slam: { fontFamily: fontFamilies.sans, fontWeight: 800, fontSize: 76 },
  kicker: { fontFamily: fontFamilies.sans, fontWeight: 500, fontSize: 36, letterSpacing: "0.2em", color: colors.accent },
  cardMinPx: 44,
  numeralMinPx: 140,
  monoMinPx: 36,
};

export const zones = {
  safe: { x0: brand.layout.safe.x0, x1: brand.layout.safe.x1, y0: brand.layout.safe.y0, y1: brand.layout.safe.y1 },
  card: { x0: brand.layout.cardBox.x0, x1: brand.layout.cardBox.x1, y0: brand.layout.cardBox.y0, y1: brand.layout.cardBox.y1 },
  headline: { x0: brand.layout.safe.x0, x1: brand.layout.safe.x1, y0: 236, y1: 440 },
  rail: {
    x0: brand.layout.rail.x,
    x1: brand.layout.rail.x + brand.layout.rail.count * brand.layout.rail.segmentW + (brand.layout.rail.count - 1) * 16,
    y0: brand.layout.rail.y,
    y1: brand.layout.rail.y + 40,
  },
  takeoverBand: { x0: brand.layout.safe.x0, x1: brand.layout.safe.x1, y0: 380, y1: 1060 },
  topLogo: { x0: brand.layout.topLogo.x0, x1: brand.layout.topLogo.x1, y0: brand.layout.topLogo.y0, y1: brand.layout.topLogo.y1 },
};

export const surface = {
  cardRadius: 36,
  tileRadius: 24,
  pillRadius: 999,
  cardPadding: 40,
  borderPx: 2,
  cardGradient: `linear-gradient(180deg, ${brand.colors.navyTop} 0%, ${brand.colors.navyBottom} 100%)`,
  takeoverGradient: `linear-gradient(180deg, ${brand.colors.navyTop} 0%, ${brand.colors.navyBottom} 100%)`,
  cardShadow: "0 18px 48px rgba(0,0,0,0.45), 0 4px 12px rgba(0,0,0,0.35)",
  textShadow: "0 2px 6px rgba(0,0,0,0.5)",
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
  bodyMinWords: 2,
  bodyMaxWords: 4,
  maxLines: 2,
  maxCharsPerLine: 22,
  minPageSec: 0.35,
  phrasePauseSec: 0.25,
  holdAfterLastWordSec: 0.6,
  maxLineWidthPx: brand.layout.safe.x1 - brand.layout.safe.x0,
  centerX: (brand.layout.safe.x0 + brand.layout.safe.x1) / 2,
};
