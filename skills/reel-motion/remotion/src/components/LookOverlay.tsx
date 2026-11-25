import { useMemo } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { look as lookTokens } from "../theme";
import { lookSchema } from "../types";

export const LookOverlay = ({ look }: { look: unknown }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const settings = useMemo(() => lookSchema.parse(look ?? {}), [look]);
  if (settings.vignette <= 0 && settings.grain <= 0) {
    return null;
  }
  const noiseWidth = Math.ceil(width / settings.grainSizePx);
  const noiseHeight = Math.ceil(height / settings.grainSizePx);
  const filterId = `look-grain-${frame}`;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {settings.vignette > 0 ? (
        <AbsoluteFill
          style={{
            background: `radial-gradient(ellipse ${lookTokens.vignetteEllipse} at 50% ${lookTokens.vignetteCenterY}, rgba(0,0,0,0) ${lookTokens.vignetteInner}%, rgba(${lookTokens.vignetteColor},${(lookTokens.vignetteMax * settings.vignette * 0.45).toFixed(3)}) ${lookTokens.vignetteMid}%, rgba(${lookTokens.vignetteColor},${(lookTokens.vignetteMax * settings.vignette).toFixed(3)}) 100%)`,
          }}
        />
      ) : null}
      {settings.grain > 0 ? (
        <AbsoluteFill style={{ mixBlendMode: "overlay", opacity: lookTokens.grainMaxOpacity * settings.grain }}>
          <svg
            width={noiseWidth}
            height={noiseHeight}
            viewBox={`0 0 ${noiseWidth} ${noiseHeight}`}
            style={{ position: "absolute", left: 0, top: 0, width, height }}
          >
            <filter id={filterId} x="0" y="0" width="100%" height="100%" colorInterpolationFilters="sRGB">
              <feTurbulence type="fractalNoise" baseFrequency={lookTokens.grainFrequency} numOctaves={2} seed={settings.seed + frame} stitchTiles="stitch" />
              <feColorMatrix type="saturate" values="0" />
              <feComponentTransfer>
                <feFuncR type="linear" slope={lookTokens.grainContrast} intercept={0.5 - lookTokens.grainContrast / 2} />
                <feFuncG type="linear" slope={lookTokens.grainContrast} intercept={0.5 - lookTokens.grainContrast / 2} />
                <feFuncB type="linear" slope={lookTokens.grainContrast} intercept={0.5 - lookTokens.grainContrast / 2} />
                <feFuncA type="linear" slope={0} intercept={1} />
              </feComponentTransfer>
            </filter>
            <rect width={noiseWidth} height={noiseHeight} filter={`url(#${filterId})`} />
          </svg>
        </AbsoluteFill>
      ) : null}
    </AbsoluteFill>
  );
};
