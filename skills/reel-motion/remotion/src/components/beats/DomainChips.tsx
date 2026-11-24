import { measureText } from "@remotion/layout-utils";
import { AbsoluteFill, interpolate, interpolateColors } from "remotion";
import { z } from "zod";
import { iconSchema, toneSchema } from "../../lib/beatSchemas";
import { colors, fontFamilies, motion, surface, zones } from "../../theme";
import type { BeatProps } from "../../types";
import { Icon, shakeOffset, stampStyle, toneColor, toneFill } from "../ui";
import { exitAmount, exitDrift, exitOpacity, fadeIn, secondsToFrames, settleOffset } from "./hook/kit";

export const schema = z.object({
  domains: z.array(z.string().min(1)).min(1).max(4),
  stampLabel: z.string().min(1).default("BURNED"),
  stampAt: z.array(z.number().nonnegative()).default([]),
  enterAt: z.number().nonnegative().default(0),
  exitAt: z.number().nonnegative().optional(),
  shakeFirstStamp: z.boolean().default(false),
  stampTone: toneSchema.default("danger"),
  stampRotateDeg: z.number().min(-20).max(20).default(-10),
  icon: iconSchema.default("globe"),
  domainFont: z.enum(["sans", "mono"]).default("sans"),
  domainSize: z.number().min(44).default(48),
  stampSize: z.number().min(44).default(64),
  box: z.object({ y0: z.number(), y1: z.number() }).optional(),
});

export type DomainChipsProps = z.infer<typeof schema>;

const chipGapPx = 18;
const chipMaxHeight = 92;
const chipPadLeft = 30;
const chipPadRight = 40;
const iconPx = 44;
const iconGapPx = 22;
const stampOverlapPx = 34;
const stampPadX = 24;
const stampBorderPx = 5;
const hitFrames = 3;
const stampLeadFrames = motion.stampFrames - 2;
const chipSettleFrames = 6;
const shakeAmplitudePx = 4;
const shakeFrames = 2;

