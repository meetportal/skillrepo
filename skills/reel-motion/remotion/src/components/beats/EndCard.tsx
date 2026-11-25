import { measureText } from "@remotion/layout-utils";
import { AbsoluteFill, Easing, Img, interpolate, interpolateColors } from "remotion";
import { z } from "zod";
import { markupLineSchema } from "../../lib/beatSchemas";
import { colors, fontFamilies, layout, motion, surface, type as typeTokens } from "../../theme";
import type { BeatProps } from "../../types";
import { AccentText, entranceProgress } from "../ui";
import { fullFrameCenterX, fullFrameContentWidth, logoForCard, logoPopDefaults, logoPopGeometry, logoPopRadius } from "./brand-end/geometry";
import { logoRect, mixPlacement, placeLogoCentered, resolveLogoSrc, useLogoMeta, type LogoMeta, type LogoPlacement } from "./brand-end/logo";
import { fitMarkupSize, useBrandFontsReady } from "./brand-end/text";

const handoffSchema = z.object({
  card: z.enum(["cream", "navy"]).default(logoPopDefaults.card),
  logo: z.string().min(1).optional(),
  widthPx: z.number().min(360).max(880).default(logoPopDefaults.widthPx),
  centerY: z.number().default(logoPopDefaults.centerY),
});

export const schema = z.object({
  headline: z.array(markupLineSchema).min(1).max(2),
  url: z.string().min(1),
  sub: z.string().optional(),
  kicker: z.string().optional(),
  offer: z.string().optional(),
  logo: z.string().min(1).default("color"),
  logoWidthPx: z.number().min(280).max(880).default(640),
  wipeFrames: z.number().int().min(4).max(20).default(8),
  handoff: handoffSchema.nullable().default(handoffSchema.parse({})),
  urlAt: z.number().nonnegative().default(0.72),
  centerY: z.number().min(700).max(1100).default(870),
  headlineSizePx: z.number().min(52).max(96).default(68),
  urlSizePx: z.number().min(56).max(96).default(80),
});

export type EndCardProps = z.infer<typeof schema>;

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const easeInOut = Easing.bezier(0.65, 0, 0.35, 1);

const contentWidth = fullFrameContentWidth;
const contentLeft = fullFrameCenterX - contentWidth / 2;
const headlineLineHeight = 1.17;
const subSizePx = Math.max(typeTokens.cardMinPx, 44);
const offerSizePx = Math.max(typeTokens.cardMinPx, 44);
const kickerMaxPx = Math.max(typeTokens.cardMinPx, 44);
const kickerMinPx = 30;
const kickerTracking = "0.14em";
const pillPadY = 30;
const pillPadX = 60;
const pillRadius = 28;
const gaps = { logo: 96, kicker: 28, headline: 76, offer: 48, pill: 34 };
const finalHoldFrames = 24;
const wipeOverscanPx = 64;
const shineDelayFrames = 7;
const shineFrames = 13;
const riseFrames = motion.entranceFrames;
const navyHandoffFrames = 6;

