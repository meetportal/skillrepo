import { AbsoluteFill, interpolate } from "remotion";
import { z } from "zod";
import { iconSchema, timeSchema, toneSchema } from "../../lib/beatSchemas";
import { colors, fontFamilies, motion, type as typeTokens, zones } from "../../theme";
import type { BeatProps } from "../../types";
import { Icon, toneColor, type IconName, type Tone } from "../ui";
import { arrive, capsEm, clamp, easeInOutCubic, fitFontPx, leave, panelSurface, ramp, relFrame, rgba } from "./mistake3/kit";

export const schema = z.object({
  labels: z.array(z.string().min(1)).min(1).max(4),
  enter: z.enum(["slam", "settled"]).default("slam"),
  slamTimes: z.array(timeSchema).default([]),
  slots: z.boolean().default(true),
  pill: z.string().min(1).optional(),
  pillTone: toneSchema.default("warning"),
  pillIcon: iconSchema.default("warning"),
  pillDelaySec: z.number().min(0).max(1).default(0.12),
  dnsLine: z.string().min(1).optional(),
  dnsAt: timeSchema.optional(),
  dnsSharpRatio: z.number().min(0).max(1).default(0.42),
  flipAt: timeSchema.optional(),
  flipLabel: z.string().min(1).default("FAIL"),
  flipTone: toneSchema.default("danger"),
  flipIcon: iconSchema.default("cross"),
  flipStaggerSec: z.number().min(0).max(0.5).default(0.12),
  labelPx: z.number().min(typeTokens.cardMinPx).max(96).default(72),
  pillPx: z.number().min(typeTokens.cardMinPx).max(60).default(44),
  exit: z.boolean().default(true),
});

export type AuthTilesProps = z.infer<typeof schema>;

const gapPx = 24;
const maxTileWidth = 300;
const tilePadY = 30;
const labelPillGap = 16;
const tileRadius = 30;
const dnsGap = 20;
const dnsFontPx = typeTokens.monoMinPx;
const dnsPadY = 12;
const flipFrames = 9;
const perspectivePx = 1400;

type Face = { label: string; pill?: string; tone: Tone; icon?: IconName; strong: boolean; compact: boolean };

const pillWidth = (text: string, fontSize: number, withIcon: boolean) =>
  Math.ceil(capsEm(text) * fontSize * 1.04 + fontSize * 0.72 + (withIcon ? fontSize * 0.84 : 0));

const StatusPill = ({ text, tone, icon, fontSize, strong, compact }: { text: string; tone: Tone; icon?: IconName; fontSize: number; strong: boolean; compact: boolean }) => {
  const color = toneColor(tone);
  if (compact && icon) {
    const size = Math.round(fontSize * 1.5);
    return (
      <div
        style={{
          width: size,
          height: size,
          borderRadius: "50%",
          boxSizing: "border-box",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: strong ? `linear-gradient(180deg, ${color} 0%, ${rgba(color, 0.86)} 100%)` : rgba(color, 0.13),
          border: `1px solid ${rgba(color, strong ? 1 : 0.55)}`,
          boxShadow: strong ? `0 6px 18px ${rgba(color, 0.35)}` : "none",
        }}
      >
        <Icon name={icon} size={Math.round(fontSize * 0.86)} color={strong ? colors.text : color} strokeWidth={2.6} />
      </div>
    );
  }
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: Math.round(fontSize * 0.22),
        height: Math.round(fontSize * 1.5),
        padding: `0 ${Math.round(fontSize * 0.36)}px`,
        borderRadius: 999,
        boxSizing: "border-box",
        background: strong ? `linear-gradient(180deg, ${color} 0%, ${rgba(color, 0.86)} 100%)` : rgba(color, 0.13),
        border: `1px solid ${rgba(color, strong ? 1 : 0.55)}`,
        boxShadow: strong ? `0 6px 18px ${rgba(color, 0.35)}, inset 0 1px 0 rgba(255,255,255,0.25)` : "none",
        color: strong ? colors.text : color,
        fontFamily: fontFamilies.sans,
        fontWeight: 700,
        fontSize,
        lineHeight: 1,
        letterSpacing: "0.03em",
        whiteSpace: "nowrap",
      }}
    >
      {icon ? <Icon name={icon} size={Math.round(fontSize * 0.62)} color={strong ? colors.text : color} strokeWidth={3.4} /> : null}
      <span style={{ transform: `translateY(${Math.round(fontSize * 0.04)}px)` }}>{text}</span>
    </div>
  );
};

