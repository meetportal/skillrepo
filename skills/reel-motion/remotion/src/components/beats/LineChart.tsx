import { Easing, interpolate } from "remotion";
import { z } from "zod";
import { colors, fontFamilies } from "../../theme";
import { timeSchema, toneSchema } from "../../lib/beatSchemas";
import type { BeatProps } from "../../types";
import { boxStyle, entranceProgress, toneColor, zones as layoutZones, type Box } from "../ui";
import { arrival, arrivalTransform, chainedMotion, hexAlpha, panelStyle, secToFrame, sheenStyle } from "./mistake2/shared";

const shapeSchema = z.enum(["rising", "flat", "falling"]);

export const schema = z.object({
  series: z
    .array(
      z.object({
        label: z.string().min(1),
        shape: shapeSchema,
        tone: toneSchema,
        emphasis: z.boolean().default(false),
      }),
    )
    .min(1)
    .max(3),
  drawStart: timeSchema,
  drawEnd: timeSchema,
  labelsAt: z.number().min(0).max(1).default(0.55),
  chainIn: z.boolean().default(false),
  chainOut: z.boolean().default(false),
  box: z.object({ x0: z.number(), x1: z.number(), y0: z.number(), y1: z.number() }).optional(),
});

export type LineChartProps = z.infer<typeof schema>;
type Shape = z.infer<typeof shapeSchema>;

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const drawEase = Easing.bezier(0.36, 0, 0.24, 1);
const samples = 96;
const origin = 0.12;
const labelPx = 48;

const shapeValue = (shape: Shape, x: number, index: number) => {
  const phase = index * 1.7;
  switch (shape) {
    case "rising":
      return origin + (0.94 - origin) * Math.pow(x, 2.05) + 0.018 * Math.sin(x * 13 + phase) * x * (1 - x);
    case "flat":
      return origin + 0.03 * Math.sin(x * 11) * Math.min(1, x * 6) + 0.012 * Math.sin(x * 27 + phase) * x + 0.03 * x;
    case "falling":
      return 0.9 - (0.9 - origin) * Math.pow(x, 1.6) + 0.016 * Math.sin(x * 12 + phase) * x * (1 - x);
  }
};