const rgba = (hex: string, alpha: number) => {
  const value = Number.parseInt(hex.replace("#", "").slice(0, 6), 16);
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`;
};

const glowStops = (hex: string, strength: number) =>
  [
    `${rgba(hex, strength)} 0%`,
    `${rgba(hex, strength * 0.82)} 18%`,
    `${rgba(hex, strength * 0.52)} 38%`,
    `${rgba(hex, strength * 0.22)} 58%`,
    `${rgba(hex, strength * 0.06)} 76%`,
    `${rgba(hex, 0)} 90%`,
  ].join(", ");

const rise = (frame: number, start: number) => {
  const p = entranceProgress(frame, start, riseFrames);
  return {
    opacity: interpolate(p, [0, 0.45], [0, 1], clamp),
    transform: `translateY(${Math.round((1 - p) * motion.arriveFromOffsetPx)}px)`,
  };
};

const LogoLayer = ({ src, meta, placement, opacity }: { src: string; meta: LogoMeta; placement: LogoPlacement; opacity: number }) => {
  if (opacity <= 0) {
    return null;
  }
  const rect = logoRect(meta, placement);
  return <Img src={src} style={{ position: "absolute", left: rect.left, top: rect.top, width: rect.width, height: rect.height, opacity }} />;
};

const EndCard = ({ props, frame, fps, durationInFrames }: BeatProps<EndCardProps>) => {
  const ready = useBrandFontsReady();
  const endSrc = resolveLogoSrc(props.logo);
  const popSrc = resolveLogoSrc(props.handoff ? (props.handoff.logo ?? logoForCard(props.handoff.card)) : props.logo);
  const endMeta = useLogoMeta(endSrc);
  const popMeta = useLogoMeta(popSrc);
  if (!endMeta || !popMeta) {
    return null;
  }

  const headlineSize = fitMarkupSize(props.headline, {
    maxWidth: contentWidth - 24,
    maxSize: props.headlineSizePx,
    minSize: 52,
    ready,
    font: { weight: 700, accentScale: 1.08 },
  });
  const urlSize = (() => {
    if (!ready) {
      return props.urlSizePx;
    }
    for (let size = props.urlSizePx; size > 56; size -= 1) {
      const width = measureText({ text: props.url, fontFamily: fontFamilies.sans, fontSize: size, fontWeight: 800, letterSpacing: "-0.01em", validateFontIsLoaded: true }).width;
      if (width + pillPadX * 2 <= contentWidth) {
        return size;
      }
    }
    return 56;
  })();

  const kickerSizePx = (() => {
    if (!ready || !props.kicker) {
      return kickerMaxPx;
    }
    for (let size = kickerMaxPx; size > kickerMinPx; size -= 1) {
      const width = measureText({ text: props.kicker, fontFamily: fontFamilies.sans, fontSize: size, fontWeight: 600, letterSpacing: kickerTracking, validateFontIsLoaded: true }).width;
      if (width <= contentWidth) {
        return size;
      }
    }
    return kickerMinPx;
  })();
  const offerLines =
    ready && props.offer && measureText({ text: props.offer, fontFamily: fontFamilies.sans, fontSize: offerSizePx, fontWeight: 500, validateFontIsLoaded: true }).width > contentWidth ? 2 : 1;

  const logoHeight = (props.logoWidthPx * endMeta.height) / endMeta.width;
  const headlineHeight = props.headline.length * headlineSize * headlineLineHeight;
  const pillHeight = Math.round(urlSize * 1.1 + pillPadY * 2);
  const blocks = [
    { key: "logo", height: logoHeight, gap: gaps.logo },
    ...(props.kicker ? [{ key: "kicker", height: kickerSizePx * 1.2, gap: gaps.kicker }] : []),
    { key: "headline", height: headlineHeight, gap: gaps.headline },
    ...(props.offer ? [{ key: "offer", height: offerSizePx * 1.25 * offerLines, gap: gaps.offer }] : []),
    { key: "pill", height: pillHeight, gap: props.sub ? gaps.pill : 0 },
    ...(props.sub ? [{ key: "sub", height: subSizePx * 1.2, gap: 0 }] : []),
  ];
  const stackHeight = blocks.reduce((sum, block) => sum + block.height + block.gap, 0);
  const topsByKey = new Map<string, number>();
  blocks.reduce((y, block) => {
    topsByKey.set(block.key, Math.round(y));
    return y + block.height + block.gap;
  }, props.centerY - stackHeight / 2);
  const topOf = (key: string) => topsByKey.get(key) ?? 0;

  const endPlacement = placeLogoCentered(endMeta, fullFrameCenterX, topOf("logo") + logoHeight / 2, props.logoWidthPx);
  const popGeometry = props.handoff ? logoPopGeometry(popMeta, props.handoff.widthPx, props.handoff.centerY) : null;
  const wipe = interpolate(frame + 1, [0, props.wipeFrames], [0, 1], { ...clamp, easing: motion.ease });
  const travel = interpolate(frame + 1, [0, props.wipeFrames + 3], [0, 1], { ...clamp, easing: motion.ease });

  const from = popGeometry?.card ?? { x0: 0, x1: layout.width, y0: layout.height, y1: layout.height };
  const towardsEdge = (gap: number) => gap * (1 - wipe) - wipeOverscanPx * wipe;
  const inset = {
    top: towardsEdge(from.y0),
    right: towardsEdge(layout.width - from.x1),
    bottom: towardsEdge(layout.height - from.y1),
    left: towardsEdge(from.x0),
  };
  const radius = (popGeometry ? logoPopRadius : 48) * (1 - wipe);
  const clipPath = `inset(${inset.top}px ${inset.right}px ${inset.bottom}px ${inset.left}px round ${radius}px)`;

  const contentStart = Math.max(0, props.wipeFrames - 2);
  const order = [props.kicker ? "kicker" : null, ...props.headline.map((_, index) => `headline${index}`), props.offer ? "offer" : null].filter(
    (key): key is string => key !== null,
  );
  const startOf = (key: string) => contentStart + order.indexOf(key) * motion.staggerFrames;
  const lastTextStart = contentStart + (order.length - 1) * motion.staggerFrames;
  const urlFrame = Math.min(Math.max(Math.round(props.urlAt * fps), lastTextStart + 3), durationInFrames - finalHoldFrames);
  const pillProgress = entranceProgress(frame, urlFrame);
  const pillOpacity = interpolate(frame, [urlFrame, urlFrame + 3], [0, 1], clamp);
  const pillScale = 1 + (motion.arriveFromScale - 1) * (1 - pillProgress);
  const shine = interpolate(frame, [urlFrame + shineDelayFrames, urlFrame + shineDelayFrames + shineFrames], [0, 1], { ...clamp, easing: easeInOut });
  const subStyle = rise(frame, urlFrame + 4);
  const drift = interpolate(frame, [0, durationInFrames], [0, 1], clamp);
  const logoOwnEntrance = popGeometry ? null : rise(frame, contentStart);

  const startPlacement = popGeometry?.logo ?? endPlacement;
  const placement = mixPlacement(startPlacement, endPlacement, travel);
  const sameLogo = endSrc === popSrc;
  const fromNavy = props.handoff?.card === "navy";
  const navyFade = 1 - interpolate(frame, [1, navyHandoffFrames], [0, 1], { ...clamp, easing: easeInOut });
  const endLogoOpacity = sameLogo ? 1 : fromNavy ? 1 - navyFade : interpolate(travel, [0, 0.3], [0, 1], clamp);
  const popLogoOpacity = sameLogo ? 0 : fromNavy ? navyFade : 1 - interpolate(travel, [0.2, 0.45], [0, 1], clamp);
  const navyHandoff = fromNavy ? navyFade : 0;
  const goldTop = interpolateColors(0.35, [0, 1], [colors.ctaGold, "#FFFFFF"]);
  const goldBottom = interpolateColors(0.06, [0, 1], [colors.ctaGold, "#B08800"]);

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {popGeometry && Math.min(inset.top, inset.left, inset.right, inset.bottom) > 0 ? (
        <div
          style={{
            position: "absolute",
            left: inset.left,
            top: inset.top,
            right: inset.right,
            bottom: inset.bottom,
            borderRadius: radius,
            boxShadow: "0 34px 70px -18px rgba(4,8,20,0.62), 0 14px 28px -10px rgba(4,8,20,0.42)",
            opacity: 1 - wipe,
          }}
        />
      ) : null}
      <AbsoluteFill style={{ clipPath, backgroundColor: colors.cream }}>
        <AbsoluteFill
          style={{
            background: [
              `radial-gradient(940px 940px at ${980 - drift * 26}px ${170 + drift * 18}px, ${glowStops(colors.creamGlowBlue, 0.8)})`,
              `radial-gradient(1000px 1000px at ${110 + drift * 24}px ${1760 - drift * 16}px, ${glowStops(colors.creamGlowPeach, 0.95)})`,
              `linear-gradient(180deg, ${rgba("#FFFFFF", 0.22)} 0%, ${rgba("#FFFFFF", 0)} 40%)`,
            ].join(", "),
          }}
        />
        {navyHandoff > 0 ? <AbsoluteFill style={{ background: surface.cardGradient, opacity: navyHandoff }} /> : null}
        <AbsoluteFill style={logoOwnEntrance ? { opacity: logoOwnEntrance.opacity, transform: logoOwnEntrance.transform } : undefined}>
          {sameLogo ? null : <LogoLayer src={popSrc} meta={popMeta} placement={placement} opacity={popLogoOpacity} />}
          <LogoLayer src={endSrc} meta={endMeta} placement={placement} opacity={endLogoOpacity} />
        </AbsoluteFill>
        {props.kicker ? (
          <div
            style={{
              position: "absolute",
              left: contentLeft,
              width: contentWidth,
              top: topOf("kicker"),
              textAlign: "center",
              fontFamily: fontFamilies.sans,
              fontWeight: 600,
              fontSize: kickerSizePx,
              lineHeight: 1.2,
              letterSpacing: kickerTracking,
              whiteSpace: "nowrap",
              color: colors.brandOrange,
              ...rise(frame, startOf("kicker")),
            }}
          >
            {props.kicker}
          </div>
        ) : null}
        {props.headline.map((line, index) => (
          <div
            key={line}
            style={{
              position: "absolute",
              left: contentLeft,
              width: contentWidth,
              top: topOf("headline") + index * headlineSize * headlineLineHeight,
              height: headlineSize * headlineLineHeight,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: fontFamilies.sans,
              fontWeight: 700,
              fontSize: headlineSize,
              lineHeight: headlineLineHeight,
              letterSpacing: "-0.012em",
              color: colors.ink,
              whiteSpace: "nowrap",
              ...rise(frame, startOf(`headline${index}`)),
            }}
          >
            <AccentText text={line} accentColor={colors.brandOrange} accentScale={1.08} />
          </div>
        ))}
        {props.offer ? (
          <div
            style={{
              position: "absolute",
              left: contentLeft,
              width: contentWidth,
              top: topOf("offer"),
              textAlign: "center",
              fontFamily: fontFamilies.sans,
              fontWeight: 500,
              fontSize: offerSizePx,
              lineHeight: 1.25,
              textWrap: "balance",
              color: colors.taglineGray,
              ...rise(frame, startOf("offer")),
            }}
          >
            {props.offer}
          </div>
        ) : null}
        <div
          style={{
            position: "absolute",
            left: contentLeft,
            width: contentWidth,
            top: topOf("pill"),
            height: pillHeight,
            display: "flex",
            justifyContent: "center",
            opacity: pillOpacity,
            transform: `scale(${pillScale})`,
            transformOrigin: `${contentWidth / 2}px ${pillHeight / 2}px`,
          }}
        >
          <div
            style={{
              position: "relative",
              height: pillHeight,
              boxSizing: "border-box",
              padding: `0 ${pillPadX}px`,
              display: "flex",
              alignItems: "center",
              borderRadius: pillRadius,
              overflow: "hidden",
              background: `linear-gradient(180deg, ${goldTop} 0%, ${colors.ctaGold} 46%, ${goldBottom} 100%)`,
              border: `1px solid ${rgba(colors.ctaInk, 0.1)}`,
              boxShadow: [
                `0 26px 44px -18px ${rgba("#8A6A00", 0.55 * pillProgress)}`,
                `0 6px 14px -4px ${rgba(colors.ctaInk, 0.16)}`,
                `inset 0 1px 0 ${rgba("#FFFFFF", 0.7)}`,
                `inset 0 -2px 0 ${rgba("#000000", 0.05)}`,
              ].join(", "),
            }}
          >
            <span
              style={{
                fontFamily: fontFamilies.sans,
                fontWeight: 800,
                fontSize: urlSize,
                lineHeight: 1,
                letterSpacing: "-0.01em",
                color: colors.ctaInk,
                whiteSpace: "nowrap",
                transform: `translateY(${Math.round(urlSize * 0.04)}px)`,
              }}
            >
              {props.url}
            </span>
            {shine > 0 && shine < 1 ? (
              <div
                style={{
                  position: "absolute",
                  top: -20,
                  bottom: -20,
                  width: "38%",
                  left: `${-45 + shine * 160}%`,
                  transform: "skewX(-18deg)",
                  background: `linear-gradient(90deg, ${rgba("#FFFFFF", 0)} 0%, ${rgba("#FFFFFF", 0.55)} 50%, ${rgba("#FFFFFF", 0)} 100%)`,
                }}
              />
            ) : null}
          </div>
        </div>
        {props.sub ? (
          <div
            style={{
              position: "absolute",
              left: contentLeft,
              width: contentWidth,
              top: topOf("sub"),
              textAlign: "center",
              fontFamily: fontFamilies.sans,
              fontWeight: 500,
              fontSize: subSizePx,
              lineHeight: 1.2,
              color: colors.taglineGray,
              ...subStyle,
            }}
          >
            {props.sub}
          </div>
        ) : null}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export default EndCard;