const TileFace = ({
  face,
  width,
  height,
  labelPx,
  pillPx,
  pillOpacity,
  pillRise,
  glow,
}: {
  face: Face;
  width: number;
  height: number;
  labelPx: number;
  pillPx: number;
  pillOpacity: number;
  pillRise: number;
  glow: number;
}) => {
  const color = toneColor(face.tone);
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        width,
        height,
        boxSizing: "border-box",
        borderRadius: tileRadius,
        border: face.strong ? `1px solid ${rgba(color, 0.85)}` : panelSurface.border,
        background: `radial-gradient(120% 70% at 50% 0%, ${rgba(color, face.strong ? 0.2 : 0.07)} 0%, rgba(0,0,0,0) 70%), ${panelSurface.background}`,
        boxShadow: `${panelSurface.highlight}, ${panelSurface.shadow}${glow > 0 ? `, 0 0 ${Math.round(44 * glow)}px ${rgba(color, 0.5 * glow)}` : ""}`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: labelPillGap,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          fontFamily: fontFamilies.sans,
          fontWeight: 800,
          fontSize: labelPx,
          lineHeight: 1.05,
          letterSpacing: "-0.01em",
          color: colors.text,
          whiteSpace: "nowrap",
          textShadow: "0 2px 10px rgba(0,0,0,0.35)",
        }}
      >
        {face.label}
      </div>
      {face.pill ? (
        <div style={{ opacity: pillOpacity, transform: `translateY(${pillRise}px)` }}>
          <StatusPill text={face.pill} tone={face.tone} icon={face.icon} fontSize={pillPx} strong={face.strong} compact={face.compact} />
        </div>
      ) : null}
    </div>
  );
};

const Slot = ({ left, top, width, height, opacity }: { left: number; top: number; width: number; height: number; opacity: number }) => (
  <div
    style={{
      position: "absolute",
      left,
      top,
      width,
      height,
      boxSizing: "border-box",
      borderRadius: tileRadius,
      border: `2px dashed ${rgba(colors.muted, 0.55)}`,
      background: `linear-gradient(180deg, ${rgba(colors.navyPanel, 0.9)} 0%, ${rgba(colors.navyBottom, 0.9)} 100%)`,
      boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
      opacity,
    }}
  />
);

const DnsLine = ({ text, top, opacity, rise, sharpRatio }: { text: string; top: number; opacity: number; rise: number; sharpRatio: number }) => {
  const sharpEnd = Math.round(sharpRatio * 100);
  const fadeEnd = Math.min(100, sharpEnd + 18);
  const textStyle = {
    fontFamily: fontFamilies.mono,
    fontSize: dnsFontPx,
    lineHeight: 1.3,
    color: colors.muted,
    whiteSpace: "nowrap" as const,
    letterSpacing: "-0.01em",
  };
  return (
    <div
      style={{
        position: "absolute",
        left: zones.card.x0,
        width: zones.card.x1 - zones.card.x0,
        top: top + rise,
        display: "flex",
        justifyContent: "center",
        opacity,
      }}
    >
      <div
        style={{
          position: "relative",
          padding: `${dnsPadY}px 26px`,
          borderRadius: 18,
          background: rgba(colors.navyBottom, 0.82),
          border: panelSurface.border,
          boxShadow: `${panelSurface.highlight}, 0 10px 28px rgba(0,0,0,0.4)`,
          maxWidth: zones.card.x1 - zones.card.x0,
          boxSizing: "border-box",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            ...textStyle,
            WebkitMaskImage: `linear-gradient(90deg, #000 0%, #000 ${sharpEnd}%, transparent ${fadeEnd}%)`,
            maskImage: `linear-gradient(90deg, #000 0%, #000 ${sharpEnd}%, transparent ${fadeEnd}%)`,
          }}
        >
          {text}
        </div>
        <div
          style={{
            ...textStyle,
            position: "absolute",
            left: 26,
            top: dnsPadY,
            filter: "blur(7px)",
            WebkitMaskImage: `linear-gradient(90deg, transparent 0%, transparent ${sharpEnd}%, #000 ${fadeEnd}%)`,
            maskImage: `linear-gradient(90deg, transparent 0%, transparent ${sharpEnd}%, #000 ${fadeEnd}%)`,
          }}
        >
          {text}
        </div>
      </div>
    </div>
  );
};

