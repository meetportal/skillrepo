import { Easing, interpolate } from "remotion";
import { z } from "zod";
import { colors, fontFamilies, motion } from "../../theme";
import { timeSchema, toneSchema } from "../../lib/beatSchemas";
import type { BeatProps } from "../../types";
import { boxStyle, shakeOffset, stampStyle, toneColor, zones as layoutZones, type Box, type Tone } from "../ui";
import { arrivalTransform, chainedMotion, fitWordFontPx, hexAlpha, panelStyle, secToFrame, sheenStyle } from "./mistake2/shared";

export const schema = z.object({
  zones: z
    .array(z.object({ label: z.string().min(1), tone: toneSchema, weight: z.number().positive().default(1) }))
    .min(2)
    .max(4),
  sweepStart: timeSchema,
  pegAt: timeSchema,
  shakeFrames: z.number().int().nonnegative().default(3),
  restValue: z.number().min(0).max(0.5).default(0.06),
  chainIn: z.boolean().default(false),
  chainOut: z.boolean().default(false),
  box: z.object({ x0: z.number(), x1: z.number(), y0: z.number(), y1: z.number() }).optional(),
});

export type GaugeProps = z.infer<typeof schema>;

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const sweepEase = Easing.bezier(0.42, 0, 0.68, 0.84);
const slamEase = Easing.bezier(0.55, 0, 1, 0.45);
const slamFrames = 3;
const swapFrames = 5;
const stampLeadFrames = 2;
const gapValue = 0.012;

const arcPoint = (cx: number, cy: number, r: number, value: number) => {
  const theta = Math.PI * (1 - value);
  return { x: cx + r * Math.cos(theta), y: cy - r * Math.sin(theta) };
};

const arcPath = (cx: number, cy: number, r: number, from: number, to: number) => {
  const a = arcPoint(cx, cy, r, from);
  const b = arcPoint(cx, cy, r, to);
  return `M ${a.x.toFixed(2)} ${a.y.toFixed(2)} A ${r} ${r} 0 0 1 ${b.x.toFixed(2)} ${b.y.toFixed(2)}`;
};

const needleValue = (frame: number, sweepF: number, pegF: number, rest: number, target: number) => {
  const slamF = Math.max(sweepF + 1, pegF - slamFrames);
  if (frame < slamF) {
    return interpolate(frame, [sweepF, slamF], [rest, target], { ...clamp, easing: sweepEase });
  }
  return interpolate(frame, [slamF, Math.max(slamF + 1, pegF)], [target, 1], { ...clamp, easing: slamEase });
};

