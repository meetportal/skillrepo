import type { ComponentType } from "react";
import { Composition } from "remotion";
import brandJson from "../../../mailinfra-brand/brand.json";
import { AuthShield3D, authShieldDefaults, authShieldTimeline, type AuthShieldProps } from "./beats/AuthShield3D";
import { BrandPatch3D, brandPatchDefaults, brandPatchTimeline, type BrandPatchProps } from "./beats/BrandPatch3D";
import { DomainBurn3D, domainBurnDefaults, domainBurnTimeline, type DomainBurnProps } from "./beats/DomainBurn3D";
import { EnvelopeToSpam3D, envelopeToSpamDefaults, envelopeToSpamTimeline, type EnvelopeToSpamProps } from "./beats/EnvelopeToSpam3D";
import { LogoExtrude3D, logoExtrudeDefaults, logoExtrudeTimeline, type LogoExtrudeProps } from "./beats/LogoExtrude3D";
import { brandAssetFolder, type BrandInput } from "./kit/brand";
import { insertMetadata, type Fit, type InsertProps, type Timeline } from "./kit/insert";

const brand: BrandInput = brandJson;

const takeover = { width: brandJson.layout.width, height: brandJson.layout.height, fit: "full" as Fit };
const card = {
  width: brandJson.layout.cardBox.x1 - brandJson.layout.cardBox.x0,
  height: brandJson.layout.cardBox.y1 - brandJson.layout.cardBox.y0,
  fit: "card" as Fit,
};

type Entry<P extends object> = {
  id: string;
  component: ComponentType<InsertProps<P>>;
  defaults: P;
  timeline: (props: P, frames: number, fps: number) => Timeline;
  size: { width: number; height: number; fit: Fit };
  frames: number;
};

const entry = <P extends object>(value: Entry<P>) => value;

const Insert = <P extends object>({ id, component, defaults, timeline, size, frames }: Entry<P>) => (
  <Composition
    id={id}
    component={component}
    width={size.width}
    height={size.height}
    fps={25}
    durationInFrames={frames}
    calculateMetadata={insertMetadata(id, defaults, timeline)}
    defaultProps={{ fps: 25, durationInFrames: frames, width: size.width, height: size.height, fit: size.fit, brand, assetBase: brandAssetFolder, beatProps: {} }}
  />
);

export const RemotionRoot = () => (
  <>
    {Insert<EnvelopeToSpamProps>(
      entry({ id: "EnvelopeToSpam3D", component: EnvelopeToSpam3D, defaults: envelopeToSpamDefaults, timeline: envelopeToSpamTimeline, size: takeover, frames: 34 }),
    )}
    {Insert<DomainBurnProps>(entry({ id: "DomainBurn3D", component: DomainBurn3D, defaults: domainBurnDefaults, timeline: domainBurnTimeline, size: card, frames: 45 }))}
    {Insert<AuthShieldProps>(entry({ id: "AuthShield3D", component: AuthShield3D, defaults: authShieldDefaults, timeline: authShieldTimeline, size: card, frames: 56 }))}
    {Insert<LogoExtrudeProps>(entry({ id: "LogoExtrude3D", component: LogoExtrude3D, defaults: logoExtrudeDefaults, timeline: logoExtrudeTimeline, size: takeover, frames: 24 }))}
    {Insert<BrandPatchProps>(entry({ id: "BrandPatch3D", component: BrandPatch3D, defaults: brandPatchDefaults, timeline: brandPatchTimeline, size: takeover, frames: 1 }))}
  </>
);
