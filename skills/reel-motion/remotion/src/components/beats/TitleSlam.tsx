import { AbsoluteFill, Easing, interpolate } from "remotion";
import { z } from "zod";
import { toneSchema } from "../../lib/beatSchemas";
import { colors, fontFamilies, layout, motion, surface, type as typeTokens, zones } from "../../theme";
import type { BeatProps } from "../../types";
import { combineMotion, entranceProgress, entranceStyle, exitProgress, exitStyle, toneColor } from "../ui";
import { alpha, clampRange, fitLines, measureWidth, panelBackground, SurfacePanel, useFontsLoaded } from "./titles-rail/shared";

export const schema = z.object({
  variant: z.enum(["band", "takeover"]).default("band"),
  kicker: z.string().optional(),
  numeral: z.string().optional(),
  title: z.string().min(1),
  tone: toneSchema.default("accent"),
  titleSizePx: z.number().min(44).max(140).default(typeTokens.slam.fontSize),
  numeralSizePx: z.number().min(140).max(420).default(300),
  bandTop: z.number().default(zones.card.y0),
  bandHeight: z.number().min(160).max(330).default(250),
  takeoverCenterY: z.number().default(740),
  cutIn: z.boolean().default(true),
});

export type TitleSlamProps = z.infer<typeof schema>;

const kickerPx = 44;
const kickerTracking = 0.2;
const bandPadX = 56;
const accentBarPx = 6;

