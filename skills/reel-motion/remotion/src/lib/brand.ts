import { staticFile } from "remotion";
import brandJson from "../../../../mailinfra-brand/brand.json";

export const brand = brandJson;

export type Brand = typeof brandJson;

export const brandPublicFolder = ".reel-motion-brand";

export const brandAsset = (assetPath: string) =>
  staticFile(`${brandPublicFolder}/${assetPath.replace(/^assets\//, "").replace(/^brand\//, "")}`);

export const brandLogo = (name: keyof Brand["logos"]) => brandAsset(brand.logos[name]);
