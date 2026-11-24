import { AbsoluteFill, interpolate, interpolateColors } from "remotion";
import { z } from "zod";
import { iconSchema, timeSchema, toneSchema } from "../../lib/beatSchemas";
import { colors, fontFamilies, motion, surface, type } from "../../theme";
import type { BeatProps } from "../../types";
import { Icon, shakeOffset, toneColor, toneFill, zones, type IconName, type Tone } from "../ui";
import { crackGeometry, type CrackGeometry } from "./mistake1/crack";
import { relFrame, riseIn, sinkOut } from "./mistake1/kit";

export const schema = z.object({
  icons: z.array(iconSchema).min(1).max(4),
  labels: z.array(z.string().min(1)).max(4).default([]),
  crackTimes: z.array(timeSchema).default([]),
  enterAt: timeSchema.default(0),
  crackTone: toneSchema.default("danger"),
  iconPx: z.number().min(96).max(180).default(140),
  labelPx: z.number().min(type.cardMinPx).max(60).default(44),
  shake: z.boolean().default(true),
  seed: z.number().int().default(7),
});

export type IconCrackTilesProps = z.infer<typeof schema>;

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const gapPx = 32;
const maxTilePx = 272;
const tileRadius = 34;

const IconLayer = ({
  name,
  iconPx,
  color,
  clipPath,
  transform,
  height,
  width,
}: {
  name: IconName;
  iconPx: number;
  color: string;
  clipPath?: string;
  transform?: string;
  height: number;
  width: number;
}) => (
  <div
    style={{
      position: "absolute",
      left: 0,
      top: 0,
      width,
      height,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      clipPath,
      transform,
    }}
  >
    <Icon name={name} size={iconPx} color={color} strokeWidth={1.5} />
  </div>
);

const CrackLines = ({ geometry, progress, color, width, height }: { geometry: CrackGeometry; progress: number; color: string; width: number; height: number }) => (
  <svg width={width} height={height} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
    <path d={geometry.mainPath} fill="none" stroke="rgba(4,8,20,0.9)" strokeWidth={9} strokeLinejoin="round" strokeLinecap="round" pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - progress} />
    <path d={geometry.mainPath} fill="none" stroke={color} strokeWidth={3.5} strokeLinejoin="round" strokeLinecap="round" pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - progress} style={{ filter: `drop-shadow(0 0 6px ${color})` }} />
    {geometry.branchPaths.map((d, index) => {
      const branch = interpolate(progress, [0.35 + index * 0.15, 1], [0, 1], clamp);
      return <path key={index} d={d} fill="none" stroke={color} strokeWidth={2.5} strokeLinecap="round" pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - branch} opacity={0.85} />;
    })}
  </svg>
);

