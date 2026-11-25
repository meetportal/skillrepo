import { AbsoluteFill } from "remotion";
import { BeatLayer } from "./components/BeatLayer";
import { Camera } from "./components/Camera";
import { Captions } from "./components/Captions";
import { LookOverlay } from "./components/LookOverlay";
import { TopLogo } from "./components/TopLogo";
import { SafeAreaGuides } from "./components/ui/SafeArea";
import "./fonts";
import type { ReelProps } from "./types";

const hookEndOf = (props: ReelProps) => props.cues.cuts.find((cut) => cut > 0) ?? props.durationSec;

export const Reel = (props: ReelProps) => (
  <AbsoluteFill style={{ backgroundColor: "#000" }}>
    <Camera src={props.aroll} keys={props.camera} cues={props.cues} limits={props.cameraLimits} />
    <LookOverlay look={props.look} />
    <BeatLayer beats={props.beats} />
    <TopLogo topLogo={props.topLogo} beats={props.beats} />
    <Captions
      captions={props.captions}
      accents={props.accents}
      modes={props.captionModes}
      hookEndSec={hookEndOf(props)}
      cuts={props.cues.cuts}
      options={props.captionOptions}
    />
    {props.guides ? <SafeAreaGuides /> : null}
  </AbsoluteFill>
);
