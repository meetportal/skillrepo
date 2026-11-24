import type { CSSProperties, ReactNode } from "react";
import { colors, surface } from "../../theme";
import { boxStyle, type Box } from "./SafeArea";
import { toneColor, type Tone } from "./tone";

export type CardProps = {
  box?: Box;
  tone?: Tone | "neutral";
  padding?: number;
  radius?: number;
  style?: CSSProperties;
  children?: ReactNode;
};

export const Card = ({ box, tone = "neutral", padding = surface.cardPadding, radius = surface.cardRadius, style, children }: CardProps) => (
  <div
    style={{
      ...(box ? boxStyle(box) : { position: "relative" }),
      boxSizing: "border-box",
      background: surface.cardGradient,
      border: `${surface.borderPx}px solid ${tone === "neutral" ? colors.border : toneColor(tone)}`,
      borderRadius: radius,
      padding,
      boxShadow: surface.cardShadow,
      color: colors.text,
      overflow: "hidden",
      ...style,
    }}
  >
    {children}
  </div>
);

export const Tile = ({ tone = "neutral", style, children }: { tone?: Tone | "neutral"; style?: CSSProperties; children?: ReactNode }) => (
  <div
    style={{
      boxSizing: "border-box",
      background: colors.navyTile,
      border: `${surface.borderPx}px solid ${tone === "neutral" ? colors.border : toneColor(tone)}`,
      borderRadius: surface.tileRadius,
      color: colors.text,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      ...style,
    }}
  >
    {children}
  </div>
);