const Band = ({ props, frame, durationInFrames, ready }: { props: TitleSlamProps; frame: number; durationInFrames: number; ready: boolean }) => {
  const accent = toneColor(props.tone);
  const box = { x0: zones.card.x0, x1: zones.card.x1, y0: props.bandTop, y1: props.bandTop + props.bandHeight };
  const innerWidth = box.x1 - box.x0 - bandPadX * 2 - accentBarPx - 28;
  const numeralPx = props.numeral ? Math.max(typeTokens.numeralMinPx, Math.min(props.numeralSizePx, props.bandHeight - 20)) : 0;
  const numeralWidth = props.numeral ? measureWidth(props.numeral, numeralPx, 800, -0.04, ready) : 0;
  const numeralBleed = numeralWidth * 0.18;
  const numeralReserve = props.numeral ? numeralWidth - numeralBleed - bandPadX + 28 : 0;
  const titleFit = fitLines({
    text: props.title,
    maxWidth: innerWidth - numeralReserve,
    maxSize: props.titleSizePx,
    minSize: typeTokens.cardMinPx + 16,
    fontWeight: 800,
    letterSpacingEm: -0.01,
    maxLines: 2,
    ready,
  });
  const panel = combineMotion(entranceStyle(frame, { from: "up" }), exitStyle(frame, durationInFrames, { to: "none" }));
  const panelLift = (1 - entranceProgress(frame, 0)) * motion.arriveFromOffsetPx;
  const kicker = entranceStyle(frame, { start: 1, from: "left" });
  const title = entranceStyle(frame, { start: 2, from: "scale" });
  const exitP = exitProgress(frame, durationInFrames);
  const contentExit = { opacity: 1 - exitP, transform: `translateY(${-exitP * 14}px)` };
  const sheen = interpolate(frame, [2, 14], [-0.4, 1.4], { ...clampRange, easing: Easing.inOut(Easing.cubic) });
  const barP = interpolate(frame, [1, 7], [0, 1], { ...clampRange, easing: Easing.bezier(0.16, 1, 0.3, 1) });
  const numeralIn = entranceStyle(frame, { start: 2, from: "right" });
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{ position: "absolute", inset: 0, opacity: panel.opacity, transform: `translateY(${panelLift}px) ${exitP > 0 ? `scale(${1 - exitP * 0.03})` : ""}` }}>
        <SurfacePanel box={box} radius={surface.cardRadius - 4}>
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: `linear-gradient(105deg, ${alpha(colors.text, 0)} ${sheen * 100 - 18}%, ${alpha(colors.text, 0.07)} ${sheen * 100}%, ${alpha(colors.text, 0)} ${sheen * 100 + 18}%)`,
            }}
          />
          {props.numeral ? (
            <div
              style={{
                position: "absolute",
                right: -numeralBleed,
                top: "50%",
                marginTop: -numeralPx * 0.5,
                fontFamily: fontFamilies.sans,
                fontWeight: 800,
                fontSize: numeralPx,
                lineHeight: 1,
                letterSpacing: "-0.04em",
                fontVariantNumeric: "tabular-nums",
                color: alpha(accent, 0.1),
                WebkitTextStroke: `2px ${alpha(accent, 0.85)}`,
                opacity: numeralIn.opacity * contentExit.opacity,
                transform: numeralIn.transform,
              }}
            >
              {props.numeral}
            </div>
          ) : null}
          <div
            style={{
              position: "absolute",
              left: bandPadX - 18,
              top: props.bandHeight * 0.2,
              width: accentBarPx,
              height: props.bandHeight * 0.6,
              borderRadius: accentBarPx,
              background: accent,
              boxShadow: `0 0 18px ${alpha(accent, 0.55)}`,
              transformOrigin: "50% 0%",
              transform: `scaleY(${0.35 + 0.65 * barP})`,
              opacity: barP,
            }}
          />
          <div
            style={{
              position: "absolute",
              left: bandPadX + accentBarPx,
              right: bandPadX,
              top: 0,
              bottom: 0,
              display: "flex",
              alignItems: "center",
              gap: 36,
              opacity: contentExit.opacity,
              transform: contentExit.transform,
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {props.kicker ? (
                <div
                  style={{
                    fontFamily: fontFamilies.sans,
                    fontWeight: 600,
                    fontSize: kickerPx,
                    letterSpacing: `${kickerTracking}em`,
                    lineHeight: 1,
                    color: accent,
                    textTransform: "uppercase",
                    opacity: kicker.opacity,
                    transform: kicker.transform,
                  }}
                >
                  {props.kicker}
                </div>
              ) : null}
              <div
                style={{
                  fontFamily: fontFamilies.sans,
                  fontWeight: 800,
                  fontSize: titleFit.fontSize,
                  lineHeight: 1.02,
                  letterSpacing: "-0.01em",
                  color: colors.text,
                  textTransform: "uppercase",
                  transformOrigin: "0% 50%",
                  opacity: title.opacity,
                  transform: title.transform,
                }}
              >
                {titleFit.lines.map((line) => (
                  <div key={line} style={{ whiteSpace: "nowrap" }}>
                    {line}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </SurfacePanel>
      </div>
    </AbsoluteFill>
  );
};

const Takeover = ({ props, frame, durationInFrames, ready }: { props: TitleSlamProps; frame: number; durationInFrames: number; ready: boolean }) => {
  const accent = toneColor(props.tone);
  const width = zones.safe.x1 - zones.safe.x0;
  const numeralPx = Math.max(typeTokens.numeralMinPx, props.numeralSizePx);
  const titleFit = fitLines({
    text: props.title,
    maxWidth: width,
    maxSize: props.titleSizePx,
    minSize: typeTokens.cardMinPx + 16,
    fontWeight: 800,
    letterSpacingEm: -0.01,
    maxLines: 2,
    ready,
  });
  const bgIn = props.cutIn ? 1 : interpolate(frame, [0, 4], [0, 1], clampRange);
  const bgOut = interpolate(frame, [durationInFrames - 4, durationInFrames], [1, 0], { ...clampRange, easing: Easing.inOut(Easing.quad) });
  const exitP = interpolate(frame, [durationInFrames - 7, durationInFrames - 3], [0, 1], { ...clampRange, easing: Easing.in(Easing.quad) });
  const contentExit = { opacity: 1 - exitP, transform: `scale(${1 - exitP * 0.04})` };
  const kicker = entranceStyle(frame, { start: 0, from: "up" });
  const numeral = entranceStyle(frame, { start: 0, from: "scale" });
  const title = entranceStyle(frame, { start: 3, from: "up" });
  const rule = interpolate(frame, [4, 12], [0, 1], { ...clampRange, easing: Easing.bezier(0.16, 1, 0.3, 1) });
  const glowScale = interpolate(frame, [0, 14], [0.92, 1], { ...clampRange, easing: Easing.out(Easing.cubic) });
  const centerX = (zones.safe.x0 + zones.safe.x1) / 2;
  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity: bgIn * bgOut }}>
      <AbsoluteFill style={{ background: panelBackground }} />
      <AbsoluteFill
        style={{
          background: `radial-gradient(46% 26% at ${(centerX / layout.width) * 100}% ${(props.takeoverCenterY / layout.height) * 100}%, ${alpha(accent, 0.2)} 0%, ${alpha(accent, 0)} 100%)`,
          transform: `scale(${glowScale})`,
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(${alpha(colors.text, 0.035)} 1px, transparent 1px), linear-gradient(90deg, ${alpha(colors.text, 0.035)} 1px, transparent 1px)`,
          backgroundSize: "88px 88px",
          backgroundPosition: `${zones.safe.x0}px 0px`,
          maskImage: `radial-gradient(60% 40% at 50% ${(props.takeoverCenterY / layout.height) * 100}%, black 0%, transparent 100%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: zones.safe.x0,
          width,
          top: props.takeoverCenterY,
          transform: `translateY(-50%) ${contentExit.transform}`,
          opacity: contentExit.opacity,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
        }}
      >
        {props.kicker ? (
          <div
            style={{
              fontFamily: fontFamilies.sans,
              fontWeight: 600,
              fontSize: kickerPx,
              letterSpacing: `${kickerTracking}em`,
              marginRight: `-${kickerTracking}em`,
              lineHeight: 1,
              color: colors.muted,
              textTransform: "uppercase",
              marginBottom: 8,
              opacity: kicker.opacity,
              transform: kicker.transform,
            }}
          >
            {props.kicker}
          </div>
        ) : null}
        {props.numeral ? (
          <div
            style={{
              fontFamily: fontFamilies.sans,
              fontWeight: 800,
              fontSize: numeralPx,
              lineHeight: 1,
              letterSpacing: "-0.045em",
              marginRight: "-0.045em",
              fontVariantNumeric: "tabular-nums",
              color: accent,
              textShadow: `0 12px 48px ${alpha(accent, 0.28)}`,
              opacity: numeral.opacity,
              transform: numeral.transform,
            }}
          >
            {props.numeral}
          </div>
        ) : null}
        <div
          style={{
            width: 120,
            height: 4,
            borderRadius: 4,
            margin: "18px 0 34px",
            background: accent,
            opacity: rule,
            transform: `scaleX(${0.3 + 0.7 * rule})`,
          }}
        />
        <div
          style={{
            fontFamily: fontFamilies.sans,
            fontWeight: 800,
            fontSize: titleFit.fontSize,
            lineHeight: 1.04,
            letterSpacing: "-0.01em",
            color: colors.text,
            textTransform: "uppercase",
            opacity: title.opacity,
            transform: title.transform,
          }}
        >
          {titleFit.lines.map((line) => (
            <div key={line} style={{ whiteSpace: "nowrap" }}>
              {line}
            </div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const TitleSlam = ({ props, frame, durationInFrames }: BeatProps<TitleSlamProps>) => {
  const ready = useFontsLoaded();
  return props.variant === "takeover" ? (
    <Takeover props={props} frame={frame} durationInFrames={durationInFrames} ready={ready} />
  ) : (
    <Band props={props} frame={frame} durationInFrames={durationInFrames} ready={ready} />
  );
};

export default TitleSlam;
