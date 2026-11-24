import { measureText } from "@remotion/layout-utils";
import { useEffect, useMemo, useState } from "react";
import { AbsoluteFill, continueRender, delayRender, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { fontsReady } from "../fonts";
import { buildCaptionPages, type CaptionPage, type PageToken } from "../lib/captionPages";
import { captionRules, layout, motion, type } from "../theme";
import type { CaptionMode, CaptionModeName, CaptionWord } from "../types";

const wordGapEm = 0.26;

const modeAt = (modes: CaptionMode[], timeSec: number): CaptionModeName => {
  let found: CaptionModeName = "talk";
  for (const mode of modes) {
    if (timeSec >= mode.from && timeSec < mode.to) {
      found = mode.mode;
    }
  }
  return found;
};

const pageUsesCardStage = (modes: CaptionMode[], startSec: number, endSec: number) =>
  modes.some((mode) => mode.mode === "card" && mode.from < endSec && mode.to > startSec);

const tokenFont = (token: PageToken, scale: number) => {
  const size = type.caption.fontSize * scale * (token.accent ? type.captionAccent.scale : 1);
  return token.accent
    ? { fontFamily: type.captionAccent.fontFamily, fontWeight: type.captionAccent.fontWeight, fontStyle: "italic" as const, fontSize: size }
    : { fontFamily: type.caption.fontFamily, fontWeight: type.caption.fontWeight, fontStyle: "normal" as const, fontSize: size };
};

const lineWidth = (line: PageToken[]) =>
  line.reduce((sum, token, index) => {
    const font = tokenFont(token, 1);
    const { width } = measureText({
      text: token.text,
      fontFamily: font.fontFamily,
      fontSize: font.fontSize,
      fontWeight: font.fontWeight,
      validateFontIsLoaded: true,
      additionalStyles: { fontStyle: font.fontStyle },
    });
    return sum + width + (index > 0 ? wordGapEm * type.caption.fontSize : 0);
  }, 0);

const pageScale = (page: CaptionPage) => {
  const widest = Math.max(...page.lines.map(lineWidth));
  return Math.min(1, captionRules.maxLineWidthPx / widest);
};

type TimedPage = CaptionPage & { firstFrame: number; endFrame: number };

const timePages = (pages: CaptionPage[], fps: number, totalFrames: number): TimedPage[] => {
  const firstFrames = pages.map((page) => Math.max(0, Math.round(page.start * fps) - captionRules.leadFrames));
  return pages.map((page, index) => {
    const nextFirst = firstFrames[index + 1] ?? totalFrames;
    const holdEnd = Math.round((page.end + captionRules.holdAfterLastWordSec) * fps);
    return { ...page, firstFrame: firstFrames[index]!, endFrame: Math.min(nextFirst, holdEnd, totalFrames) };
  });
};

const Word = ({ token, scale, frame, fps }: { token: PageToken; scale: number; frame: number; fps: number }) => {
  const revealStart = Math.round(token.start * fps) - captionRules.leadFrames - 1;
  const progress = interpolate(frame, [revealStart, revealStart + captionRules.revealFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const font = tokenFont(token, scale);
  return (
    <span
      style={{
        ...font,
        display: "inline-block",
        whiteSpace: "pre",
        color: token.accent ? type.captionAccent.color : type.caption.color,
        opacity: progress,
        transform: `translateY(${(1 - motion.ease(progress)) * captionRules.risePx}px)`,
      }}
    >
      {token.text}
    </span>
  );
};

export const Captions = ({
  captions,
  accents,
  modes,
  hookEndSec,
}: {
  captions: CaptionWord[];
  accents: string[];
  modes: CaptionMode[];
  hookEndSec: number;
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

  const pages = useMemo(
    () => timePages(buildCaptionPages(captions, accents, hookEndSec), fps, durationInFrames),
    [captions, accents, hookEndSec, fps, durationInFrames],
  );
  const scales = useMemo(() => (fontsLoaded ? pages.map(pageScale) : null), [pages, fontsLoaded]);

  if (!scales || modeAt(modes, frame / fps) === "hidden") {
    return null;
  }
  const pageIndex = pages.findIndex((page) => frame >= page.firstFrame && frame < page.endFrame);
  const page = pages[pageIndex];
  if (!page) {
    return null;
  }
  const scale = scales[pageIndex] ?? 1;
  const centerY = pageUsesCardStage(modes, page.firstFrame / fps, page.endFrame / fps)
    ? layout.captionY.card
    : layout.captionY.talk;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
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
          textShadow: type.caption.textShadow,
        }}
      >
        {page.lines.map((line, lineIndex) => (
          <div
            key={lineIndex}
            style={{ display: "flex", alignItems: "baseline", justifyContent: "center", gap: `${wordGapEm * type.caption.fontSize * scale}px` }}
          >
            {line.map((token) => (
              <Word key={`${token.start}-${token.text}`} token={token} scale={scale} frame={frame} fps={fps} />
            ))}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
