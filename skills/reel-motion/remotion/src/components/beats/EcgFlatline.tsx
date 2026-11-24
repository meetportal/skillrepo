import { AbsoluteFill, interpolate } from "remotion";
import { z } from "zod";
import { colors, fontFamilies, layout, surface } from "../../theme";
import { timeSchema, toneSchema } from "../../lib/beatSchemas";
import type { BeatProps } from "../../types";
import { entranceProgress, exitProgress, toneColor, zones as layoutZones, type Box } from "../ui";
import { arrival, arrivalTransform, hexAlpha, panelStyle, secToFrame, sheenStyle } from "./mistake2/shared";

export const schema = z.object({
  label: z.string().min(1),
  flatlineAt: timeSchema,
  liveTone: toneSchema.default("success"),
  deadTone: toneSchema.default("danger"),
  sweepSec: z.number().positive().default(1.0),
  beatSec: z.number().positive().default(0.5),
  flatlineX: z.number().min(0.1).max(0.9).default(0.36),
  flatRushFactor: z.number().min(1).max(6).default(3),
  band: z.object({ x0: z.number(), x1: z.number(), y0: z.number(), y1: z.number() }).optional(),
  card: z.boolean().default(false),
});

export type EcgFlatlineProps = z.infer<typeof schema>;

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const gauss = (u: number, mean: number, sigma: number) => Math.exp(-((u - mean) * (u - mean)) / (2 * sigma * sigma));
const rPhase = 0.33;

const ecgShape = (u: number) =>
  0.11 * gauss(u, 0.16, 0.028) -
  0.13 * gauss(u, 0.305, 0.008) +
  1.0 * gauss(u, rPhase, 0.0085) -
  0.32 * gauss(u, 0.357, 0.009) +
  0.24 * gauss(u, 0.6, 0.042);

const positiveMod = (value: number, modulus: number) => ((value % modulus) + modulus) % modulus;

const cardInsetPx = 40;

const geometryFor = (band: Box, card: boolean) => {
  const height = band.y1 - band.y0;
  if (card) {
    return {
      traceX0: band.x0 + cardInsetPx,
      traceW: band.x1 - band.x0 - 2 * cardInsetPx,
      amplitude: Math.min(250, height * 0.32),
      baseY: Math.round(band.y0 + height * 0.74),
      labelY: band.y0 + 30,
      gridTop: band.y0 + 112,
      gridBottom: band.y1 - 18,
    };
  }
  return {
    traceX0: band.x0,
    traceW: band.x1 - band.x0,
    amplitude: Math.min(250, height * 0.36),
    baseY: Math.round(band.y0 + height * 0.66),
    labelY: band.y0 + 70,
    gridTop: band.y0 + 150,
    gridBottom: band.y1 - 20,
  };
};