const CrackTile = ({
  name,
  label,
  index,
  frame,
  enterStart,
  crackStart,
  tone,
  props,
  left,
  top,
  width,
  height,
}: {
  name: IconName;
  label?: string;
  index: number;
  frame: number;
  enterStart: number;
  crackStart: number | undefined;
  tone: Tone;
  props: IconCrackTilesProps;
  left: number;
  top: number;
  width: number;
  height: number;
}) => {
  const enter = riseIn(frame, enterStart);
  const cracked = crackStart !== undefined && frame >= crackStart;
  const local = crackStart === undefined ? -1 : frame - crackStart;
  const line = cracked ? interpolate(local, [0, 3], [0, 1], { ...clamp, easing: motion.ease }) : 0;
  const tint = cracked ? interpolate(local, [0, 2], [0, 1], clamp) : 0;
  const split = cracked ? interpolate(local, [0, 5], [0, 1], { ...clamp, easing: motion.ease }) : 0;
  const flash = cracked ? interpolate(local, [0, 2, 14], [0, 1, 0.35], clamp) : 0;
  const shake = props.shake && crackStart !== undefined ? shakeOffset(frame, crackStart, 2, 5) : { x: 0, y: 0 };
  const toneHex = toneColor(tone);
  const iconColor = interpolateColors(tint, [0, 1], [colors.text, toneHex]);
  const borderColor = interpolateColors(tint, [0, 1], [colors.border, toneFill(tone, 0.75)]);
  const labelColor = interpolateColors(tint, [0, 1], [colors.muted, toneHex]);
  const labelBand = label ? props.labelPx * 1.2 + 14 : 0;
  const iconHeight = height - labelBand;
  const geometry = crackGeometry(width, height, props.seed + index * 31);
  const gap = split * 7;
  return (
    <div
      style={{
        position: "absolute",
        left: left + shake.x,
        top: top + shake.y + enter.y,
        width,
        height,
        boxSizing: "border-box",
        borderRadius: tileRadius,
        border: `1px solid ${borderColor}`,
        background: `linear-gradient(180deg, ${toneFill(tone, 0.16 * tint)} 0%, rgba(0,0,0,0) 70%), linear-gradient(180deg, ${colors.navyTile} 0%, ${colors.navyPanel} 100%)`,
        boxShadow: `${surface.cardShadow}, inset 0 1px 0 rgba(255,255,255,0.07), 0 0 ${48 * flash}px ${toneFill(tone, 0.45 * flash)}`,
        opacity: enter.opacity,
        overflow: "hidden",
      }}
    >
      {cracked ? (
        <>
          <IconLayer name={name} iconPx={props.iconPx} color={iconColor} width={width} height={iconHeight} clipPath={geometry.leftClip} transform={`translate(${-gap}px, ${gap * 0.25}px) rotate(${-split * 2.5}deg)`} />
          <IconLayer name={name} iconPx={props.iconPx} color={iconColor} width={width} height={iconHeight} clipPath={geometry.rightClip} transform={`translate(${gap}px, ${-gap * 0.2}px) rotate(${split * 2}deg)`} />
          <CrackLines geometry={geometry} progress={line} color={toneHex} width={width} height={height} />
        </>
      ) : (
        <IconLayer name={name} iconPx={props.iconPx} color={iconColor} width={width} height={iconHeight} />
      )}
      {label ? (
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            bottom: 26,
            textAlign: "center",
            fontFamily: fontFamilies.sans,
            fontWeight: 600,
            fontSize: props.labelPx,
            lineHeight: 1.2,
            color: labelColor,
            whiteSpace: "nowrap",
          }}
        >
          {label}
        </div>
      ) : null}
    </div>
  );
};

const IconCrackTiles = ({ props, frame, durationInFrames, beat, toFrame }: BeatProps<IconCrackTilesProps>) => {
  const context = { beat, toFrame };
  const count = props.icons.length;
  const zoneWidth = zones.card.x1 - zones.card.x0;
  const zoneHeight = zones.card.y1 - zones.card.y0;
  const tileWidth = Math.min(maxTilePx, Math.floor((zoneWidth - gapPx * (count - 1)) / count));
  const tileHeight = props.labels.length > 0 ? zoneHeight : Math.min(zoneHeight, tileWidth);
  const rowWidth = tileWidth * count + gapPx * (count - 1);
  const x0 = Math.round(zones.card.x0 + (zoneWidth - rowWidth) / 2);
  const y0 = Math.round(zones.card.y0 + (zoneHeight - tileHeight) / 2);
  const enterStart = relFrame(context, props.enterAt);
  const exit = sinkOut(frame, durationInFrames);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity: exit.opacity, transform: `translateY(${exit.y}px)` }}>
      {props.icons.map((name, index) => (
        <CrackTile
          key={index}
          name={name}
          label={props.labels[index]}
          index={index}
          frame={frame}
          enterStart={enterStart + index * motion.staggerFrames}
          crackStart={props.crackTimes[index] === undefined ? undefined : relFrame(context, props.crackTimes[index])}
          tone={props.crackTone}
          props={props}
          left={x0 + index * (tileWidth + gapPx)}
          top={y0}
          width={tileWidth}
          height={tileHeight}
        />
      ))}
    </AbsoluteFill>
  );
};

export default IconCrackTiles;
