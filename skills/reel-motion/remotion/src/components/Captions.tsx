import { measureText } from "@remotion/layout-utils";
import { useEffect, useMemo, useState } from "react";
import { AbsoluteFill, continueRender, delayRender, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { fontsReady } from "../fonts";
import { buildCaptionPages, modeFrames, splitPunctuation, timePages, type CaptionPage, type PageRules, type PageToken, type TimedPage } from "../lib/captionPages";
import { captionAccentStyles, captionRules, captionScrim, captionUnderline, layout, motion, type } from "../theme";
import { captionOptionsSchema, type AccentSpec, type AccentStyle, type CaptionMode, type CaptionModeName, type CaptionOptions, type CaptionWord } from "../types";

const wordGapEm = 0.26;

export const modeAtFrame = (modes: CaptionMode[], frame: number, fps: number): CaptionModeName => {
  let found: CaptionModeName = "talk";
  for (const mode of modes) {
    const { first, end } = modeFrames(mode, fps);
    if (frame >= first && frame < end) {
      found = mode.mode;
    }
  }
  return found;
};

const pageUsesCardStage = (modes: CaptionMode[], startSec: number, endSec: number) =>
  modes.some((mode) => mode.mode === "card" && mode.from < endSec && mode.to > startSec);

type Font = { fontFamily: string; fontWeight: number; fontStyle: "normal" | "italic"; fontSize: number };

const baseFont = (scale: number): Font => ({
  fontFamily: type.caption.fontFamily,
  fontWeight: type.caption.fontWeight,
  fontStyle: "normal",
  fontSize: type.caption.fontSize * scale,
});

const accentFont = (style: AccentStyle, scale: number): Font => {
  const accent = captionAccentStyles[style];
  return {
    fontFamily: accent.fontFamily,
    fontWeight: accent.fontWeight,
    fontStyle: accent.fontStyle,
    fontSize: type.caption.fontSize * scale * accent.scale,
  };
};

const tokenParts = (token: PageToken) => {
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

const measure = (text: string, font: Font) =>
  measureText({
    text,
    fontFamily: font.fontFamily,
    fontSize: font.fontSize,
    fontWeight: font.fontWeight,
    validateFontIsLoaded: true,
    additionalStyles: { fontStyle: font.fontStyle },
  }).width;

const lineWidth = (line: PageToken[], style: AccentStyle) =>
  line.reduce(
    (sum, token, index) =>
      sum +
      tokenParts(token).reduce((width, part) => width + measure(part.text, part.accent ? accentFont(style, 1) : baseFont(1)), 0) +
      (index > 0 ? wordGapEm * type.caption.fontSize : 0),
    0,
  );

const pageScale = (page: CaptionPage, style: AccentStyle) => {
  const widest = Math.max(...page.lines.map((line) => lineWidth(line, style)));
  return Math.min(1, captionRules.maxLineWidthPx / widest);
};

export const resolveCaptionOptions = (options: unknown): CaptionOptions => captionOptionsSchema.parse(options ?? {});

const pageRulesOf = (options: CaptionOptions): PageRules => ({
  hookMaxWords: options.hookMaxWords,
  bodyMinWords: options.bodyMinWords,
  bodyMaxWords: options.bodyMaxWords,
  mergeAcrossPauseSec: options.mergeAcrossPauseSec,
});

export const cutFramesOf = (cuts: number[], fps: number) => cuts.filter((cut) => cut > 0).map((cut) => Math.round(cut * fps));

const pageCenterY = (modes: CaptionMode[], page: TimedPage, fps: number) =>
  pageUsesCardStage(modes, page.firstFrame / fps, page.endFrame / fps) ? layout.captionY.card : layout.captionY.talk;

export type CaptionPageLayout = {
  text: string;
  firstFrame: number;
  endFrame: number;
  visibleFrames: number[];
  scale: number;
  centerY: number;
  bbox: [number, number, number, number];
};

const lineHeightPx = (line: PageToken[], scale: number, style: AccentStyle) =>
  Math.max(...line.map((token) => (token.accent ? accentFont(style, scale).fontSize : baseFont(scale).fontSize))) * type.caption.lineHeight;

const pageSize = (page: CaptionPage, scale: number, style: AccentStyle) => ({
  width: Math.max(...page.lines.map((line) => lineWidth(line, style) * scale)),
  height: page.lines.reduce((sum, line) => sum + lineHeightPx(line, scale, style), 0),
});

export const layoutCaptionPages = ({
  captions,
  accents,
  modes,
  hookEndSec,
  fps,
  totalFrames,
  cuts,
  options,
}: {
  captions: CaptionWord[];
  accents: AccentSpec[];
  modes: CaptionMode[];
  hookEndSec: number;
  fps: number;
  totalFrames: number;
  cuts: number[];
  options?: unknown;
}): CaptionPageLayout[] => {
  const settings = resolveCaptionOptions(options);
  const pages = timePages(buildCaptionPages(captions, accents, hookEndSec, pageRulesOf(settings)), modes, fps, totalFrames, cutFramesOf(cuts, fps));
  return pages.map((page) => {
    const scale = pageScale(page, settings.accentStyle);
    const centerY = pageCenterY(modes, page, fps);
    const { width, height } = pageSize(page, scale, settings.accentStyle);
    const half = width / 2;
    const visibleFrames: number[] = [];
    for (let frame = page.firstFrame; frame < page.endFrame; frame++) {
      if (modeAtFrame(modes, frame, fps) !== "hidden") {
        visibleFrames.push(frame);
      }
    }
    return {
      text: page.tokens.map((token) => token.text).join(" "),
      firstFrame: page.firstFrame,
      endFrame: page.endFrame,
      visibleFrames,
      scale,
      centerY,
      bbox: [captionRules.centerX - half, centerY - height / 2, captionRules.centerX + half, centerY + height / 2],
    };
  });
};

const partStyle = (accent: boolean, scale: number, style: AccentStyle) => {
  if (!accent) {
    return {
      ...baseFont(scale),
      color: type.caption.color,
      textShadow: type.caption.textShadow,
      WebkitTextStroke: `${type.caption.strokePx * scale}px ${type.caption.strokeColor}`,
    };
  }
  const settings = captionAccentStyles[style];
  const serif = settings.fontFamily === type.captionAccent.fontFamily;
  return {
    ...accentFont(style, scale),
    color: settings.color,
    textShadow: serif ? type.captionAccent.textShadow : type.caption.textShadow,
    WebkitTextStroke: `${settings.strokePx * scale}px ${serif ? type.captionAccent.strokeColor : type.caption.strokeColor}`,
    ...(settings.underlinePx > 0
      ? {
          textDecorationLine: "underline" as const,
          textDecorationColor: captionUnderline.color,
          textDecorationThickness: `${settings.underlinePx * scale}px`,
          textUnderlineOffset: `${(settings.underlinePx + captionUnderline.gapPx) * scale}px`,
          textDecorationSkipInk: "none" as const,
        }
      : {}),
  };
};

const Word = ({ token, scale, frame, fps, style }: { token: PageToken; scale: number; frame: number; fps: number; style: AccentStyle }) => {
  const revealStart = Math.round(token.start * fps) - captionRules.leadFrames - 1;
  const progress = interpolate(frame, [revealStart, revealStart + captionRules.revealFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <span
      style={{
        display: "inline-block",
        whiteSpace: "pre",
        opacity: progress,
        transform: `translateY(${(1 - motion.ease(progress)) * captionRules.risePx}px)`,
      }}
    >
      {tokenParts(token).map((part, index) => (
        <span key={index} style={{ ...partStyle(part.accent, scale, style), paintOrder: "stroke fill" }}>
          {part.text}
        </span>
      ))}
    </span>
  );
};

export const Captions = ({
  captions,
  accents,
  modes,
  hookEndSec,
  cuts,
  options,
}: {
  captions: CaptionWord[];
  accents: AccentSpec[];
  modes: CaptionMode[];
  hookEndSec: number;
  cuts: number[];
  options?: unknown;
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const [layoutHandle] = useState(() => delayRender("Caption layout waits for fonts"));
  const [fontsLoaded, setFontsLoaded] = useState(false);

  useEffect(() => {
    fontsReady.then(() => setFontsLoaded(true));
  }, []);

  useEffect(() => {
    if (fontsLoaded) {
      continueRender(layoutHandle);
    }
  }, [fontsLoaded, layoutHandle]);

  const settings = useMemo(() => resolveCaptionOptions(options), [options]);
  const pages = useMemo(
    () => timePages(buildCaptionPages(captions, accents, hookEndSec, pageRulesOf(settings)), modes, fps, durationInFrames, cutFramesOf(cuts, fps)),
    [captions, accents, modes, hookEndSec, fps, durationInFrames, cuts, settings],
  );
  const sizes = useMemo(
    () =>
      fontsLoaded
        ? pages.map((page) => {
            const scale = pageScale(page, settings.accentStyle);
            return { scale, ...pageSize(page, scale, settings.accentStyle) };
          })
        : null,
    [pages, fontsLoaded, settings],
  );

  if (!sizes || modeAtFrame(modes, frame, fps) === "hidden") {
    return null;
  }
  const pageIndex = pages.findIndex((page) => frame >= page.firstFrame && frame < page.endFrame);
  const page = pages[pageIndex];
  if (!page) {
    return null;
  }
  const size = sizes[pageIndex];
  const scale = size?.scale ?? 1;
  const centerY = pageCenterY(modes, page, fps);
  const scrim = Math.min(settings.localScrim, captionScrim.max);

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {scrim > 0 && size ? (
        <div
          style={{
            position: "absolute",
            left: captionRules.centerX - size.width / 2 - captionScrim.padXPx,
            top: centerY - size.height / 2 - captionScrim.padYPx,
            width: size.width + captionScrim.padXPx * 2,
            height: size.height + captionScrim.padYPx * 2,
            borderRadius: (size.height + captionScrim.padYPx * 2) / 2,
            backgroundColor: `rgba(${captionScrim.color},1)`,
            opacity: scrim,
            filter: `blur(${captionScrim.blurPx}px)`,
          }}
        />
      ) : null}
      <div
        style={{
          position: "absolute",
          left: captionRules.centerX - captionRules.maxLineWidthPx / 2,
          width: captionRules.maxLineWidthPx,
          top: centerY,
          transform: "translateY(-50%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          lineHeight: type.caption.lineHeight,
        }}
      >
        {page.lines.map((line, lineIndex) => (
          <div
            key={lineIndex}
            style={{ display: "flex", alignItems: "baseline", justifyContent: "center", gap: `${wordGapEm * type.caption.fontSize * scale}px` }}
          >
            {line.map((token) => (
              <Word key={`${token.start}-${token.text}`} token={token} scale={scale} frame={frame} fps={fps} style={settings.accentStyle} />
            ))}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