const AuthTiles = ({ props, frame, durationInFrames, fps, beat, toFrame }: BeatProps<AuthTilesProps>) => {
  const context = { beat, toFrame };
  const count = props.labels.length;
  const zoneWidth = zones.card.x1 - zones.card.x0;
  const zoneHeight = zones.card.y1 - zones.card.y0;
  const tileWidth = Math.min(maxTileWidth, Math.floor((zoneWidth - gapPx * (count - 1)) / count));
  const labelPx = fitFontPx(props.labels, tileWidth - 44, props.labelPx, 52);
  const pillHeight = props.pill || props.flipAt !== undefined ? Math.round(props.pillPx * 1.5) : 0;
  const tileHeight = tilePadY * 2 + Math.round(labelPx * 1.05) + (pillHeight > 0 ? labelPillGap + pillHeight : 0);
  const dnsHeight = props.dnsLine ? Math.round(dnsFontPx * 1.3) + dnsPadY * 2 + 2 : 0;
  const blockHeight = tileHeight + (dnsHeight > 0 ? dnsGap + dnsHeight : 0);
  const rowWidth = tileWidth * count + gapPx * (count - 1);
  const x0 = Math.round(zones.card.x0 + (zoneWidth - rowWidth) / 2);
  const y0 = Math.round(zones.card.y0 + Math.max(0, (zoneHeight - blockHeight) / 2));
  const settled = props.enter === "settled";
  const lastSlam = props.slamTimes[props.slamTimes.length - 1] ?? 0;
  const slamFrames: number[] = props.labels.map((_, index) =>
    settled
      ? -fps
      : relFrame(context, props.slamTimes[index] ?? lastSlam + (index - props.slamTimes.length + 1) * (motion.staggerFrames / fps)),
  );
  const pillDelay = Math.round(props.pillDelaySec * fps);
  const flipStart = props.flipAt === undefined ? undefined : relFrame(context, props.flipAt);
  const flipStagger = Math.round(props.flipStaggerSec * fps);
  const dnsStart = settled ? -fps : props.dnsAt !== undefined ? relFrame(context, props.dnsAt) : (slamFrames[0] ?? 0) + 6;
  const exit = leave(frame, durationInFrames, props.exit);
  const slotIn = settled ? 0 : ramp(frame + 1, 0, 4);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity: exit.opacity, transform: `translateY(${exit.y}px)` }}>
      {props.labels.map((label, index) => {
        const left = x0 + index * (tileWidth + gapPx);
        const slam = slamFrames[index] ?? 0;
        const tile = arrive(frame, slam);
        const slotOpacity = props.slots && !settled ? slotIn * interpolate(frame, [slam, slam + 3], [1, 0], clamp) : 0;
        const pillMotion = arrive(frame, slam + pillDelay);
        const thisFlip = flipStart === undefined ? undefined : flipStart + index * flipStagger;
        const flip = thisFlip === undefined ? 0 : ramp(frame, thisFlip, flipFrames, easeInOutCubic);
        const angle = flip * 180;
        const showBack = angle > 90;
        const lift = 1 + 0.05 * Math.sin(flip * Math.PI);
        const glow = thisFlip === undefined ? 0 : interpolate(frame, [thisFlip + flipFrames - 2, thisFlip + flipFrames, thisFlip + flipFrames + 12], [0, 1, 0.35], clamp);
        const frontCompact = props.pill !== undefined && pillWidth(props.pill, props.pillPx, false) > tileWidth - 16;
        const backCompact = pillWidth(props.flipLabel, props.pillPx, true) > tileWidth - 16;
        const front: Face = { label, pill: props.pill, tone: props.pillTone, icon: frontCompact ? props.pillIcon : undefined, strong: false, compact: frontCompact };
        const back: Face = { label, pill: props.flipLabel, tone: props.flipTone, icon: props.flipIcon, strong: true, compact: backCompact };
        return (
          <div key={index}>
            {slotOpacity > 0 ? <Slot left={left} top={y0} width={tileWidth} height={tileHeight} opacity={slotOpacity} /> : null}
            {frame >= slam ? (
              <div
                style={{
                  position: "absolute",
                  left,
                  top: y0,
                  width: tileWidth,
                  height: tileHeight,
                  opacity: tile.opacity,
                  transform: `perspective(${perspectivePx}px) scale(${tile.scale * lift}) rotateY(${showBack ? angle - 180 : angle}deg)`,
                }}
              >
                <TileFace
                  face={showBack ? back : front}
                  width={tileWidth}
                  height={tileHeight}
                  labelPx={labelPx}
                  pillPx={props.pillPx}
                  pillOpacity={showBack ? 1 : pillMotion.opacity}
                  pillRise={showBack ? 0 : Math.round(pillMotion.rise * 0.4)}
                  glow={showBack ? glow : 0}
                />
              </div>
            ) : null}
          </div>
        );
      })}
      {props.dnsLine && frame >= dnsStart ? (
        <DnsLine
          text={props.dnsLine}
          top={y0 + tileHeight + dnsGap}
          opacity={arrive(frame, dnsStart).opacity}
          rise={Math.round(arrive(frame, dnsStart).rise * 0.5)}
          sharpRatio={props.dnsSharpRatio}
        />
      ) : null}
    </AbsoluteFill>
  );
};

export default AuthTiles;
