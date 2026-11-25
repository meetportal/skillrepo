import { useMemo } from "react";
import { AbsoluteFill } from "remotion";
import { BeatLayer } from "./components/BeatLayer";
import { Camera } from "./components/Camera";
import { Captions } from "./components/Captions";
import { FramedBackground, FramedWindow } from "./components/FramedStage";
import { LookOverlay } from "./components/LookOverlay";
import { SectionBar } from "./components/SectionBar";
import { TopLogo } from "./components/TopLogo";
import { SafeAreaGuides } from "./components/ui/SafeArea";
import "./fonts";
import { isFramed, resolveLayout } from "./lib/stage";
import type { ReelProps } from "./types";

const hookEndOf = (props: ReelProps) => props.cues.cuts.find((cut) => cut > 0) ?? props.durationSec;

export const Reel = (props: ReelProps) => {
  const stage = useMemo(() => resolveLayout(props.layout), [props.layout]);
  const framed = isFramed(stage);
  const camera = <Camera src={props.aroll} keys={props.camera} cues={props.cues} limits={props.cameraLimits} />;
  const windowSize = { width: stage.window.width, height: stage.window.y1 - stage.window.y0 };
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {framed ? (
        <>
          <FramedBackground settings={stage} />
          <FramedWindow settings={stage} cues={props.cues} overlay={<LookOverlay look={props.look} size={windowSize} />}>
            {camera}
          </FramedWindow>
        </>
      ) : (
        <>
          {camera}
          <LookOverlay look={props.look} />
        </>
      )}
      <BeatLayer beats={props.beats} stage={framed ? stage : undefined} />
      <SectionBar sectionBar={props.sectionBar} beats={props.beats} />
      <TopLogo topLogo={props.topLogo} beats={props.beats} />
      <Captions
        captions={props.captions}
        accents={props.accents}
        modes={props.captionModes}
        hookEndSec={hookEndOf(props)}
        cuts={props.cues.cuts}
        options={props.captionOptions}
        stage={stage}
      />
      {props.guides ? <SafeAreaGuides /> : null}
    </AbsoluteFill>
  );
};
