import { layout, surface, zones } from "../../../theme";
import type { Box } from "../../ui";
import { placeLogoCentered, type LogoMeta, type LogoPlacement } from "./logo";

export type LogoCard = "cream" | "navy";

export const logoForCard = (card: LogoCard) => (card === "navy" ? "white" : "color");

export const logoPopDefaults = {
  card: "cream" as LogoCard,
  widthPx: 720,
  centerY: Math.round((zones.card.y0 + zones.card.y1) / 2),
};

export const brandCenterX = (zones.safe.x0 + zones.safe.x1) / 2;

export const fullFrameCenterX = layout.width / 2;

export const fullFrameContentWidth = 2 * Math.min(fullFrameCenterX - zones.safe.x0, zones.safe.x1 - fullFrameCenterX);

export const logoPopRadius = surface.cardRadius;

export type LogoPopGeometry = { card: Box; logo: LogoPlacement; logoWidth: number };

export const logoPopGeometry = (meta: LogoMeta, widthPx: number, centerY: number): LogoPopGeometry => {
  const padX = Math.round(widthPx * 0.1);
  const logoWidth = widthPx - padX * 2;
  const logoHeight = (logoWidth * meta.height) / meta.width;
  const padY = Math.max(56, Math.round(widthPx * 0.105));
  const cardHeight = Math.min(logoHeight + padY * 2, layout.safe.y1 - layout.safe.y0);
  const card: Box = {
    x0: Math.round(brandCenterX - widthPx / 2),
    x1: Math.round(brandCenterX + widthPx / 2),
    y0: Math.round(centerY - cardHeight / 2),
    y1: Math.round(centerY + cardHeight / 2),
  };
  return { card, logo: placeLogoCentered(meta, brandCenterX, centerY, logoWidth), logoWidth };
};
