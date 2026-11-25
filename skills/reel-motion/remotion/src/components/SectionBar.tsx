import { useMemo } from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { railStatesAt } from "../lib/rail";
import { layout, motion, type } from "../theme";
import { sectionBarSchema, type Beat } from "../types";
import { defaultRailTones, RailSegment, railVisualAt } from "./beats/titles-rail/shared";
import { visibleWindows } from "./TopLogo";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const railGapPx = 16;

const labelBandPx = 60;

const labelBandMask = "linear-gradient(180deg, transparent 0%, #000 16%, #000 84%, transparent 100%)";

const rollEase = Easing.bezier(0.65, 0, 0.35, 1);

const kickerShadow = "0 2px 6px rgba(4,8,20,0.55)";

const Label = ({ text, centerX, centerY, opacity, offsetY }: { text: string; centerX: number; centerY: number; opacity: number; offsetY: number }) => (
  <div
    style={{
      position: "absolute",
      left: centerX - 450,
      width: 900,
      top: centerY,
      transform: `translateY(-50%) translateY(${offsetY.toFixed(2)}px)`,
      opacity,
      textAlign: "center",
      whiteSpace: "nowrap",
      fontFamily: type.kicker.fontFamily,
      fontWeight: type.kicker.fontWeight,
      fontSize: type.kicker.fontSize,
      letterSpacing: type.kicker.letterSpacing,
      paddingLeft: type.kicker.letterSpacing,
      textTransform: "uppercase",
      color: type.kicker.color,
      lineHeight: 1.1,
      textShadow: kickerShadow,
    }}
  >
    {text}
  </div>
);

export const SectionBar = ({ sectionBar, beats }: { sectionBar: unknown; beats: Beat[] }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const settings = useMemo(() => sectionBarSchema.parse(sectionBar ?? {}), [sectionBar]);
  const windows = useMemo(
    () => visibleWindows(settings.ranges, settings.hideDuring, beats, fps, durationInFrames),
    [settings, beats, fps, durationInFrames],
  );
  const sections = useMemo(
    () => [...settings.sections].sort((a, b) => a.from - b.from).map((section) => ({ ...section, frame: Math.round(section.from * fps) })),
    [settings.sections, fps],
  );
  const railEvents = useMemo(
    () => settings.railEvents.map((event) => ({ ...event, t: Math.round(event.t * fps) / fps })),
    [settings.railEvents, fps],
  );
  if (!settings.enabled) {
    return null;
  }
  const window = windows.find((item) => frame >= item.start && frame < item.end);
  if (!window) {
    return null;
  }
  const enter = settings.enterFrames === 0 ? 1 : interpolate(frame + 1, [window.start, window.start + settings.enterFrames], [0, 1], { ...clamp, easing: motion.ease });
  const exit = window.end >= durationInFrames ? 0 : interpolate(frame, [window.end - settings.exitFrames, window.end], [0, 1], { ...clamp, easing: motion.exitEase });
  const opacity = Math.min(interpolate(enter, [0, 0.6], [0, 1], clamp), 1 - exit);
  if (opacity <= 0) {
    return null;
  }
  const groupY = -14 * (1 - enter) - 8 * exit;

  const currentIndex = sections.reduce((found, section, index) => (section.frame <= frame ? index : found), -1);
  const labels: { key: string; text: string; opacity: number; offsetY: number }[] = [];
  const current = sections[currentIndex];
  const previous = sections[currentIndex - 1];
  const rolling = current !== undefined && current.frame > window.start;
  const roll = rolling ? interpolate(frame + 1, [current.frame, current.frame + settings.rollFrames], [0, 1], { ...clamp, easing: rollEase }) : 1;
  if (current && current.label) {
    labels.push({ key: `${currentIndex}`, text: current.label, opacity: interpolate(roll, [0, 0.6], [0, 1], clamp), offsetY: labelBandPx * (1 - roll) });
  }
  if (rolling && previous && previous.label && roll < 1) {
    labels.push({ key: `${currentIndex - 1}`, text: previous.label, opacity: interpolate(roll, [0.4, 1], [1, 0], clamp), offsetY: -labelBandPx * roll });
  }

  const railWidth = settings.segments * layout.rail.segmentW + Math.max(0, settings.segments - 1) * railGapPx;
  const railDx = settings.centerX - railWidth / 2 - layout.rail.x;
  const railDy = settings.railY - layout.rail.y;
  const beatSec = frame / fps;
  const states = settings.segments > 0 ? railStatesAt(railEvents, settings.segments, beatSec) : [];

  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity, transform: `translateY(${groupY.toFixed(2)}px)` }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: settings.kickerY - labelBandPx / 2, height: labelBandPx, overflow: "hidden", maskImage: labelBandMask, WebkitMaskImage: labelBandMask }}>
        {labels.map((label) => (
          <Label key={label.key} text={label.text} centerX={settings.centerX} centerY={labelBandPx / 2} opacity={label.opacity} offsetY={label.offsetY} />
        ))}
      </div>
      {states.length > 0 ? (
        <AbsoluteFill style={{ transform: `translate(${railDx}px, ${railDy}px)` }}>
          {states.map((segment, index) => {
            const visual = railVisualAt(segment, index, beatSec, fps, defaultRailTones);
            return (
              <RailSegment
                key={index}
                box={visual.box}
                fill={visual.fill}
                borderColor={visual.borderColor}
                glowColor={visual.glowColor}
                glow={visual.glow}
                checkProgress={visual.checkProgress}
                transform={`translateX(${visual.shakeX}px) scaleY(${visual.flipScaleY})`}
              />
            );
          })}
        </AbsoluteFill>
      ) : null}
    </AbsoluteFill>
  );
};

