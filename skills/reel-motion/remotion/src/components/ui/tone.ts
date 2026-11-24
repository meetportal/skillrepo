import { colors } from "../../theme";

export type Tone = "accent" | "danger" | "success" | "warning" | "brand" | "text" | "muted";

export const toneNames: [Tone, ...Tone[]] = ["accent", "danger", "success", "warning", "brand", "text", "muted"];

export const toneColor = (tone: Tone) => {
  switch (tone) {
    case "accent":
      return colors.accent;
    case "danger":
      return colors.danger;
    case "success":
      return colors.success;
    case "warning":
      return colors.warning;
    case "brand":
      return colors.brandBlueOnDark;
    case "text":
      return colors.text;
    case "muted":
      return colors.muted;
  }
};

export const toneFill = (tone: Tone, alpha = 0.16) => {
  const hex = toneColor(tone).replace("#", "");
  const value = Number.parseInt(hex, 16);
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`;
};
