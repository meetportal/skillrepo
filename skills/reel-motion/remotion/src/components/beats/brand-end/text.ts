import { measureText } from "@remotion/layout-utils";
import { useEffect, useState } from "react";
import { cancelRender, continueRender, delayRender } from "remotion";
import { fontsReady } from "../../../fonts";
import { fontFamilies } from "../../../theme";
import { parseAccentMarkup } from "../../ui";

export const useBrandFontsReady = () => {
  const [handle] = useState(() => delayRender("Brand end layout waits for fonts"));
  const [ready, setReady] = useState(false);
  useEffect(() => {
    fontsReady
      .then(() => {
        setReady(true);
        continueRender(handle);
      })
      .catch((error: unknown) => cancelRender(error));
  }, [handle]);
  return ready;
};

export type MarkupFont = { weight: number; accentScale: number };

export const measureMarkupLine = (line: string, fontSize: number, font: MarkupFont) =>
  parseAccentMarkup(line).reduce(
    (width, part) =>
      width +
      (part.accent
        ? measureText({
            text: part.text,
            fontFamily: fontFamilies.accent,
            fontSize: fontSize * font.accentScale,
            fontWeight: 600,
            additionalStyles: { fontStyle: "italic" },
            validateFontIsLoaded: true,
          }).width
        : measureText({
            text: part.text.replace(/ /g, " "),
            fontFamily: fontFamilies.sans,
            fontSize,
            fontWeight: font.weight,
            validateFontIsLoaded: true,
          }).width),
    0,
  );

export const fitMarkupSize = (
  lines: string[],
  { maxWidth, maxSize, minSize, ready, font }: { maxWidth: number; maxSize: number; minSize: number; ready: boolean; font: MarkupFont },
) => {
  if (!ready) {
    return maxSize;
  }
  for (let size = maxSize; size > minSize; size -= 1) {
    if (lines.every((line) => measureMarkupLine(line, size, font) <= maxWidth)) {
      return size;
    }
  }
  return minSize;
};
