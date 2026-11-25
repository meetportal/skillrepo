import { useMemo, type ReactNode } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { buildShots, shotAtFrame } from "../lib/camera";
import { windowBox, windowVideoTransform } from "../lib/stage";
import { colors, framed, layout as layoutTokens } from "../theme";
import type { Cues, LayoutProps } from "../types";
import { alpha } from "./beats/titles-rail/shared";

export const FramedBackground = ({ settings }: { settings: LayoutProps }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const phase = ((frame / fps) * 2 * Math.PI) / settings.background.periodSec;
  const glowX = layoutTokens.width / 2 + framed.glowDriftXPx * Math.sin(phase);
  const glowY = framed.glowCenterY + framed.glowDriftYPx * Math.sin(phase * 0.73 + 1.1);
  const warmX = layoutTokens.width / 2 - framed.glowDriftXPx * 0.8 * Math.sin(phase * 0.81 + 0.6);
  const warmY = framed.warmCenterY + framed.glowDriftYPx * 0.5 * Math.cos(phase * 0.9);
  const { glow, grid } = settings.background;
  return (
    <AbsoluteFill style={{ background: `linear-gradient(180deg, ${colors.navyTop} 0%, ${colors.navyBottom} 100%)` }}>
      {glow > 0 ? (
        <AbsoluteFill
          style={{
            background: [
              `radial-gradient(${framed.glowRadiusPx}px ${framed.glowRadiusPx * 0.8}px at ${glowX.toFixed(1)}px ${glowY.toFixed(1)}px, ${alpha(colors.brandBlue, framed.glowAlpha * glow)} 0%, ${alpha(colors.brandBlue, 0)} 100%)`,
              `radial-gradient(${framed.warmRadiusPx}px ${framed.warmRadiusPx * 0.7}px at ${warmX.toFixed(1)}px ${warmY.toFixed(1)}px, ${alpha(colors.accent, framed.warmAlpha * glow)} 0%, ${alpha(colors.accent, 0)} 100%)`,
            ].join(", "),
          }}
        />
      ) : null}
      {grid > 0 ? (
        <AbsoluteFill
          style={{
            backgroundImage: [
              `linear-gradient(to right, ${alpha(colors.text, framed.gridAlpha * grid)} 1px, transparent 1px)`,
              `linear-gradient(to bottom, ${alpha(colors.text, framed.gridAlpha * grid)} 1px, transparent 1px)`,
            ].join(", "),
            backgroundSize: `${framed.gridStepPx}px ${framed.gridStepPx}px`,
            backgroundPosition: `${(layoutTokens.width / 2) % framed.gridStepPx}px 0px`,
            maskImage: `radial-gradient(${framed.gridMaskPx}px ${framed.gridMaskPx * 1.1}px at ${glowX.toFixed(1)}px ${glowY.toFixed(1)}px, #000 0%, rgba(0,0,0,0.35) 55%, transparent 100%)`,
            WebkitMaskImage: `radial-gradient(${framed.gridMaskPx}px ${framed.gridMaskPx * 1.1}px at ${glowX.toFixed(1)}px ${glowY.toFixed(1)}px, #000 0%, rgba(0,0,0,0.35) 55%, transparent 100%)`,
          }}
        />
      ) : null}
    </AbsoluteFill>
  );
};

export const FramedWindow = ({ settings, cues, children, overlay }: { settings: LayoutProps; cues: Cues; children: ReactNode; overlay?: ReactNode }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const shots = useMemo(() => buildShots(cues, fps, durationInFrames), [cues, fps, durationInFrames]);
  const face = shotAtFrame(shots, frame)?.face;
  const origin = face ? { x: face.cx, y: face.cy } : { x: layoutTokens.width / 2, y: layoutTokens.height * framed.defaultFaceY };
  const box = windowBox(settings);
  const video = windowVideoTransform(settings, origin);
  const radius = settings.window.radius;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: box.x0,
          top: box.y0,
          width: box.x1 - box.x0,
          height: box.y1 - box.y0,
          borderRadius: radius,
          boxShadow: framed.windowShadow,
          backgroundColor: "#000",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: box.x0,
          top: box.y0,
          width: box.x1 - box.x0,
          height: box.y1 - box.y0,
          borderRadius: radius,
          overflow: "hidden",
          isolation: "isolate",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: video.x - box.x0,
            top: video.y - box.y0,
            width: layoutTokens.width,
            height: layoutTokens.height,
            transformOrigin: "0 0",
            transform: `scale(${video.scale})`,
          }}
        >
          {children}
        </div>
        {overlay}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `linear-gradient(180deg, ${alpha(colors.text, framed.sheenAlpha)} 0%, ${alpha(colors.text, 0)} 18%)`,
          }}
        />
      </div>
      {settings.window.borderPx > 0 ? (
        <div
          style={{
            position: "absolute",
            left: box.x0,
            top: box.y0,
            width: box.x1 - box.x0,
            height: box.y1 - box.y0,
            boxSizing: "border-box",
            borderRadius: radius,
            border: `${settings.window.borderPx}px solid ${colors.border}`,
          }}
        />
      ) : null}
    </AbsoluteFill>
  );
};
