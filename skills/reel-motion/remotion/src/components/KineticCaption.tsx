import { AbsoluteFill, Easing, interpolate, interpolateColors } from "remotion";
import type { CaptionPage, PageToken, TimedPage } from "../lib/captionPages";
import { measure, tokenParts, type Font } from "../lib/captionText";
import type { CaptionStage } from "../lib/stage";
import { colors, fontFamilies, kinetic } from "../theme";
import type { KineticOptions } from "../types";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const popEase = Easing.bezier(0.22, 1, 0.36, 1);

const slideEase = Easing.bezier(0.33, 1, 0.68, 1);

export type KineticWord = { token: PageToken; x: number; width: number; line: number };

export type KineticLayout = { scale: number; fontPx: number; lineHeight: number; width: number; height: number; words: KineticWord[] };

const baseFont = (fontPx: number): Font => ({ fontFamily: fontFamilies.sans, fontWeight: kinetic.fontWeight, fontStyle: "normal", fontSize: fontPx });

const accentFont = (fontPx: number): Font => ({
  fontFamily: fontFamilies.accent,
  fontWeight: kinetic.accentWeight,
  fontStyle: "italic",
  fontSize: fontPx * kinetic.accentScale,
});

const tokenWidth = (token: PageToken, fontPx: number) =>
  tokenParts(token).reduce((sum, part) => sum + measure(part.text, part.accent ? accentFont(fontPx) : baseFont(fontPx)), 0);

export const kineticPillPadPx = (fontPx: number) => ({ x: kinetic.pillPadXEm * fontPx, top: kinetic.pillTopEm * fontPx });

export const layoutKineticPage = (page: CaptionPage, options: KineticOptions, stage: CaptionStage): KineticLayout => {
  const natural = options.fontPx;
  const gap = kinetic.wordGapEm * natural;
  const lineWidths = page.lines.map((line) => line.reduce((sum, token, index) => sum + tokenWidth(token, natural) + (index > 0 ? gap : 0), 0));
  const widest = Math.max(...lineWidths);
  const naturalHeight = page.lines.length * natural * kinetic.lineHeight;
  const pad = options.highlight === "pill" ? kinetic.pillPadXEm * natural * 2 : 0;
  const scale = Math.min(1, stage.maxWidth / (widest + pad), (stage.band.y1 - stage.band.y0) / naturalHeight);
  const fontPx = natural * scale;
  const words: KineticWord[] = [];
  page.lines.forEach((line, lineIndex) => {
    let x = (-lineWidths[lineIndex]! * scale) / 2;
    for (const token of line) {
      const width = tokenWidth(token, natural) * scale;
      words.push({ token, x, width, line: lineIndex });
      x += width + gap * scale;
    }
  });
  return { scale, fontPx, lineHeight: fontPx * kinetic.lineHeight, width: widest * scale, height: naturalHeight * scale, words };
};

type Box = { x0: number; x1: number; y0: number; y1: number };

const wordBox = (word: KineticWord, layout: KineticLayout, centerX: number, top: number): Box => {
  const pad = kineticPillPadPx(layout.fontPx);
  const lineTop = top + word.line * layout.lineHeight;
  return { x0: centerX + word.x - pad.x, x1: centerX + word.x + word.width + pad.x, y0: lineTop + pad.top, y1: lineTop + kinetic.pillBottomEm * layout.fontPx };
};

const mixBox = (a: Box, b: Box, t: number): Box => ({
  x0: a.x0 + (b.x0 - a.x0) * t,
  x1: a.x1 + (b.x1 - a.x1) * t,
  y0: a.y0 + (b.y0 - a.y0) * t,
  y1: a.y1 + (b.y1 - a.y1) * t,
});

const strokeColor = (alpha: number) => kinetic.strokeColor.replace(/[\d.]+\)$/, `${(0.8 * alpha).toFixed(3)})`);

