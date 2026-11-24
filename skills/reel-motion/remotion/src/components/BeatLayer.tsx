import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import { colors, layout } from "../theme";
import type { Beat } from "../types";
import { registry } from "./registry";

const placeholderRowPx = 128;

const MissingComponent = ({ beat, row }: { beat: Beat; row: number }) => (
  <AbsoluteFill style={{ pointerEvents: "none" }}>
    <div
      style={{
        position: "absolute",
        left: layout.safe.x0,
        top: layout.safe.y0 + (row % 9) * placeholderRowPx,
        width: layout.safe.x1 - layout.safe.x0,
        height: placeholderRowPx - 12,
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
      }}
    >
      <div>MISSING: {beat.component}</div>
      <div style={{ fontSize: 30, fontWeight: 500 }}>
        {beat.id} {beat.from.toFixed(2)}-{beat.to.toFixed(2)} s
      </div>
    </div>
  </AbsoluteFill>
);

export const BeatLayer = ({ beats }: { beats: Beat[] }) => {
  const { fps } = useVideoConfig();
  return (
    <>
      {beats.map((beat, index) => {
        const from = Math.round(beat.from * fps);
        const durationInFrames = Math.max(1, Math.round(beat.to * fps) - from);
        const Component = registry[beat.component];
        return (
          <Sequence key={beat.id} name={`${beat.id} ${beat.component}`} from={from} durationInFrames={durationInFrames}>
            {Component ? <Component beat={beat} /> : <MissingComponent beat={beat} row={index} />}
          </Sequence>
        );
      })}
    </>
  );
};
