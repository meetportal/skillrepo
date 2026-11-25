import { AbsoluteFill, interpolate } from "remotion";
import { z } from "zod";
import { timeSchema, toneSchema } from "../../lib/beatSchemas";
import { railEventSchema, railEventsOnFrames, railStatesAt } from "../../lib/rail";
import { colors, fontFamilies, motion, type as typeTokens, zones } from "../../theme";
import type { BeatProps } from "../../types";
import { checklistRowRect, entranceProgress, entranceStyle, exitProgress, stampScale, toneColor } from "../ui";
import {
  alpha,
  clampRange,
  defaultRailTones,
  easeInOutTravel,
  fitLines,
  lerp,
  lerpBox,
  RailSegment,
  railChipRect,
  railVisualAt,
  SurfacePanel,
  useFontsLoaded,
} from "./titles-rail/shared";

export const schema = z.object({
  items: z.array(z.string().min(1)).min(1).max(5),
  tone: toneSchema.default("success"),
  fromRail: z.boolean().default(true),
  railEvents: z.array(railEventSchema).default([]),
  checkTimes: z.array(timeSchema).default([]),
  itemSizePx: z.number().min(44).max(72).default(52),
  travelFrames: z.number().int().min(6).max(24).default(12),
  exitMode: z.enum(["all", "content", "none"]).default("all"),
});

export type ChecklistProps = z.infer<typeof schema>;

const travelStaggerFrames = 0;

const Checklist = ({ props, frame, durationInFrames, fps, toFrame }: BeatProps<ChecklistProps>) => {
  const ready = useFontsLoaded();
  const color = toneColor(props.tone);
  const count = props.items.length;
  const rows = props.items.map((_, index) => checklistRowRect(index, count));
  const firstRow = checklistRowRect(0, count);
  const textLeft = firstRow.iconBox.x1 + 32;
  const textWidth = firstRow.x1 - textLeft;
  const fits = props.items.map((item) =>
    fitLines({ text: item, maxWidth: textWidth, maxSize: props.itemSizePx, minSize: typeTokens.cardMinPx, fontWeight: 600, maxLines: 1, ready }),
  );
  const itemPx = Math.min(...fits.map((fit) => fit.fontSize));
  const beatSec = frame / fps;
  const railStates = props.railEvents.length > 0 ? railStatesAt(railEventsOnFrames(props.railEvents, toFrame, fps), count, beatSec) : null;
  const tones = { ...defaultRailTones, fixed: props.tone };

  const exitAll = props.exitMode === "all" ? exitProgress(frame, durationInFrames) : 0;
  const exitContent = props.exitMode === "none" ? 0 : exitProgress(frame, durationInFrames);
  const cardP = entranceProgress(frame, 0);
  const cardOpacity = interpolate(cardP, [0, 0.45], [0, 1], clampRange) * (1 - exitAll);
  const cardLift = (1 - cardP) * motion.arriveFromOffsetPx + exitAll * 12;

  const landFrame = (index: number) => {
    if (props.fromRail) {
      return index * travelStaggerFrames + props.travelFrames;
    }
    const at = props.checkTimes[index];
    return at === undefined ? 6 + index * motion.staggerFrames : toFrame(at);
  };

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{ position: "absolute", inset: 0, opacity: cardOpacity, transform: `translateY(${cardLift}px)` }}>
        <SurfacePanel box={zones.card}>
          {rows.slice(1).map((row, index) => (
            <div
              key={index}
              style={{
                position: "absolute",
                left: row.x0 - zones.card.x0,
                right: zones.card.x1 - row.x1,
                top: row.y0 - zones.card.y0,
                height: 1,
                background: alpha(colors.text, 0.08),
                opacity: 1 - exitContent,
              }}
            />
          ))}
        </SurfacePanel>
      </div>
      {rows.map((row, index) => {
        const land = landFrame(index);
        const textStart = props.fromRail ? Math.min(land - 5, index * motion.staggerFrames) : land - 5;
        const text = entranceStyle(frame, { start: textStart, from: "left" });
        const textOpacity = text.opacity * (1 - exitContent);
        const rowCenter = (row.y0 + row.y1) / 2;
        return (
          <div
            key={`text-${index}`}
            style={{
              position: "absolute",
              left: textLeft,
              width: textWidth,
              top: rowCenter,
              transform: `translateY(-50%) ${text.transform} translateY(${-exitContent * 10}px)`,
              opacity: textOpacity,
              fontFamily: fontFamilies.sans,
              fontWeight: 600,
              fontSize: itemPx,
              lineHeight: 1.1,
              color: colors.text,
              whiteSpace: "nowrap",
            }}
          >
            {props.items[index]}
          </div>
        );
      })}
      {rows.map((row, index) => {
        const target = row.iconBox;
        if (props.fromRail) {
          const start = index * travelStaggerFrames;
          const travel = interpolate(frame, [start, start + props.travelFrames], [0, 1], { ...clampRange, easing: easeInOutTravel });
          const railSegment = railStates?.[index];
          const railVisual = railSegment ? railVisualAt(railSegment, index, beatSec, fps, tones) : null;
          const fromBox = railVisual ? railVisual.box : railChipRect(index);
          const box = lerpBox(fromBox, target, travel);
          const check = railVisual ? lerp(railVisual.checkProgress, 1, travel) : 1;
          const glow = railVisual ? lerp(railVisual.glow, 0.5, travel) : 0.7;
          const fill = railVisual && railVisual.state === "fixed" ? railVisual.fill : color;
          const flipScaleY = railVisual ? lerp(railVisual.flipScaleY, 1, travel) : 1;
          const landKick = interpolate(frame, [start + props.travelFrames - 1, start + props.travelFrames + 4], [1, 0], clampRange);
          return (
            <RailSegment
              key={`chip-${index}`}
              box={box}
              fill={travel >= 1 ? color : fill}
              borderColor={alpha(colors.text, 0.28)}
              glowColor={color}
              glow={glow + landKick * 0.4}
              checkProgress={check}
              opacity={1 - exitContent}
              transform={`scaleY(${flipScaleY})`}
            />
          );
        }
        const land = landFrame(index);
        const appear = interpolate(frame, [land, land + 2], [0, 1], clampRange);
        const scale = stampScale(frame, land);
        const check = interpolate(frame, [land + 1, land + 7], [0, 1], clampRange);
        return (
          <RailSegment
            key={`chip-${index}`}
            box={target}
            fill={color}
            borderColor={alpha(colors.text, 0.28)}
            glowColor={color}
            glow={0.6}
            checkProgress={check}
            opacity={appear * (1 - exitContent)}
            transform={`scale(${scale})`}
          />
        );
      })}
    </AbsoluteFill>
  );
};

export default Checklist;