const LineChart = ({ props, frame, durationInFrames, fps }: BeatProps<LineChartProps>) => {
  const box: Box = props.box ?? layoutZones.card;
  const width = box.x1 - box.x0;
  const height = box.y1 - box.y0;
  const startF = secToFrame(props.drawStart, fps);
  const endF = Math.max(startF + 1, secToFrame(props.drawEnd, fps));
  const progress = interpolate(frame, [startF, endF], [0, 1], { ...clamp, easing: drawEase });
  const labelF = Math.round(startF + (endF - startF) * props.labelsAt);

  const longestLabel = Math.max(...props.series.map((line) => line.label.length));
  const labelWidth = Math.round(longestLabel * labelPx * 0.6) + 28;
  const plot = { x0: 56, x1: width - 48 - labelWidth - 36, y0: 58, y1: height - 54 };
  const plotW = plot.x1 - plot.x0;
  const plotH = plot.y1 - plot.y0;
  const toX = (x: number) => plot.x0 + x * plotW;
  const toY = (y: number) => plot.y1 - y * plotH;

  const chain = chainedMotion(frame, durationInFrames, props.chainIn, props.chainOut);
  const enter = chain.panel;
  const gridLines = [0, 1 / 3, 2 / 3, 1];
  const drawOrder = props.series.map((_, index) => index).sort((a, b) => Number(props.series[a]?.emphasis) - Number(props.series[b]?.emphasis));

  const endYs = props.series.map((line, index) => toY(shapeValue(line.shape, 1, index)));
  const minGap = labelPx * 1.25;
  const labelYs = endYs
    .map((y, index) => ({ y, index }))
    .sort((a, b) => a.y - b.y)
    .reduce<{ y: number; index: number }[]>((placed, item) => {
      const previous = placed[placed.length - 1];
      return [...placed, { index: item.index, y: previous && item.y - previous.y < minGap ? previous.y + minGap : item.y }];
    }, [])
    .sort((a, b) => a.index - b.index)
    .map((item) => item.y);

  return (
    <div style={{ ...boxStyle(box), ...panelStyle, opacity: enter.opacity, transform: arrivalTransform(enter) }}>
      <div style={sheenStyle} />
      <div style={{ position: "absolute", inset: 0, opacity: chain.contentOpacity, transform: `translateY(${chain.contentDy}px)` }}>
      <svg width={width} height={height} style={{ position: "absolute", left: 0, top: 0 }}>
        <defs>
          {props.series.map((line, index) => (
            <linearGradient key={`fill-${index}`} id={`linechart-fill-${index}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={toneColor(line.tone)} stopOpacity={0.32} />
              <stop offset="100%" stopColor={toneColor(line.tone)} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>
        {gridLines.map((value, index) => (
          <line
            key={`grid-${index}`}
            x1={plot.x0}
            x2={plot.x1}
            y1={Math.round(toY(value)) + 0.5}
            y2={Math.round(toY(value)) + 0.5}
            stroke={hexAlpha(colors.muted, value === 0 ? 0.5 : 0.22)}
            strokeWidth={value === 0 ? 2 : 1}
            strokeDasharray={value === 0 ? undefined : "4 8"}
          />
        ))}
        {drawOrder.map((index) => {
          const line = props.series[index];
          if (!line) return null;
          const color = toneColor(line.tone);
          const count = Math.max(2, Math.ceil(samples * progress) + 1);
          const points = Array.from({ length: count }, (_, step) => {
            const x = Math.min(progress, (step / (count - 1)) * progress);
            return { x: toX(x), y: toY(shapeValue(line.shape, x, index)) };
          });
          const pathD = points.map((point, step) => `${step === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");
          const head = points[points.length - 1] ?? { x: toX(0), y: plot.y1 };
          const first = points[0] ?? head;
          const areaD = `${pathD} L ${head.x.toFixed(2)} ${plot.y1} L ${first.x.toFixed(2)} ${plot.y1} Z`;
          const strokeWidth = line.emphasis ? 9 : 7;
          const dotIn = entranceProgress(frame, index * 3);
          return (
            <g key={`series-${index}`}>
              {line.emphasis && progress > 0 ? <path d={areaD} fill={`url(#linechart-fill-${index})`} /> : null}
              {progress > 0 ? (
                <path
                  d={pathD}
                  stroke={color}
                  strokeWidth={strokeWidth}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  fill="none"
                  style={{ filter: `drop-shadow(0 0 ${line.emphasis ? 10 : 6}px ${hexAlpha(color, line.emphasis ? 0.45 : 0.25)})` }}
                />
              ) : null}
              <circle cx={head.x} cy={head.y} r={line.emphasis ? 24 : 20} fill={hexAlpha(color, 0.18 * dotIn)} />
              <circle cx={head.x} cy={head.y} r={line.emphasis ? 11 : 9.5} fill={color} opacity={dotIn} stroke={colors.navyBottom} strokeWidth={3} />
            </g>
          );
        })}
      </svg>
      {props.series.map((line, index) => {
        const label = arrival(frame, durationInFrames + 100, { start: labelF + index * 3, from: "left", exit: false });
        const color = toneColor(line.tone);
        return (
          <div
            key={`label-${index}`}
            style={{
              position: "absolute",
              left: plot.x1 + 36,
              top: Math.round((labelYs[index] ?? 0) - labelPx * 0.62),
              height: Math.round(labelPx * 1.24),
              display: "flex",
              alignItems: "center",
              fontFamily: fontFamilies.sans,
              fontWeight: line.emphasis ? 700 : 600,
              fontSize: labelPx,
              lineHeight: 1,
              color,
              whiteSpace: "nowrap",
              opacity: label.opacity,
              transform: arrivalTransform(label),
              textShadow: `0 0 16px ${hexAlpha(color, line.emphasis ? 0.3 : 0.12)}`,
            }}
          >
            {line.label}
          </div>
        );
      })}
      </div>
    </div>
  );
};

export default LineChart;
