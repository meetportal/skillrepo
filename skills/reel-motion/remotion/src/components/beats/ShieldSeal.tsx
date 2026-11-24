import { useId } from "react";
import { AbsoluteFill, Easing, interpolate, interpolateColors } from "remotion";
import { z } from "zod";
import { timeSchema, toneSchema } from "../../lib/beatSchemas";
import { colors, fontFamilies, layout, motion, type as typeTokens, zones } from "../../theme";
import type { BeatProps } from "../../types";
import { entranceProgress, entranceStyle, exitProgress, Icon, stampScale, toneColor } from "../ui";
import { alpha, clampRange, fitLines, mixHex, SurfacePanel, useFontsLoaded } from "./titles-rail/shared";

export const schema = z.object({
  domain: z.string().min(1),
  sealAt: timeSchema,
  kicker: z.string().default("PROTECTED"),
  tone: toneSchema.default("success"),
  domainSizePx: z.number().min(44).max(80).default(54),
  enterMode: z.enum(["card", "content"]).default("card"),
});

export type ShieldSealProps = z.infer<typeof schema>;

const shieldPath = "M50 5 L88 18.5 V52 C88 78 71 96 50 106 C29 96 12 78 12 52 V18.5 Z";
const checkPath = "M33 55 L45.5 67.5 L69 42";
const checkLength = 52;
const shieldW = 176;
const shieldH = shieldW * 1.1;
const padX = 52;
const columnGap = 44;

const Shield = ({ frame, sealFrame, color }: { frame: number; sealFrame: number; color: string }) => {
  const sealed = frame >= sealFrame;
  const scale = stampScale(frame, sealFrame);
  const solid = interpolate(frame, [sealFrame, sealFrame + 2], [0, 1], clampRange);
  const check = interpolate(frame, [sealFrame + 2, sealFrame + 9], [0, 1], { ...clampRange, easing: Easing.inOut(Easing.cubic) });
  const ghost = entranceProgress(frame, 0) * (1 - solid);
  const ring = interpolate(frame, [sealFrame + 3, sealFrame + 13], [0, 1], clampRange);
  const deep = mixHex(color, colors.navyBottom, 0.38);
  const gradientId = `shield-fill-${useId().replace(/:/g, "")}`;
  return (
    <div style={{ position: "relative", width: shieldW, height: shieldH }}>
      {ring > 0 && ring < 1 ? (
        <svg
          width={shieldW}
          height={shieldH}
          viewBox="0 0 100 110"
          style={{
            position: "absolute",
            inset: 0,
            overflow: "visible",
            opacity: interpolate(ring, [0, 0.15, 1], [0, 0.6, 0], { ...clampRange, easing: Easing.out(Easing.quad) }),
            transform: `scale(${interpolate(ring, [0, 1], [1.04, 1.6], { ...clampRange, easing: Easing.out(Easing.cubic) })})`,
          }}
        >
          <path d={shieldPath} fill="none" stroke={color} strokeWidth={2} />
        </svg>
      ) : null}
      <svg width={shieldW} height={shieldH} viewBox="0 0 100 110" style={{ position: "absolute", inset: 0, opacity: ghost * 0.7, overflow: "visible" }}>
        <path d={shieldPath} fill={alpha(colors.text, 0.04)} stroke={alpha(colors.text, 0.45)} strokeWidth={2} strokeDasharray="5 5" strokeLinejoin="round" />
      </svg>
      {sealed ? (
        <svg
          width={shieldW}
          height={shieldH}
          viewBox="0 0 100 110"
          style={{
            position: "absolute",
            inset: 0,
            overflow: "visible",
            opacity: solid,
            transform: `scale(${scale})`,
            filter: `drop-shadow(0 10px 22px ${alpha(color, 0.35)}) drop-shadow(0 4px 8px rgba(0,0,0,0.45))`,
          }}
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} />
              <stop offset="100%" stopColor={deep} />
            </linearGradient>
          </defs>
          <path d={shieldPath} fill={`url(#${gradientId})`} stroke={alpha(colors.text, 0.35)} strokeWidth={1.2} strokeLinejoin="round" />
          <path d="M50 11 L82 22.5 V30 C64 26 36 26 18 30 V22.5 Z" fill={alpha(colors.text, 0.12)} />
          <path
            d={checkPath}
            fill="none"
            stroke={colors.text}
            strokeWidth={8}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={checkLength}
            strokeDashoffset={checkLength * (1 - check)}
            opacity={check > 0.02 ? 1 : 0}
          />
        </svg>
      ) : null}
    </div>
  );
};

