import { AbsoluteFill } from "remotion";
import { z } from "zod";
import { timeSchema, toneSchema } from "../../lib/beatSchemas";
import { railEventSchema, railEventsOnFrames, railStatesAt } from "../../lib/rail";
import type { BeatProps } from "../../types";
import { entranceStyle, exitStyle, combineMotion } from "../ui";
import { defaultRailTones, RailSegment, railVisualAt } from "./titles-rail/shared";

export const schema = z.object({
  segments: z.number().int().min(1).max(6).default(3),
  events: z.array(railEventSchema).default([]),
  morphIntoChecklistAt: timeSchema.optional(),
  tones: z
    .object({ active: toneSchema.default("accent"), marked: toneSchema.default("danger"), fixed: toneSchema.default("success") })
    .default(defaultRailTones),
  entrance: z.enum(["drop", "none"]).default("drop"),
});

export type ProgressRailProps = z.infer<typeof schema>;

const ProgressRail = ({ props, frame, durationInFrames, fps, toFrame }: BeatProps<ProgressRailProps>) => {
  const morphFrame = props.morphIntoChecklistAt === undefined ? null : toFrame(props.morphIntoChecklistAt);
  if (morphFrame !== null && frame >= morphFrame) {
    return null;
  }
  const beatSec = frame / fps;
  const states = railStatesAt(railEventsOnFrames(props.events, toFrame, fps), props.segments, beatSec);
  const exitEnd = morphFrame !== null && morphFrame <= durationInFrames ? null : durationInFrames;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {states.map((segment, index) => {
        const visual = railVisualAt(segment, index, beatSec, fps, props.tones);
        const enter =
          props.entrance === "drop" ? entranceStyle(frame, { start: 0, from: "down", index }) : { opacity: 1, transform: "none" };
        const motion = exitEnd === null ? enter : combineMotion(enter, exitStyle(frame, exitEnd, { to: "down" }));
        return (
          <div key={index} style={{ position: "absolute", inset: 0, opacity: motion.opacity, transform: motion.transform }}>
            <RailSegment
              box={visual.box}
              fill={visual.fill}
              borderColor={visual.borderColor}
              glowColor={visual.glowColor}
              glow={visual.glow}
              checkProgress={visual.checkProgress}
              transform={`translateX(${visual.shakeX}px) scaleY(${visual.flipScaleY})`}
            />
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

export default ProgressRail;
