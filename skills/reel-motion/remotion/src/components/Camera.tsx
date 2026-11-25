import { useMemo } from "react";
import { AbsoluteFill, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { applyKick, buildShots, kickKeys, kickOffsetAt, resolveTransform, sampleCamera, shotAtFrame, sortCameraKeys } from "../lib/camera";
import { camera as cameraTokens, layout } from "../theme";
import type { CameraKey, CameraLimits, Cues } from "../types";

const resolveSrc = (src: string) => (/^https?:\/\//.test(src) ? src : staticFile(src));

export const Camera = ({ src, keys, cues, limits }: { src: string; keys: CameraKey[]; cues: Cues; limits?: CameraLimits }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const sortedKeys = useMemo(() => sortCameraKeys(keys, fps), [keys, fps]);
  const kicks = useMemo(() => kickKeys(keys), [keys]);
  const shots = useMemo(() => buildShots(cues, fps, durationInFrames), [cues, fps, durationInFrames]);
  const maxScale = limits?.maxScale ?? cameraTokens.maxScale;
  const face = shotAtFrame(shots, frame)?.face;
  const origin = face ? { x: face.cx, y: face.cy } : { x: layout.width / 2, y: layout.height / 2 };
  const base = resolveTransform(sampleCamera(sortedKeys, frame, fps, durationInFrames), origin, maxScale);
  const { scale, tx, ty, rotateDeg } = applyKick(base, kickOffsetAt(kicks, frame, fps), origin, maxScale);
  const videoFrames = cues.segments.length > 0 ? Math.round(Math.max(...cues.segments.map((segment) => segment.end)) * fps) : durationInFrames;

  if (!src) {
    return <AbsoluteFill style={{ backgroundColor: "#000" }} />;
  }

  return (
    <AbsoluteFill style={{ backgroundColor: "#000", overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          transformOrigin: `${origin.x}px ${origin.y}px`,
          transform: rotateDeg === 0 ? `translate(${tx}px, ${ty}px) scale(${scale})` : `translate(${tx}px, ${ty}px) rotate(${rotateDeg}deg) scale(${scale})`,
        }}
      >
        <Sequence durationInFrames={Math.max(1, Math.min(videoFrames, durationInFrames))} layout="none">
          <OffthreadVideo src={resolveSrc(src)} muted style={{ width: "100%", height: "100%" }} />
        </Sequence>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
