import { useEffect, useState } from "react";
import { AbsoluteFill, interpolate, OffthreadVideo, staticFile, useDelayRender } from "remotion";
import { z } from "zod";
import { colors, motion, surface, zones } from "../../theme";
import type { BeatProps } from "../../types";
import { boxStyle } from "../ui";

const boxSchema = z.object({ x0: z.number(), x1: z.number(), y0: z.number(), y1: z.number() });

export const schema = z.object({
  src: z.string().min(1),
  fit: z.enum(["full", "card"]).default("full"),
  box: boxSchema.optional(),
  radius: z.number().min(0).max(120).optional(),
  enterFrames: z.number().int().min(0).max(20).optional(),
  exitFrames: z.number().int().min(0).max(20).default(0),
  startFromFrame: z.number().int().min(0).default(0),
  three: z.record(z.string(), z.unknown()).optional(),
});

export type VideoInsertProps = z.infer<typeof schema>;

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const cardEnterFrames = 8;
const firstFrameOpacity = 0.4;

const resolveSrc = (src: string) => (/^https?:\/\//.test(src) ? src : staticFile(src));

const useRequiredFile = (url: string) => {
  const { delayRender, continueRender, cancelRender } = useDelayRender();
  const [handle] = useState(() => delayRender(`VideoInsert ${url}`));
  useEffect(() => {
    fetch(url, { method: "HEAD" })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`VideoInsert: ${url} returned ${response.status}; render the 3D inserts first (reel-3d render3d.py)`);
        }
        continueRender(handle);
      })
      .catch((error: unknown) => cancelRender(error instanceof Error ? error : new Error(String(error))));
  }, [url, handle, continueRender, cancelRender]);
};

const VideoInsert = ({ props, frame, durationInFrames }: BeatProps<VideoInsertProps>) => {
  const url = resolveSrc(props.src);
  useRequiredFile(url);
  const card = props.fit === "card";
  const enterFrames = props.enterFrames ?? (card ? cardEnterFrames : 0);
  const enter = enterFrames > 0 ? interpolate(frame + 1, [0, enterFrames], [0, 1], { ...clamp, easing: motion.ease }) : 1;
  const exit = props.exitFrames > 0 ? interpolate(frame, [durationInFrames - props.exitFrames, durationInFrames - 1], [0, 1], { ...clamp, easing: motion.exitEase }) : 0;
  const opacity = (enterFrames > 0 ? interpolate(frame, [0, Math.min(2, enterFrames)], [firstFrameOpacity, 1], clamp) : 1) * (1 - exit);
  const video = (
    <OffthreadVideo src={url} muted trimBefore={props.startFromFrame} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
  );
  if (!card) {
    return <AbsoluteFill style={{ opacity, transform: enter < 1 ? `scale(${1 + (motion.arriveFromScale - 1) * 0.25 * (1 - enter)})` : undefined }}>{video}</AbsoluteFill>;
  }
  const box = props.box ?? zones.card;
  const radius = props.radius ?? surface.cardRadius;
  const scale = 1 + (motion.arriveFromScale - 1) * (1 - enter) - 0.04 * exit;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          ...boxStyle(box),
          borderRadius: radius,
          overflow: "hidden",
          boxShadow: surface.cardShadow,
          backgroundColor: colors.navyPanel,
          opacity,
          transform: `scale(${scale})`,
        }}
      >
        {video}
        <div style={{ position: "absolute", inset: 0, boxSizing: "border-box", borderRadius: radius, border: `${surface.borderPx}px solid ${colors.border}` }} />
      </div>
    </AbsoluteFill>
  );
};

export default VideoInsert;
