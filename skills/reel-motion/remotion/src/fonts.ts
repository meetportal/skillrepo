import { loadFont } from "@remotion/fonts";
import { cancelRender, continueRender, delayRender } from "remotion";
import { brand, brandAsset } from "./lib/brand";

type FontSpec = { family: string; weight: string; style: "normal" | "italic"; assetPath: string };

const fontSpecs: FontSpec[] = [
  ...Object.entries(brand.fonts.sans.files).map(([weight, assetPath]) => ({
    family: brand.fonts.sans.family,
    weight,
    style: "normal" as const,
    assetPath,
  })),
  ...Object.entries(brand.fonts.accent.files).map(([weight, assetPath]) => ({
    family: brand.fonts.accent.family,
    weight,
    style: "italic" as const,
    assetPath,
  })),
];

const assertFontsLoaded = () => {
  const loadedFaces = new Set<string>();
  document.fonts.forEach((face) => {
    if (face.status === "loaded") {
      loadedFaces.add(`${face.family.replace(/"/g, "")}|${face.weight}|${face.style}`);
    }
  });
  const missing = fontSpecs.filter((spec) => !loadedFaces.has(`${spec.family}|${spec.weight}|${spec.style}`));
  if (missing.length > 0) {
    throw new Error(`Fonts failed to load: ${missing.map((spec) => `${spec.family} ${spec.weight} ${spec.style}`).join(", ")}`);
  }
};

const fontsHandle = delayRender("Loading brand fonts");

export const fontsReady = Promise.all(
  fontSpecs.map((spec) =>
    loadFont({ family: spec.family, url: brandAsset(spec.assetPath), weight: spec.weight, style: spec.style }),
  ),
).then(assertFontsLoaded);

fontsReady.then(() => continueRender(fontsHandle)).catch((error: unknown) => cancelRender(error));
