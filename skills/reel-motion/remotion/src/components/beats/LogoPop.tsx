import { AbsoluteFill, Img, interpolate, interpolateColors } from "remotion";
import { z } from "zod";
import { brand } from "../../lib/brand";
import { colors, layout, motion, surface } from "../../theme";
import type { BeatProps } from "../../types";
import { entranceProgress, exitProgress, stampScale } from "../ui";
import { logoForCard, logoPopDefaults, logoPopGeometry, logoPopRadius } from "./brand-end/geometry";
import { logoRect, resolveLogoSrc, useLogoMeta } from "./brand-end/logo";

export const schema = z.object({
  logo: z.string().min(1).optional(),
  card: z.enum(["cream", "navy"]).default(logoPopDefaults.card),
  widthPx: z.number().min(360).max(880).default(logoPopDefaults.widthPx),
  centerY: z.number().min(layout.safe.y0 + 120).max(layout.safe.y1 - 120).default(logoPopDefaults.centerY),
  popAt: z.number().nonnegative().default(0),
  markSplit: z.number().gt(0).lt(1).nullable().default(brand.logoMark.iconSplit),
  exit: z.enum(["handoff", "fade"]).default("handoff"),
});

export type LogoPopProps = z.infer<typeof schema>;

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const markLeadFrames = 1;
const wordmarkLeadFrames = 3;
const wordmarkFrames = 10;
const wordmarkTravelPx = 44;

const cardSkins = {
  cream: {
    background: `linear-gradient(180deg, ${interpolateColors(0.55, [0, 1], [colors.cream, "#FFFFFF"])} 0%, ${colors.cream} 100%)`,
    border: "rgba(20,24,40,0.10)",
    shadow:
      "0 34px 70px -18px rgba(4,8,20,0.62), 0 14px 28px -10px rgba(4,8,20,0.42), inset 0 1px 0 rgba(255,255,255,0.95), inset 0 -1px 0 rgba(20,24,40,0.05)",
  },
  navy: {
    background: surface.cardGradient,
    border: colors.border,
    shadow: `${surface.cardShadow}, inset 0 1px 0 rgba(255,255,255,0.07)`,
  },
};

const LogoPop = ({ props, frame, fps, durationInFrames }: BeatProps<LogoPopProps>) => {
  const src = resolveLogoSrc(props.logo ?? logoForCard(props.card));
  const meta = useLogoMeta(src);
  if (!meta) {
    return null;
  }
  const geometry = logoPopGeometry(meta, props.widthPx, props.centerY);
  const rect = logoRect(meta, geometry.logo);
  const start = Math.round(props.popAt * fps);
  const cardProgress = entranceProgress(frame, start);
  const exit = props.exit === "fade" ? exitProgress(frame, durationInFrames) : 0;
  const cardOpacity = interpolate(frame, [start, start + 2], [0, 1], clamp) * (1 - exit);
  const lift = Math.round((1 - cardProgress) * motion.arriveFromOffsetPx + exit * 16);
  const skin = cardSkins[props.card];
  const card = geometry.card;

  const imageStyle = { position: "absolute" as const, left: 0, top: 0, width: rect.width, height: rect.height };
  const logoBox = { position: "absolute" as const, left: rect.left, top: rect.top, width: rect.width, height: rect.height };

  const renderLogo = () => {
    if (props.markSplit === null) {
      const p = entranceProgress(frame, start + markLeadFrames);
      return (
        <div
          style={{
            ...logoBox,
            opacity: interpolate(p, [0, 0.5], [0, 1], clamp),
            transform: `scale(${1 + 0.06 * (1 - p)})`,
          }}
        >
          <Img src={src} style={imageStyle} />
        </div>
      );
    }
    const splitPct = props.markSplit * 100;
    const markStart = start + markLeadFrames;
    const markOpacity = interpolate(frame, [markStart, markStart + 2], [0, 1], clamp);
    const wordStart = start + wordmarkLeadFrames;
    const wordProgress = interpolate(frame, [wordStart, wordStart + wordmarkFrames], [0, 1], { ...clamp, easing: motion.ease });
    return (
      <>
        <div
          style={{
            ...logoBox,
            clipPath: `inset(-20% ${100 - splitPct}% -20% -20%)`,
            opacity: markOpacity,
            transform: `scale(${stampScale(frame, markStart)})`,
            transformOrigin: `${splitPct / 2}% 50%`,
          }}
        >
          <Img src={src} style={imageStyle} />
        </div>
        <div style={{ ...logoBox, clipPath: `inset(-20% -20% -20% ${splitPct}%)` }}>
          <div
            style={{
              ...imageStyle,
              opacity: interpolate(wordProgress, [0, 0.8], [0, 1], clamp),
              transform: `translateX(${-Math.round((1 - wordProgress) * wordmarkTravelPx)}px)`,
            }}
          >
            <Img src={src} style={imageStyle} />
          </div>
        </div>
      </>
    );
  };

  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity: cardOpacity, transform: `translateY(${lift}px)` }}>
      <div
        style={{
          position: "absolute",
          left: card.x0,
          top: card.y0,
          width: card.x1 - card.x0,
          height: card.y1 - card.y0,
          boxSizing: "border-box",
          borderRadius: logoPopRadius,
          background: skin.background,
          border: `1px solid ${skin.border}`,
          boxShadow: skin.shadow,
        }}
      />
      {renderLogo()}
    </AbsoluteFill>
  );
};

export default LogoPop;
