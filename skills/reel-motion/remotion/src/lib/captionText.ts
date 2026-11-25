import { measureText } from "@remotion/layout-utils";
import { splitPunctuation, type PageToken } from "./captionPages";

export type Font = { fontFamily: string; fontWeight: number; fontStyle: "normal" | "italic"; fontSize: number };

export const tokenParts = (token: PageToken) => {
  if (!token.accent) {
    return [{ text: token.text, accent: false }];
  }
  const { lead, core, trail } = splitPunctuation(token.text);
  return [
    { text: lead, accent: false },
    { text: core, accent: true },
    { text: trail, accent: false },
  ].filter((part) => part.text.length > 0);
};

export const measure = (text: string, font: Font) =>
  measureText({
    text,
    fontFamily: font.fontFamily,
    fontSize: font.fontSize,
    fontWeight: font.fontWeight,
    validateFontIsLoaded: true,
    additionalStyles: { fontStyle: font.fontStyle },
  }).width;
