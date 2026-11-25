import { useMemo, type ReactNode } from "react";
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { beatSecondsToLocalFrame } from "../lib/beat";
import { windowBox } from "../lib/stage";
import { colors, layout, zones } from "../theme";
import type { Beat, LayoutProps } from "../types";
import { registry } from "./registry";

const placeholderRowPx = 128;

const ErrorBox = ({ beat, row, title, details }: { beat: Beat; row: number; title: string; details: string[] }) => (
  <AbsoluteFill style={{ pointerEvents: "none" }}>
    <div
      style={{
        position: "absolute",
        left: layout.safe.x0,
        top: layout.safe.y0 + (row % 9) * placeholderRowPx,
        width: layout.safe.x1 - layout.safe.x0,
        minHeight: placeholderRowPx - 12,
        border: "6px solid #FF0000",
        backgroundColor: "rgba(255,0,0,0.35)",
        color: colors.text,
        fontFamily: "Poppins",
        fontWeight: 700,
        fontSize: 40,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        gap: 4,
        padding: 8,
      }}
    >
      <div>
        {title}: {beat.component}
      </div>
      <div style={{ fontSize: 30, fontWeight: 500 }}>
        {beat.id} {beat.from.toFixed(2)}-{beat.to.toFixed(2)} s
      </div>
      {details.slice(0, 4).map((detail) => (
        <div key={detail} style={{ fontSize: 26, fontWeight: 500 }}>
          {detail}
        </div>
      ))}
    </div>
  </AbsoluteFill>
);

const BeatHost = ({ beat, row, durationInFrames }: { beat: Beat; row: number; durationInFrames: number }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const definition = registry[beat.component];
  const parsed = useMemo(() => definition?.parse(beat.props), [definition, beat.props]);
  if (!definition || !parsed) {
    return <ErrorBox beat={beat} row={row} title="MISSING" details={[]} />;
  }
  if (!parsed.ok) {
    return <ErrorBox beat={beat} row={row} title="BAD PROPS" details={parsed.issues} />;
  }
  const toFrame = (beatSec: number) => beatSecondsToLocalFrame(beatSec, beat.from, fps);
  return definition.render({ beat, frame, durationInFrames, fps, toFrame }, parsed.value);
};

export const orderBeats = (beats: Beat[]) =>
  beats.map((beat, index) => ({ beat, index })).sort((a, b) => (a.beat.layer ?? 0) - (b.beat.layer ?? 0) || a.index - b.index);

const cardOrigin = { x: (zones.card.x0 + zones.card.x1) / 2, y: (zones.card.y0 + zones.card.y1) / 2 };

const FramedBeat = ({ beat, stage, children }: { beat: Beat; stage: LayoutProps; children: ReactNode }) => {
  if (beat.mode === "card") {
    const { dx, dy, scale } = stage.cardBeats;
    return (
      <AbsoluteFill style={{ transformOrigin: `${cardOrigin.x}px ${cardOrigin.y}px`, transform: `translate(${dx}px, ${dy}px) scale(${scale})` }}>
        {children}
      </AbsoluteFill>
    );
  }
  if (beat.mode === "takeover" && stage.takeoverClip === "window") {
    const box = windowBox(stage);
    return (
      <AbsoluteFill
        style={{
          clipPath: `inset(${box.y0}px ${layout.width - box.x1}px ${layout.height - box.y1}px ${box.x0}px round ${stage.window.radius}px)`,
        }}
      >
        {children}
      </AbsoluteFill>
    );
  }
  return <>{children}</>;
};

export const BeatLayer = ({ beats, stage }: { beats: Beat[]; stage?: LayoutProps }) => {
  const { fps } = useVideoConfig();
  const ordered = useMemo(() => orderBeats(beats), [beats]);
  return (
    <>
      {ordered.map(({ beat, index }) => {
        const from = Math.round(beat.from * fps);
        const durationInFrames = Math.max(1, Math.round(beat.to * fps) - from);
        return (
          <Sequence key={beat.id} name={`${beat.id} ${beat.component}`} from={from} durationInFrames={durationInFrames}>
            {stage ? (
              <FramedBeat beat={beat} stage={stage}>
                <BeatHost beat={beat} row={index} durationInFrames={durationInFrames} />
              </FramedBeat>
            ) : (
              <BeatHost beat={beat} row={index} durationInFrames={durationInFrames} />
            )}
          </Sequence>
        );
      })}
    </>
  );
};