const ShieldSeal = ({ props, frame, durationInFrames, toFrame }: BeatProps<ShieldSealProps>) => {
  const ready = useFontsLoaded();
  const color = toneColor(props.tone);
  const sealFrame = toFrame(props.sealAt);
  const box = zones.card;
  const textWidth = box.x1 - box.x0 - padX * 2 - shieldW - columnGap;
  const domainFit = fitLines({
    text: props.domain,
    maxWidth: textWidth - 56,
    maxSize: props.domainSizePx,
    minSize: typeTokens.cardMinPx,
    fontWeight: 600,
    maxLines: 1,
    ready,
  });
  const exit = exitProgress(frame, durationInFrames);
  const cardP = props.enterMode === "card" ? entranceProgress(frame, 0) : 1;
  const cardOpacity = interpolate(cardP, [0, 0.45], [0, 1], clampRange) * (1 - exit);
  const cardLift = (1 - cardP) * motion.arriveFromOffsetPx + exit * 12;
  const sealP = interpolate(frame, [sealFrame, sealFrame + 6], [0, 1], { ...clampRange, easing: Easing.out(Easing.cubic) });
  const borderColor = interpolateColors(sealP, [0, 1], [colors.border, alpha(color, 0.7)]);
  const chip = entranceStyle(frame, { start: props.enterMode === "card" ? 2 : 0, from: "left" });
  const kicker = entranceStyle(frame, { start: sealFrame + 2, from: "up" });
  const chipBorder = interpolateColors(sealP, [0, 1], [alpha(colors.text, 0.18), alpha(color, 0.85)]);
  const chipFill = interpolateColors(sealP, [0, 1], [colors.navyTile, mixHex(colors.navyTile, color, 0.14)]);
  const iconColor = interpolateColors(sealP, [0, 1], [colors.muted, color]);
  const contentOpacity = 1 - exit;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{ position: "absolute", inset: 0, opacity: cardOpacity, transform: `translateY(${cardLift}px)` }}>
        <SurfacePanel box={box} borderColor={borderColor} glow={`0 0 48px ${alpha(color, 0.18 * sealP)}`}>
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: `radial-gradient(40% 70% at ${padX + shieldW / 2}px 50%, ${alpha(color, 0.16 * sealP)} 0%, ${alpha(color, 0)} 100%)`,
            }}
          />
        </SurfacePanel>
      </div>
      <div
        style={{
          position: "absolute",
          left: box.x0 + padX,
          right: layoutRight(box.x1, padX),
          top: box.y0,
          height: box.y1 - box.y0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: columnGap,
          opacity: contentOpacity,
          transform: `translateY(${cardLift}px)`,
        }}
      >
        <Shield frame={frame} sealFrame={sealFrame} color={color} />
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 22 }}>
          <div
            style={{
              fontFamily: fontFamilies.sans,
              fontWeight: 600,
              fontSize: 44,
              lineHeight: 1,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              color,
              opacity: kicker.opacity,
              transform: kicker.transform,
            }}
          >
            {props.kicker}
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              padding: "18px 30px 18px 22px",
              borderRadius: 999,
              background: chipFill,
              border: `2px solid ${chipBorder}`,
              boxShadow: `0 6px 18px rgba(0,0,0,0.35), 0 0 24px ${alpha(color, 0.25 * sealP)}`,
              opacity: chip.opacity,
              transform: chip.transform,
            }}
          >
            <Icon name="globe" size={Math.round(domainFit.fontSize * 0.8)} color={iconColor} strokeWidth={2} />
            <div
              style={{
                fontFamily: fontFamilies.sans,
                fontWeight: 600,
                fontSize: domainFit.fontSize,
                lineHeight: 1,
                color: colors.text,
                whiteSpace: "nowrap",
              }}
            >
              {props.domain}
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const layoutRight = (x1: number, pad: number) => layout.width - x1 + pad;

export default ShieldSeal;