const Gauge = ({ props, frame, durationInFrames, fps }: BeatProps<GaugeProps>) => {
  const box: Box = props.box ?? layoutZones.card;
  const width = box.x1 - box.x0;
  const height = box.y1 - box.y0;
  const sweepF = secToFrame(props.sweepStart, fps);
  const pegF = Math.max(sweepF + slamFrames + 1, secToFrame(props.pegAt, fps));

  const totalWeight = props.zones.reduce((sum, zone) => sum + zone.weight, 0);
  const bounds = props.zones.reduce<number[]>((acc, zone) => [...acc, (acc[acc.length - 1] ?? 0) + zone.weight / totalWeight], [0]);
  const bound = (index: number): number => bounds[index] ?? 1;
  const lastIndex = props.zones.length - 1;
  const sweepTarget = Math.max(props.restValue, bound(lastIndex) - gapValue * 1.5);
  const value = needleValue(frame, sweepF, pegF, props.restValue, sweepTarget);

  const crossFrames = props.zones.map((_, index) => {
    if (index === 0) return 0;
    if (index === lastIndex) return pegF - stampLeadFrames;
    for (let f = 0; f <= durationInFrames; f += 1) {
      if (needleValue(f, sweepF, pegF, props.restValue, sweepTarget) >= bound(index)) return f;
    }
    return Number.POSITIVE_INFINITY;
  });

  const inner = height - 64;
  const radius = Math.round(Math.min(inner * 0.78, width * 0.24));
  const stroke = Math.round(radius * 0.17);
  const cx = 40 + stroke / 2 + radius;
  const cy = Math.round(height / 2 + radius / 2 - 4);
  const readoutX = Math.round(cx + radius + stroke / 2 + 36);
  const readoutWidth = width - readoutX - 40;
  const words = props.zones.flatMap((zone) => zone.label.split(/\s+/));
  const readoutPx = fitWordFontPx(words, readoutWidth, 96, 56);

  const chain = chainedMotion(frame, durationInFrames, props.chainIn, props.chainOut);
  const enter = chain.panel;
  const shake = shakeOffset(frame, pegF, props.shakeFrames, 6);
  const pegged = frame >= pegF;
  const pegGlow = interpolate(frame, [pegF, pegF + 2, pegF + 14], [0, 1, 0.55], clamp);

  const needleDeg = -180 * (1 - value);
  const tickCount = 24;

  return (
    <div
      style={{
        ...boxStyle(box),
        ...panelStyle,
        opacity: enter.opacity,
        transform: arrivalTransform(enter, shake.x, shake.y),
      }}
    >
      <div style={sheenStyle} />
      <div style={{ position: "absolute", inset: 0, opacity: chain.contentOpacity, transform: `translateY(${chain.contentDy}px)` }}>
      <svg width={width} height={height} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
        {props.zones.map((zone, index) => (
          <path
            key={`track-${index}`}
            d={arcPath(cx, cy, radius, bound(index) + (index === 0 ? 0 : gapValue / 2), bound(index + 1) - (index === lastIndex ? 0 : gapValue / 2))}
            stroke={hexAlpha(toneColor(zone.tone), 0.17)}
            strokeWidth={stroke}
            fill="none"
          />
        ))}
        {props.zones.map((zone, index) => {
          const start = bound(index) + (index === 0 ? 0 : gapValue / 2);
          const end = Math.min(value, bound(index + 1) - (index === lastIndex ? 0 : gapValue / 2));
          if (end <= start + 0.001) return null;
          const color = toneColor(zone.tone);
          const glow = index === lastIndex ? pegGlow : 0;
          return (
            <path
              key={`lit-${index}`}
              d={arcPath(cx, cy, radius, start, end)}
              stroke={color}
              strokeWidth={stroke}
              fill="none"
              style={{ filter: `drop-shadow(0 0 ${8 + glow * 16}px ${hexAlpha(color, 0.35 + glow * 0.45)})` }}
            />
          );
        })}
        {Array.from({ length: tickCount + 1 }, (_, index) => {
          const tickValue = index / tickCount;
          const isBound = bounds.some((bound) => Math.abs(bound - tickValue) < 0.02 && bound > 0 && bound < 1);
          const outer = arcPoint(cx, cy, radius - stroke / 2 - 10, tickValue);
          const innerPoint = arcPoint(cx, cy, radius - stroke / 2 - (isBound ? 30 : 20), tickValue);
          return (
            <line
              key={`tick-${index}`}
              x1={outer.x}
              y1={outer.y}
              x2={innerPoint.x}
              y2={innerPoint.y}
              stroke={hexAlpha(colors.muted, isBound ? 0.55 : 0.28)}
              strokeWidth={isBound ? 3 : 2}
              strokeLinecap="round"
            />
          );
        })}
        <g transform={`rotate(${needleDeg.toFixed(3)} ${cx} ${cy})`} style={{ filter: "drop-shadow(0 3px 6px rgba(0,0,0,0.55))" }}>
          <polygon
            points={`${cx - 14},${cy - 8} ${cx + radius - stroke / 2 - 18},${cy - 2} ${cx + radius - stroke / 2 - 18},${cy + 2} ${cx - 14},${cy + 8}`}
            fill={colors.text}
          />
        </g>
        <circle cx={cx} cy={cy} r={20} fill={colors.text} />
        <circle cx={cx} cy={cy} r={8} fill={colors.navyBottom} />
      </svg>
      <div
        style={{
          position: "absolute",
          left: readoutX,
          top: 0,
          width: readoutWidth,
          height,
        }}
      >
        {props.zones.map((zone, index) => {
          const appear = crossFrames[index] ?? 0;
          const leave = index === lastIndex ? Number.POSITIVE_INFINITY : (crossFrames[index + 1] ?? Number.POSITIVE_INFINITY);
          const cutToStamp = index + 1 === lastIndex;
          if (frame < appear || frame >= leave + (cutToStamp ? 1 : swapFrames)) return null;
          const color = toneColor(zone.tone as Tone);
          const isStamp = index === lastIndex && index > 0;
          const inProgress = index === 0 ? 1 : interpolate(frame, [appear, appear + swapFrames], [0, 1], { ...clamp, easing: motion.ease });
          const outProgress = Number.isFinite(leave) ? interpolate(frame, [leave, leave + swapFrames - 1], [0, 1], { ...clamp, easing: motion.exitEase }) : 0;
          const stamp = stampStyle(frame, appear);
          const opacity = isStamp ? stamp.opacity : inProgress * (1 - outProgress);
          const transform = isStamp
            ? stamp.transform
            : `translateY(${Math.round((1 - inProgress) * 28 - outProgress * 22)}px)`;
          return (
            <div
              key={`readout-${index}`}
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                textAlign: "center",
                opacity,
              }}
            >
              <div
                style={{
                  transform,
                  transformOrigin: "center center",
                  fontFamily: fontFamilies.sans,
                  fontWeight: 800,
                  fontSize: readoutPx,
                  lineHeight: 0.98,
                  letterSpacing: "-0.01em",
                  color,
                  textShadow: `0 0 ${isStamp && pegged ? 28 : 18}px ${hexAlpha(color, isStamp && pegged ? 0.45 : 0.25)}`,
                }}
              >
                {zone.label}
              </div>
            </div>
          );
        })}
      </div>
      </div>
    </div>
  );
};

export default Gauge;