const EcgFlatline = ({ props, frame, durationInFrames, fps }: BeatProps<EcgFlatlineProps>) => {
  const band: Box = props.band ?? (props.card ? layoutZones.card : layoutZones.takeoverBand);
  const { traceX0, traceW, amplitude, baseY, labelY, gridTop, gridBottom } = geometryFor(band, props.card);
  const flatF = secToFrame(props.flatlineAt, fps);
  const speed = traceW / props.sweepSec;
  const periodPx = speed * props.beatSec;
  const flatS = props.flatlineX * traceW + Math.ceil((props.flatlineAt * speed) / traceW + 1) * traceW;
  const sweepBaseAtFlat = Math.floor(flatS / traceW) * traceW;
  const head =
    frame < flatF
      ? flatS - ((flatF - frame) / fps) * speed
      : Math.min(sweepBaseAtFlat + traceW, flatS + ((frame - flatF) / fps) * speed * props.flatRushFactor);
  const lastPeakS = flatS - 0.58 * periodPx;
  const phaseOffset = rPhase * periodPx - lastPeakS;
  const gapPx = 46;

  const sampleY = (s: number) => (s >= flatS ? 0 : ecgShape(positiveMod(s + phaseOffset, periodPx) / periodPx));

  const headX = frame >= flatF ? head - sweepBaseAtFlat : positiveMod(head, traceW);
  const buildPath = (fromX: number, toX: number, sweepBase: number) => {
    if (toX - fromX < 1) return "";
    const parts: string[] = [];
    for (let x = fromX; x <= toX; x += 1) {
      const s = sweepBase + x;
      parts.push(`${parts.length === 0 ? "M" : "L"} ${(traceX0 + x).toFixed(1)} ${(baseY - sampleY(s) * amplitude).toFixed(2)}`);
    }
    const s = sweepBase + toX;
    parts.push(`L ${(traceX0 + toX).toFixed(1)} ${(baseY - sampleY(s) * amplitude).toFixed(2)}`);
    return parts.join(" ");
  };
  const currentBase = head - headX;
  const currentPath = buildPath(0, headX, currentBase);
  const previousPath = buildPath(Math.min(traceW, headX + gapPx), traceW, currentBase - traceW);

  const dead = interpolate(frame, [flatF, flatF + 2], [0, 1], clamp);
  const liveColor = toneColor(props.liveTone);
  const deadColor = toneColor(props.deadTone);

  const bgIn = interpolate(entranceProgress(frame, 0, 6), [0, 0.6], [0, 1], clamp);
  const bgOut = exitProgress(frame, durationInFrames);
  const contentOut = exitProgress(frame, durationInFrames - 2, 3);
  const content = arrival(frame, durationInFrames, { from: "up", exit: false });
  const panel = arrival(frame, durationInFrames, { from: "up" });
  const traceOpacity = interpolate(entranceProgress(frame, 0, 6), [0, 0.6], [0, 1], clamp) * (1 - contentOut);

  const sinceBeat = positiveMod(head + phaseOffset - rPhase * periodPx, periodPx) / speed;
  const pulse = frame >= flatF ? 0 : interpolate(sinceBeat, [0, 0.06, 0.35], [0.35, 1, 0.35], clamp);
  const headY = baseY - sampleY(head) * amplitude;

  const gridStep = 44;

  const previousFade = interpolate(frame, [flatF, flatF + 6], [1, 0], clamp);
  const traceLayer = (color: string, opacity: number) => (
    <g opacity={opacity}>
      <path
        d={previousPath}
        stroke={color}
        strokeOpacity={0.3 * previousFade}
        strokeWidth={6}
        fill="none"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <path
        d={currentPath}
        stroke={color}
        strokeWidth={7}
        fill="none"
        strokeLinejoin="round"
        strokeLinecap="round"
        style={{ filter: `drop-shadow(0 0 10px ${hexAlpha(color, 0.65)})` }}
      />
    </g>
  );

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {props.card ? (
        <div
          style={{
            ...panelStyle,
            position: "absolute",
            left: band.x0,
            top: band.y0,
            width: band.x1 - band.x0,
            height: band.y1 - band.y0,
            opacity: panel.opacity,
            transform: arrivalTransform(panel),
            background: `radial-gradient(80% 60% at 50% ${Math.round(((baseY - band.y0) / (band.y1 - band.y0)) * 100)}%, ${hexAlpha(liveColor, 0.12 * (1 - dead))} 0%, rgba(0,0,0,0) 70%), radial-gradient(80% 60% at 50% ${Math.round(((baseY - band.y0) / (band.y1 - band.y0)) * 100)}%, ${hexAlpha(deadColor, 0.16 * dead)} 0%, rgba(0,0,0,0) 70%), ${panelStyle.background}`,
          }}
        >
          <div style={sheenStyle} />
        </div>
      ) : (
        <>
          <AbsoluteFill style={{ background: surface.takeoverGradient, opacity: bgIn * (1 - bgOut) }} />
          <AbsoluteFill
            style={{
              opacity: bgIn * (1 - bgOut),
              background: `radial-gradient(70% 34% at 50% ${Math.round((baseY / layout.height) * 100)}%, ${hexAlpha(liveColor, 0.12 * (1 - dead))} 0%, rgba(0,0,0,0) 70%), radial-gradient(70% 34% at 50% ${Math.round((baseY / layout.height) * 100)}%, ${hexAlpha(deadColor, 0.16 * dead)} 0%, rgba(0,0,0,0) 70%)`,
            }}
          />
        </>
      )}
      <svg
        width={layout.width}
        height={layout.height}
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          opacity: props.card ? panel.opacity * (1 - contentOut) : traceOpacity,
          transform: props.card ? arrivalTransform(panel) : undefined,
        }}
      >
        <defs>
          <linearGradient id="ecg-grid-fade" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#fff" stopOpacity={0} />
            <stop offset="12%" stopColor="#fff" stopOpacity={1} />
            <stop offset="88%" stopColor="#fff" stopOpacity={1} />
            <stop offset="100%" stopColor="#fff" stopOpacity={0} />
          </linearGradient>
          <mask id="ecg-grid-mask">
            <rect x={traceX0} y={gridTop} width={traceW} height={gridBottom - gridTop} fill="url(#ecg-grid-fade)" />
          </mask>
        </defs>
        <g mask="url(#ecg-grid-mask)">
          {Array.from({ length: Math.floor((gridBottom - gridTop) / gridStep) + 1 }, (_, index) => (
            <line
              key={`h-${index}`}
              x1={traceX0}
              x2={traceX0 + traceW}
              y1={gridTop + index * gridStep + 0.5}
              y2={gridTop + index * gridStep + 0.5}
              stroke={hexAlpha(colors.muted, 0.09)}
              strokeWidth={1}
            />
          ))}
          {Array.from({ length: Math.floor(traceW / gridStep) + 1 }, (_, index) => (
            <line
              key={`v-${index}`}
              x1={traceX0 + index * gridStep + 0.5}
              x2={traceX0 + index * gridStep + 0.5}
              y1={gridTop}
              y2={gridBottom}
              stroke={hexAlpha(colors.muted, 0.09)}
              strokeWidth={1}
            />
          ))}
        </g>
        {traceLayer(liveColor, 1 - dead)}
        {traceLayer(deadColor, dead)}
        <circle cx={traceX0 + headX} cy={headY} r={22} fill={hexAlpha(dead > 0.5 ? deadColor : liveColor, 0.22)} />
        <circle cx={traceX0 + headX} cy={headY} r={9} fill={colors.text} style={{ filter: `drop-shadow(0 0 10px ${dead > 0.5 ? deadColor : liveColor})` }} />
      </svg>
      <div
        style={{
          position: "absolute",
          left: band.x0,
          width: band.x1 - band.x0,
          top: labelY,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          gap: 26,
          opacity: (props.card ? panel.opacity : content.opacity) * (1 - contentOut),
          transform: arrivalTransform(props.card ? panel : content),
        }}
      >
        <div style={{ position: "relative", width: 30, height: 30, flexShrink: 0 }}>
          <div
            style={{
              position: "absolute",
              inset: -12,
              borderRadius: 999,
              background: hexAlpha(dead > 0.5 ? deadColor : liveColor, 0.28 * (dead > 0.5 ? 1 : pulse)),
            }}
          />
          <div
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: 999,
              background: dead > 0.5 ? deadColor : liveColor,
              boxShadow: `0 0 18px ${hexAlpha(dead > 0.5 ? deadColor : liveColor, 0.8)}`,
            }}
          />
        </div>
        <div
          style={{
            fontFamily: fontFamilies.sans,
            fontWeight: 800,
            fontSize: 64,
            lineHeight: 1,
            letterSpacing: "0.01em",
            color: colors.text,
            whiteSpace: "nowrap",
            textShadow: surface.textShadow,
          }}
        >
          {props.label}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export default EcgFlatline;
