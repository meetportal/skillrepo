import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill } from "remotion";
import { layout, zones } from "../../theme";

export type ZoneName = keyof typeof zones;

export type Box = { x0: number; x1: number; y0: number; y1: number };

export { zones };

export const boxStyle = (box: Box): CSSProperties => ({
  position: "absolute",
  left: box.x0,
  top: box.y0,
  width: box.x1 - box.x0,
  height: box.y1 - box.y0,
});

export const insetBox = (box: Box, px: number): Box => ({ x0: box.x0 + px, x1: box.x1 - px, y0: box.y0 + px, y1: box.y1 - px });

export const Zone = ({ zone, children, style }: { zone: ZoneName | Box; children?: ReactNode; style?: CSSProperties }) => (
  <div style={{ ...boxStyle(typeof zone === "string" ? zones[zone] : zone), ...style }}>{children}</div>
);

const railGapPx = 16;

export const railSegmentRect = (index: number): Box => {
  const width = layout.rail.segmentW;
  const x0 = layout.rail.x + index * (width + railGapPx);
  return { x0, x1: x0 + width, y0: layout.rail.y, y1: layout.rail.y + layout.rail.segmentH };
};

const checklistRowHeight = 96;
const checklistIconPx = 60;

export const checklistRowRect = (index: number, count: number): Box & { iconBox: Box } => {
  const card = zones.card;
  const top = (card.y0 + card.y1) / 2 - (count * checklistRowHeight) / 2 + index * checklistRowHeight;
  const x0 = card.x0 + 48;
  const iconTop = top + (checklistRowHeight - checklistIconPx) / 2;
  return {
    x0,
    x1: card.x1 - 48,
    y0: top,
    y1: top + checklistRowHeight,
    iconBox: { x0, x1: x0 + checklistIconPx, y0: iconTop, y1: iconTop + checklistIconPx },
  };
};

const guideColors: Record<ZoneName, string> = {
  safe: "rgba(0,255,255,0.8)",
  card: "rgba(255,0,255,0.8)",
  headline: "rgba(255,255,0,0.8)",
  rail: "rgba(0,255,0,0.8)",
  takeoverBand: "rgba(255,128,0,0.6)",
  topLogo: "rgba(255,255,255,0.8)",
};

export const SafeAreaGuides = () => (
  <AbsoluteFill style={{ pointerEvents: "none" }}>
    {(Object.keys(zones) as ZoneName[]).map((name) => (
      <div key={name} style={{ ...boxStyle(zones[name]), outline: `3px dashed ${guideColors[name]}` }} />
    ))}
    <div style={{ position: "absolute", left: 0, right: 0, top: layout.height - layout.bottomReservedPx, bottom: 0, background: "rgba(255,0,0,0.15)" }} />
    <div style={{ position: "absolute", top: 0, bottom: 0, left: layout.width - layout.rightReservedPx, right: 0, background: "rgba(255,0,0,0.15)" }} />
  </AbsoluteFill>
);