export const KineticCaption = ({
  page,
  layout,
  options,
  stage,
  centerY,
  frame,
  fps,
}: {
  page: TimedPage;
  layout: KineticLayout;
  options: KineticOptions;
  stage: CaptionStage;
  centerY: number;
  frame: number;
  fps: number;
}) => {
  const top = centerY - layout.height / 2;
  const onsets = layout.words.map((word) => Math.round(word.token.start * fps));
  const switches = onsets.map((onset) => Math.max(page.firstFrame, onset - 1));
  const current = switches.reduce((found, switchFrame, index) => (switchFrame <= frame ? index : found), -1);
  const pill = options.highlight === "pill";
  const moveFrames = pill ? kinetic.pillSlideFrames : kinetic.colorFrames;
  const move = current >= 0 ? interpolate(frame, [switches[current]!, switches[current]! + moveFrames], [0, 1], { ...clamp, easing: slideEase }) : 0;
  const popOf = (index: number) =>
    interpolate(frame, [onsets[index]! - 2, onsets[index]! - 2 + options.popFrames], [0, 1], { ...clamp, easing: popEase });
  const appearOf = (index: number) => interpolate(frame, [onsets[index]! - 2, onsets[index]!], [0, 1], clamp);

  const previous = current - 1;
  const slides = pill && previous >= 0 && layout.words[previous]!.line === layout.words[current]!.line && move < 1;
  const pillBox =
    current >= 0
      ? slides
        ? mixBox(wordBox(layout.words[previous]!, layout, stage.centerX, top), wordBox(layout.words[current]!, layout, stage.centerX, top), move)
        : wordBox(layout.words[current]!, layout, stage.centerX, top)
      : null;
  const pillPop = current >= 0 && !slides ? popOf(current) : 1;
  const pillOpacity = current >= 0 ? (slides ? 1 : appearOf(current)) : 0;

  const inkAmount = (index: number) => {
    if (index === current) {
      return move;
    }
    if (index === previous && move < 1) {
      return 1 - move;
    }
    return 0;
  };

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {pill && pillBox && pillOpacity > 0 ? (
        <div
          style={{
            position: "absolute",
            left: pillBox.x0,
            top: pillBox.y0,
            width: pillBox.x1 - pillBox.x0,
            height: pillBox.y1 - pillBox.y0,
            borderRadius: kinetic.pillRadiusEm * layout.fontPx,
            backgroundColor: colors.accent,
            boxShadow: kinetic.pillShadow,
            opacity: pillOpacity,
            transform: `scale(${options.popFromScale + (1 - options.popFromScale) * pillPop})`,
          }}
        />
      ) : null}
      {layout.words.map((word, index) => {
        const appear = appearOf(index);
        if (appear <= 0) {
          return null;
        }
        const pop = popOf(index);
        const amount = inkAmount(index);
        const lineTop = top + word.line * layout.lineHeight;
        return (
          <span
            key={`${word.token.start}-${index}`}
            style={{
              position: "absolute",
              left: stage.centerX + word.x,
              top: lineTop,
              width: word.width,
              height: layout.lineHeight,
              lineHeight: `${layout.lineHeight}px`,
              whiteSpace: "pre",
              opacity: appear,
              transformOrigin: "50% 60%",
              transform: `scale(${options.popFromScale + (1 - options.popFromScale) * pop})`,
            }}
          >
            {tokenParts(word.token).map((part, partIndex) => {
              const font = part.accent ? accentFont(layout.fontPx) : baseFont(layout.fontPx);
              const rest = part.accent ? colors.accent : colors.text;
              const lit = pill ? colors.ink : colors.accent;
              const ink = pill ? amount : part.accent ? 0 : amount;
              const color = ink > 0 ? interpolateColors(ink, [0, 1], [rest, lit]) : rest;
              const outline = pill ? 1 - amount : 1;
              return (
                <span
                  key={partIndex}
                  style={{
                    ...font,
                    color,
                    paintOrder: "stroke fill",
                    WebkitTextStroke: `${(kinetic.strokeEm * layout.fontPx).toFixed(2)}px ${strokeColor(outline)}`,
                    textShadow: outline > 0.01 ? kinetic.textShadow.replace(/rgba\((\d+),(\d+),(\d+),([\d.]+)\)/g, (_, r, g, b, a) => `rgba(${r},${g},${b},${(Number(a) * outline).toFixed(3)})`) : "none",
                  }}
                >
                  {part.text}
                </span>
              );
            })}
          </span>
        );
      })}
    </AbsoluteFill>
  );
};