const DomainChips = ({ props, frame, durationInFrames, fps }: BeatProps<DomainChipsProps>) => {
  const box = props.box ?? { y0: zones.card.y0, y1: zones.card.y1 };
  const count = props.domains.length;
  const chipHeight = Math.min(chipMaxHeight, Math.floor((box.y1 - box.y0 - chipGapPx * (count - 1)) / count));
  const stackHeight = chipHeight * count + chipGapPx * (count - 1);
  const stackTop = Math.round(box.y0 + (box.y1 - box.y0 - stackHeight) / 2);

  const domainFamily = props.domainFont === "mono" ? fontFamilies.mono : fontFamilies.sans;
  const domainWeight = props.domainFont === "mono" ? 500 : 600;
  const widest = Math.max(
    ...props.domains.map(
      (domain) =>
        measureText({ text: domain, fontFamily: domainFamily, fontSize: props.domainSize, fontWeight: domainWeight, letterSpacing: "-0.01em" }).width,
    ),
  );
  const radians = (Math.abs(props.stampRotateDeg) * Math.PI) / 180;
  const stampGeometry = (fontSize: number) => {
    const text = measureText({
      text: props.stampLabel.toUpperCase(),
      fontFamily: fontFamilies.sans,
      fontSize,
      fontWeight: 800,
      letterSpacing: "0.06em",
    });
    const width = Math.ceil(text.width + stampPadX * 2 + stampBorderPx * 2);
    const height = Math.ceil(fontSize + 16 + stampBorderPx * 2);
    const halfExtent = Math.ceil((width * Math.cos(radians) + height * Math.sin(radians)) / 2);
    return { fontSize, width, height, halfExtent };
  };
  const chipWidth = Math.ceil(chipPadLeft + iconPx + iconGapPx + widest + chipPadRight);
  const safeWidth = zones.safe.x1 - zones.safe.x0 - shakeAmplitudePx * 2;
  const groupWidthFor = (halfExtent: number) => chipWidth - stampOverlapPx + halfExtent * 2;
  let stamp = stampGeometry(props.stampSize);
  if (groupWidthFor(stamp.halfExtent) > safeWidth) {
    const room = safeWidth - (chipWidth - stampOverlapPx);
    stamp = stampGeometry(Math.max(44, Math.floor((props.stampSize * room) / (stamp.halfExtent * 2))));
  }
  const groupWidth = Math.min(safeWidth, groupWidthFor(stamp.halfExtent));
  const chipLeft = Math.round(zones.safe.x0 + shakeAmplitudePx + (safeWidth - groupWidth) / 2);
  const stampCentreX = Math.round(chipLeft + chipWidth - stampOverlapPx + stamp.halfExtent);
  const stampWidth = stamp.width;
  const stampHeight = stamp.height;

  const enterFrame = secondsToFrames(props.enterAt, fps);
  const chips = props.domains.map((domain, index) => {
    const at = props.stampAt[index];
    const stampFrame = at === undefined ? null : secondsToFrames(at, fps);
    const staggered = enterFrame + index * motion.staggerFrames;
    const latestForStamp = stampFrame === null ? staggered : stampFrame - stampLeadFrames - chipSettleFrames;
    return {
      domain,
      index,
      stampFrame,
      start: Math.max(0, Math.min(staggered, latestForStamp)),
      top: stackTop + index * (chipHeight + chipGapPx),
    };
  });

  const exitEnd = props.exitAt === undefined ? durationInFrames : Math.min(durationInFrames, secondsToFrames(props.exitAt, fps));
  if (frame >= exitEnd) {
    return null;
  }
  const leaving = exitAmount(frame, exitEnd);
  const visibility = exitOpacity(frame, exitEnd);
  const firstStamp = chips[0]?.stampFrame ?? null;
  const shake = props.shakeFirstStamp && firstStamp !== null ? shakeOffset(frame, firstStamp, shakeFrames, shakeAmplitudePx) : { x: 0, y: 0 };
  const stampColor = toneColor(props.stampTone);

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: visibility,
          transform: `translate(${shake.x}px, ${shake.y + exitDrift(leaving, 24)}px)`,
        }}
      >
        {chips.map(({ domain, index, start, stampFrame, top }) => {
          const hit = stampFrame === null ? 0 : interpolate(frame, [stampFrame, stampFrame + hitFrames], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <div
              key={`${domain}-${index}`}
              style={{
                position: "absolute",
                left: chipLeft,
                top,
                width: chipWidth,
                height: chipHeight,
                boxSizing: "border-box",
                borderRadius: Math.round(chipHeight * 0.3),
                background: `linear-gradient(180deg, ${colors.navyTile} 0%, ${colors.navyPanel} 100%)`,
                border: `${surface.borderPx}px solid ${interpolateColors(hit, [0, 1], [colors.border, stampColor])}`,
                boxShadow: `inset 0 1px 0 rgba(255,255,255,0.06), 0 14px 32px rgba(0,0,0,0.38), 0 3px 8px rgba(0,0,0,0.3)`,
                display: "flex",
                alignItems: "center",
                paddingLeft: chipPadLeft,
                gap: iconGapPx,
                opacity: frame < start ? 0 : fadeIn(frame, start),
                transform: `translateY(${settleOffset(frame, start, motion.arriveFromOffsetPx)}px)`,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  background: `linear-gradient(90deg, ${toneFill(props.stampTone, 0.05)} 0%, ${toneFill(props.stampTone, 0.22)} 100%)`,
                  opacity: hit,
                }}
              />
              <Icon
                name={props.icon}
                size={iconPx}
                strokeWidth={1.8}
                color={interpolateColors(hit, [0, 1], [colors.muted, stampColor])}
                style={{ position: "relative", flexShrink: 0 }}
              />
              <div
                style={{
                  position: "relative",
                  fontFamily: domainFamily,
                  fontWeight: domainWeight,
                  fontSize: props.domainSize,
                  letterSpacing: "-0.01em",
                  lineHeight: 1,
                  whiteSpace: "nowrap",
                  color: interpolateColors(hit, [0, 1], [colors.text, "#C9CEDA"]),
                }}
              >
                {domain}
              </div>
            </div>
          );
        })}
        {chips.map(({ domain, index, stampFrame, top }) => {
          if (stampFrame === null || frame < stampFrame - stampLeadFrames) {
            return null;
          }
          const centreY = top + chipHeight / 2;
          const stampMotion = stampStyle(frame, stampFrame - stampLeadFrames, props.stampRotateDeg);
          const lift = interpolate(frame, [stampFrame - stampLeadFrames, stampFrame], [1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const flash = interpolate(frame, [stampFrame, stampFrame + 1, stampFrame + 10], [0, 0.55, 0.16], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          return (
            <div key={`stamp-${domain}-${index}`}>
              <div
                style={{
                  position: "absolute",
                  left: stampCentreX - stampWidth * 0.75,
                  top: centreY - stampHeight * 1.1,
                  width: stampWidth * 1.5,
                  height: stampHeight * 2.2,
                  background: `radial-gradient(closest-side, ${toneFill(props.stampTone, 0.9)} 0%, ${toneFill(props.stampTone, 0.25)} 45%, ${toneFill(props.stampTone, 0)} 100%)`,
                  opacity: flash,
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: Math.round(stampCentreX - stampWidth / 2),
                  top: Math.round(centreY - stampHeight / 2),
                  width: stampWidth,
                  height: stampHeight,
                  boxSizing: "border-box",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 14,
                  border: `${stampBorderPx}px solid ${stampColor}`,
                  background: "rgba(10,14,30,0.82)",
                  boxShadow: `inset 0 0 0 4px rgba(10,14,30,0.82), inset 0 0 0 6px ${toneFill(props.stampTone, 0.7)}, 0 ${Math.round(6 + lift * 18)}px ${Math.round(14 + lift * 30)}px rgba(0,0,0,${0.45 - lift * 0.15})`,
                  fontFamily: fontFamilies.sans,
                  fontWeight: 800,
                  fontSize: stamp.fontSize,
                  letterSpacing: "0.06em",
                  lineHeight: 1,
                  paddingTop: Math.round(stamp.fontSize * 0.08),
                  paddingLeft: "0.06em",
                  color: stampColor,
                  textTransform: "uppercase",
                  whiteSpace: "nowrap",
                  opacity: stampMotion.opacity,
                  transform: stampMotion.transform,
                }}
              >
                {props.stampLabel}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export default DomainChips;
