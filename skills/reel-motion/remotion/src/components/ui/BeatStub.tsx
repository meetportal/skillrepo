import { AbsoluteFill } from "remotion";
import { colors, fontFamilies, surface } from "../../theme";
import type { BeatContext } from "../../types";
import { Card } from "./Card";
import { Kicker } from "./Kicker";
import { enterExitStyle } from "./motion";
import { boxStyle, zones, type Box } from "./SafeArea";

export type StubPlacement = "card" | "headline" | "rail" | "takeover" | "endcard";

const placementBox = (placement: StubPlacement): Box => {
  switch (placement) {
    case "card":
      return zones.card;
    case "headline":
      return zones.headline;
    case "rail":
      return zones.rail;
    case "takeover":
    case "endcard":
      return zones.takeoverBand;
  }
};

export const BeatStub = ({
  context,
  name,
  placement,
  summary,
}: {
  context: BeatContext;
  name: string;
  placement: StubPlacement;
  summary: string;
}) => {
  const style = enterExitStyle(context.frame, context.durationInFrames, { from: placement === "rail" ? "down" : "scale" });
  const box = placementBox(placement);
  const background =
    placement === "takeover" ? surface.takeoverGradient : placement === "endcard" ? colors.cream : undefined;
  const compact = placement === "rail";
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {background ? <AbsoluteFill style={{ background, opacity: style.opacity }} /> : null}
      <div style={{ ...boxStyle(box), opacity: style.opacity, transform: style.transform }}>
        <Card
          padding={compact ? 6 : surface.cardPadding}
          radius={compact ? 12 : surface.cardRadius}
          style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "center", gap: 10 }}
        >
          <Kicker style={{ fontSize: compact ? 18 : 36, letterSpacing: compact ? "0.08em" : undefined }}>
            {compact ? name : `${context.beat.id} stub`}
          </Kicker>
          {compact ? null : (
            <>
              <div style={{ fontFamily: fontFamilies.sans, fontWeight: 800, fontSize: 64, lineHeight: 1.05 }}>{name}</div>
              <div style={{ fontFamily: fontFamilies.sans, fontWeight: 500, fontSize: 30, color: colors.muted, lineHeight: 1.2 }}>
                {summary}
              </div>
            </>
          )}
        </Card>
      </div>
    </AbsoluteFill>
  );
};
