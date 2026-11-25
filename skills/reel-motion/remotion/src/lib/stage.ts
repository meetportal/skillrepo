import { captionRules, layout as layoutTokens, zones } from "../theme";
import { layoutSchema, type CaptionOptions, type LayoutProps } from "../types";

export type Box = { x0: number; x1: number; y0: number; y1: number };

export type CaptionStage = {
  centerX: number;
  maxWidth: number;
  y: { talk: number; card: number };
  band: { y0: number; y1: number };
};

export const resolveLayout = (raw: unknown): LayoutProps => layoutSchema.parse(raw ?? {});

export const isFramed = (settings: LayoutProps) => settings.mode === "framed";

export const windowBox = (settings: LayoutProps): Box => ({
  x0: settings.window.centerX - settings.window.width / 2,
  x1: settings.window.centerX + settings.window.width / 2,
  y0: settings.window.y0,
  y1: settings.window.y1,
});

export const windowVideoTransform = (settings: LayoutProps, face: { x: number; y: number }) => {
  const box = windowBox(settings);
  const scale = (settings.window.width / layoutTokens.width) * settings.window.zoom;
  const videoWidth = layoutTokens.width * scale;
  const videoHeight = layoutTokens.height * scale;
  const targetX = settings.window.centerX - face.x * scale;
  const targetY = box.y0 + settings.window.focusY * (box.y1 - box.y0) - face.y * scale;
  const clampTo = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));
  return {
    scale,
    x: clampTo(targetX, box.x1 - videoWidth, box.x0),
    y: clampTo(targetY, box.y1 - videoHeight, box.y0),
  };
};

export const captionGapBelowWindowPx = 14;

const bottomLimit = layoutTokens.height - layoutTokens.bottomReservedPx;

export const captionStageOf = (settings: LayoutProps, options: CaptionOptions): CaptionStage => {
  const override = options.centerY ?? {};
  if (isFramed(settings)) {
    const centerX = settings.window.centerX;
    const half = Math.min(centerX - zones.safe.x0, zones.safe.x1 - centerX, settings.window.width / 2 - 30);
    return {
      centerX,
      maxWidth: 2 * half,
      y: { talk: override.talk ?? settings.captionY.talk, card: override.card ?? settings.captionY.card },
      band: { y0: settings.window.y1 + captionGapBelowWindowPx, y1: bottomLimit },
    };
  }
  return {
    centerX: captionRules.centerX,
    maxWidth: captionRules.maxLineWidthPx,
    y: { talk: override.talk ?? layoutTokens.captionY.talk, card: override.card ?? layoutTokens.captionY.card },
    band: { y0: zones.topLogo.y1, y1: bottomLimit },
  };
};

export const fitInBand = (centerY: number, height: number, band: { y0: number; y1: number }) =>
  Math.min(band.y1 - height / 2, Math.max(band.y0 + height / 2, centerY));
