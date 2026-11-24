import type { CSSProperties } from "react";
import { colors, fontFamilies } from "../../theme";

export const parseAccentMarkup = (text: string) =>
  text
    .split(/(\*[^*]+\*)/)
    .filter((part) => part.length > 0)
    .map((part) => (part.startsWith("*") && part.endsWith("*") ? { text: part.slice(1, -1), accent: true } : { text: part, accent: false }));

export const stripAccentMarkup = (text: string) => text.replace(/\*/g, "");

export const AccentText = ({
  text,
  accentColor = colors.accent,
  accentScale = 1.08,
  style,
}: {
  text: string;
  accentColor?: string;
  accentScale?: number;
  style?: CSSProperties;
}) => (
  <span style={{ whiteSpace: "pre-wrap", ...style }}>
    {parseAccentMarkup(text).map((part, index) =>
      part.accent ? (
        <span
          key={index}
          style={{
            fontFamily: fontFamilies.accent,
            fontStyle: "italic",
            fontWeight: 600,
            color: accentColor,
            fontSize: `${accentScale}em`,
            textTransform: "none",
          }}
        >
          {part.text}
        </span>
      ) : (
        <span key={index}>{part.text}</span>
      ),
    )}
  </span>
);
