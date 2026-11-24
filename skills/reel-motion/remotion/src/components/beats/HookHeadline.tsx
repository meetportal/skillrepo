import { AbsoluteFill } from "remotion";
import { z } from "zod";
import { markupLineSchema, toneSchema } from "../../lib/beatSchemas";
import { fontFamilies, motion, zones } from "../../theme";
import type { BeatProps } from "../../types";
import { AccentText, toneColor } from "../ui";
import { exitAmount, exitDrift, exitOpacity, fadeIn, fitMarkupLine, secondsToFrames, settleOffset, type LineFont } from "./hook/kit";

const lineStyleSchema = z.object({
  size: z.number().positive(),
  weight: z.number().int().min(100).max(900),
  uppercase: z.boolean(),
  trackingEm: z.number(),
});

export const schema = z.object({
  lines: z.array(markupLineSchema).min(1).max(3),
  lineStyles: z
    .array(lineStyleSchema)
    .default([
      { size: 120, weight: 800, uppercase: true, trackingEm: -0.02 },
      { size: 72, weight: 700, uppercase: false, trackingEm: -0.01 },
    ]),
  textTone: toneSchema.default("text"),
  accentTone: toneSchema.default("accent"),
  top: z.number().default(zones.headline.y0),
  lineGapPx: z.number().default(6),
  appearAt: z.number().nonnegative().default(0),
  entrance: z.enum(["cut", "rise"]).default("cut"),
  exit: z.enum(["cut", "fade"]).default("fade"),
  exitAt: z.number().nonnegative().optional(),
  scrim: z.number().min(0).max(1).default(0.45),
});

export type HookHeadlineProps = z.infer<typeof schema>;

const accentScale = 1.06;
const scrimFadeFrames = 6;

const fontFor = (style: z.infer<typeof lineStyleSchema>): LineFont => ({
  fontSize: style.size,
  fontWeight: style.weight,
  uppercase: style.uppercase,
  letterSpacingEm: style.trackingEm,
  accentScale,
});

const HookHeadline = ({ props, frame, durationInFrames, fps }: BeatProps<HookHeadlineProps>) => {
  const appearFrame = secondsToFrames(props.appearAt, fps);
  const exitEnd = props.exitAt === undefined ? durationInFrames : Math.min(durationInFrames, secondsToFrames(props.exitAt, fps));
  if (frame < appearFrame || frame >= exitEnd) {
    return null;
  }
  const fading = props.exit === "fade";
  const leaving = fading ? exitAmount(frame, exitEnd) : 0;
  const visibility = fading ? exitOpacity(frame, exitEnd) : 1;
  const maxWidth = zones.headline.x1 - zones.headline.x0;
  const textColor = toneColor(props.textTone);
  const accentColor = toneColor(props.accentTone);
  const fallbackStyle = props.lineStyles[props.lineStyles.length - 1] ?? { size: 72, weight: 700, uppercase: false, trackingEm: 0 };

  const rendered = props.lines.map((line, index) => {
    const style = props.lineStyles[index] ?? fallbackStyle;
    const font = fontFor(style);
    const fontSize = fitMarkupLine(line, font, maxWidth - 8);
    const start = appearFrame + index * motion.staggerFrames;
    const rising = props.entrance === "rise";
    return {
      key: index,
      line,
      style,
      fontSize,
      opacity: rising ? fadeIn(frame, start) : 1,
      offsetY: rising ? settleOffset(frame, start, motion.arriveFromOffsetPx) : 0,
    };
  });

  const blockHeight = rendered.reduce((sum, item) => sum + item.fontSize * 1.08, 0) + props.lineGapPx * (rendered.length - 1);
  const scrimBottom = props.top + blockHeight + 260;
  const scrimIn = props.entrance === "rise" ? fadeIn(frame, appearFrame, scrimFadeFrames) : 1;
  const scrimOpacity = props.scrim * scrimIn * visibility;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {props.scrim > 0 ? (
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 0,
            height: scrimBottom,
            opacity: scrimOpacity,
            background: `linear-gradient(180deg, rgba(8,16,36,0.92) 0%, rgba(8,16,36,0.78) 34%, rgba(8,16,36,0.42) 62%, rgba(8,16,36,0.14) 82%, rgba(8,16,36,0) 100%)`,
          }}
        />
      ) : null}
      <div
        style={{
          position: "absolute",
          left: zones.headline.x0,
          width: maxWidth,
          top: props.top,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: props.lineGapPx,
          opacity: visibility,
          transform: `translateY(${-exitDrift(leaving, 16)}px)`,
        }}
      >
        {rendered.map((item) => (
          <div
            key={item.key}
            style={{
              fontFamily: fontFamilies.sans,
              fontWeight: item.style.weight,
              fontSize: item.fontSize,
              lineHeight: 1.08,
              letterSpacing: `${item.style.trackingEm}em`,
              textTransform: item.style.uppercase ? "uppercase" : "none",
              color: textColor,
              whiteSpace: "nowrap",
              textAlign: "center",
              opacity: item.opacity,
              transform: `translateY(${item.offsetY}px)`,
              textShadow: `0 2px 3px rgba(8,16,36,0.55), 0 6px 22px rgba(8,16,36,0.5)`,
            }}
          >
            <AccentText text={item.line} accentColor={accentColor} accentScale={accentScale} style={{ whiteSpace: "nowrap" }} />
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

export default HookHeadline;
