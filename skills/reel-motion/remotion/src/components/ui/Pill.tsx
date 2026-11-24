import type { CSSProperties, ReactNode } from "react";
import { colors, fontFamilies, surface } from "../../theme";
import { toneColor, toneFill, type Tone } from "./tone";

export type PillProps = {
  tone?: Tone;
  variant?: "solid" | "soft" | "outline";
  fontSize?: number;
  style?: CSSProperties;
  children: ReactNode;
};

export const Pill = ({ tone = "accent", variant = "solid", fontSize = 44, style, children }: PillProps) => {
  const color = toneColor(tone);
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: fontSize * 0.3,
        padding: `${fontSize * 0.28}px ${fontSize * 0.6}px`,
        borderRadius: surface.pillRadius,
        fontFamily: fontFamilies.sans,
        fontWeight: 700,
        fontSize,
        lineHeight: 1,
        letterSpacing: "0.04em",
        whiteSpace: "nowrap",
        background: variant === "solid" ? color : variant === "soft" ? toneFill(tone, 0.2) : "transparent",
        color: variant === "solid" ? colors.navyBottom : color,
        border: `${surface.borderPx + 1}px solid ${color}`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
