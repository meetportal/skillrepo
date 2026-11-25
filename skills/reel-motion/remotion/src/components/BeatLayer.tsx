import { useMemo } from "react";
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { beatSecondsToLocalFrame } from "../lib/beat";
import { colors, layout } from "../theme";
import type { Beat } from "../types";
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

export const BeatLayer = ({ beats }: { beats: Beat[] }) => {
  const { fps } = useVideoConfig();
  const ordered = useMemo(() => orderBeats(beats), [beats]);
  return (
    <>
      {ordered.map(({ beat, index }) => {
        const from = Math.round(beat.from * fps);
        const durationInFrames = Math.max(1, Math.round(beat.to * fps) - from);
        return (
          <Sequence key={beat.id} name={`${beat.id} ${beat.component}`} from={from} durationInFrames={durationInFrames}>
            <BeatHost beat={beat} row={index} durationInFrames={durationInFrames} />
          </Sequence>
        );
      })}
    </>
  );
};
