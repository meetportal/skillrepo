import { useMemo } from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { motion } from "../theme";
import { topLogoSchema, type Beat, type TopLogoProps } from "../types";
import { resolveLogoSrc } from "./beats/brand-end/logo";

type Window = { start: number; end: number };

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const subtract = (windows: Window[], hole: Window) =>
  windows.flatMap((window) => {
    if (hole.end <= window.start || hole.start >= window.end) {
      return [window];
    }
    return [
      ...(hole.start > window.start ? [{ start: window.start, end: hole.start }] : []),
      ...(hole.end < window.end ? [{ start: hole.end, end: window.end }] : []),
    ];
  });

export const topLogoWindows = (settings: TopLogoProps, beats: Beat[], fps: number, totalFrames: number): Window[] => {
  const toFrame = (sec: number) => Math.round(sec * fps);
  const ranges = settings.ranges.length > 0 ? settings.ranges : [{ from: 0, to: totalFrames / fps }];
  const base = ranges
    .map((range) => ({ start: toFrame(range.from), end: Math.min(totalFrames, toFrame(range.to)) }))
    .filter((window) => window.end > window.start);
  const holes = beats
    .filter((beat) => settings.hideDuring.includes(beat.component))
    .map((beat) => ({ start: toFrame(beat.from), end: toFrame(beat.to) }));
  return holes.reduce(subtract, base).filter((window) => window.end > window.start);
};

export const TopLogo = ({ topLogo, beats }: { topLogo: unknown; beats: Beat[] }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const settings = useMemo(() => topLogoSchema.parse(topLogo ?? {}), [topLogo]);
  const windows = useMemo(() => topLogoWindows(settings, beats, fps, durationInFrames), [settings, beats, fps, durationInFrames]);
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
  const offsetY = -settings.slidePx * (1 - enter) - 8 * exit;
  const shadow = settings.shadow;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {settings.scrim > 0 ? (
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: settings.centerY,
            width: settings.widthPx * 2,
            height: settings.widthPx * 0.8,
            opacity: opacity * settings.scrim,
            transform: `translate(-50%, -50%) translateY(${offsetY.toFixed(2)}px)`,
            background: "radial-gradient(closest-side, rgba(4,8,20,0.8) 0%, rgba(4,8,20,0.6) 30%, rgba(4,8,20,0.3) 60%, rgba(4,8,20,0.1) 82%, rgba(4,8,20,0) 100%)",
          }}
        />
      ) : null}
      <Img
        src={resolveLogoSrc(settings.logo)}
        style={{
          position: "absolute",
          left: "50%",
          top: settings.centerY,
          width: settings.widthPx,
          height: "auto",
          opacity,
          transform: `translate(-50%, -50%) translateY(${offsetY.toFixed(2)}px)`,
          filter: [
            `drop-shadow(0 1px 2px rgba(4,8,20,${(0.7 * shadow).toFixed(3)}))`,
            `drop-shadow(0 3px 10px rgba(4,8,20,${(0.5 * shadow).toFixed(3)}))`,
            `drop-shadow(0 0 22px rgba(4,8,20,${(0.35 * shadow).toFixed(3)}))`,
          ].join(" "),
        }}
      />
    </AbsoluteFill>
  );
};
