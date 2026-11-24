import { AbsoluteFill } from "remotion";
import { z } from "zod";
import { iconSchema, markupLineSchema, timeSchema, toneSchema } from "../../lib/beatSchemas";
import { colors, fontFamilies, motion, surface, type } from "../../theme";
import type { BeatProps } from "../../types";
import { AccentText, Icon, stampStyle, toneColor, toneFill, zones, type IconName, type Tone } from "../ui";
import { dashStyle, drawOn, relFrame, riseIn, sinkOut } from "./mistake1/kit";

const itemSchema = z.object({
  title: markupLineSchema,
  subtitle: z.string().min(1).optional(),
  tone: toneSchema,
  icon: iconSchema.optional(),
  at: timeSchema.optional(),
  subtitleAt: timeSchema.optional(),
});

export const schema = z.object({
  items: z.array(itemSchema).min(1).max(2),
  stamp: z.enum(["first", "none"]).default("first"),
  gapPx: z.number().int().min(8).max(48).default(16),
  titlePx: z.number().min(type.cardMinPx).max(72).default(52),
  subtitlePx: z.number().min(type.cardMinPx).max(60).default(44),
});

export type CompareCardsProps = z.infer<typeof schema>;
type Item = z.infer<typeof itemSchema>;

const defaultIcon = (tone: Tone): IconName => {
  switch (tone) {
    case "danger":
      return "cross";
    case "success":
      return "shield";
    case "warning":
      return "warning";
    default:
      return "check";
  }
};

const badgePx = 96;
const badgeIconPx = 52;
const rowPadX = 36;
const rowRadius = 30;

const Badge = ({ item, frame, start, stamped }: { item: Item; frame: number; start: number; stamped: boolean }) => {
  const color = toneColor(item.tone);
  const name = item.icon ?? defaultIcon(item.tone);
  const ring = drawOn(frame, start, motion.entranceFrames + 4);
  const glyph = stamped ? 1 : drawOn(frame, start + 2);
  const stampMotion = stamped ? stampStyle(frame, start + 1) : { opacity: 1, transform: "none" };
  const check = name === "shield" ? drawOn(frame, start + 6, 6) : 0;
  return (
    <div style={{ position: "relative", width: badgePx, height: badgePx, flexShrink: 0 }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          background: `radial-gradient(circle at 50% 35%, ${toneFill(item.tone, 0.26)} 0%, ${toneFill(item.tone, 0.1)} 70%)`,
          opacity: ring,
        }}
      />
      <svg width={badgePx} height={badgePx} viewBox="0 0 96 96" style={{ position: "absolute", inset: 0, transform: "rotate(-90deg)" }}>
        <circle cx="48" cy="48" r="47" fill="none" stroke={toneFill(item.tone, 0.55)} strokeWidth="1.5" pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - ring} />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          opacity: stampMotion.opacity,
          transform: stampMotion.transform,
        }}
      >
        <Icon name={name} size={badgeIconPx} color={color} strokeWidth={2.2} style={stamped ? undefined : dashStyle(glyph)} />
        {name === "shield" ? (
          <svg width={badgeIconPx} height={badgeIconPx} viewBox="0 0 24 24" style={{ position: "absolute", overflow: "visible" }}>
            <path d="M8.6 12.2l2.4 2.4 4.6-4.8" fill="none" stroke={color} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - check} />
          </svg>
        ) : null}
      </div>
    </div>
  );
};

const Row = ({
  item,
  frame,
  start,
  subtitleStart,
  top,
  height,
  stamped,
  titlePx,
  subtitlePx,
}: {
  item: Item;
  frame: number;
  start: number;
  subtitleStart: number;
  top: number;
  height: number;
  stamped: boolean;
  titlePx: number;
  subtitlePx: number;
}) => {
  const card = riseIn(frame, start);
  const sub = riseIn(frame, subtitleStart, 14);
  const glow = toneFill(item.tone, 0.18);
  return (
    <div
      style={{
        position: "absolute",
        left: zones.card.x0,
        width: zones.card.x1 - zones.card.x0,
        top,
        height,
        boxSizing: "border-box",
        borderRadius: rowRadius,
        background: `linear-gradient(90deg, ${glow} 0%, rgba(0,0,0,0) 42%), ${surface.cardGradient}`,
        border: `1px solid ${toneFill(item.tone, 0.42)}`,
        boxShadow: `${surface.cardShadow}, inset 0 1px 0 rgba(255,255,255,0.07)`,
        display: "flex",
        alignItems: "center",
        gap: 30,
        padding: `0 ${rowPadX}px`,
        opacity: card.opacity,
        transform: `translateY(${card.y}px)`,
      }}
    >
      <Badge item={item} frame={frame} start={start + 1} stamped={stamped} />
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: 4, minWidth: 0 }}>
        <div
          style={{
            fontFamily: fontFamilies.sans,
            fontWeight: 700,
            fontSize: titlePx,
            lineHeight: 1.1,
            letterSpacing: "-0.012em",
            color: colors.text,
          }}
        >
          <AccentText text={item.title} />
        </div>
        {item.subtitle ? (
          <div
            style={{
              fontFamily: fontFamilies.sans,
              fontWeight: 500,
              fontSize: subtitlePx,
              lineHeight: 1.15,
              color: colors.muted,
              opacity: sub.opacity,
              transform: `translateY(${sub.y}px)`,
            }}
          >
            {item.subtitle}
          </div>
        ) : null}
      </div>
    </div>
  );
};

const CompareCards = ({ props, frame, durationInFrames, beat, toFrame }: BeatProps<CompareCardsProps>) => {
  const context = { beat, toFrame };
  const count = props.items.length;
  const zoneHeight = zones.card.y1 - zones.card.y0;
  const rowHeight = (zoneHeight - props.gapPx * (count - 1)) / count;
  const exit = sinkOut(frame, durationInFrames);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity: exit.opacity, transform: `translateY(${exit.y}px)` }}>
      {props.items.map((item, index) => {
        const start = item.at === undefined ? index * motion.staggerFrames : relFrame(context, item.at);
        const subtitleStart = item.subtitleAt === undefined ? start + motion.staggerFrames : relFrame(context, item.subtitleAt);
        return (
          <Row
            key={index}
            item={item}
            frame={frame}
            start={start}
            subtitleStart={subtitleStart}
            top={zones.card.y0 + index * (rowHeight + props.gapPx)}
            height={rowHeight}
            stamped={props.stamp === "first" && index === 0}
            titlePx={props.titlePx}
            subtitlePx={props.subtitlePx}
          />
        );
      })}
    </AbsoluteFill>
  );
};

export default CompareCards;
