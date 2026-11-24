import type { CSSProperties, ReactNode } from "react";
import { type } from "../../theme";
import { toneColor, type Tone } from "./tone";

export const Kicker = ({ tone = "accent", style, children }: { tone?: Tone; style?: CSSProperties; children: ReactNode }) => (
  <div
    style={{
      fontFamily: type.kicker.fontFamily,
      fontWeight: type.kicker.fontWeight,
      fontSize: type.kicker.fontSize,
      letterSpacing: type.kicker.letterSpacing,
      textTransform: "uppercase",
      color: toneColor(tone),
      lineHeight: 1.1,
      ...style,
    }}
  >
    {children}
  </div>
);
