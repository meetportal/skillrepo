import { Config } from "@remotion/cli/config";
import { brandAlias } from "../scripts/brand-webpack.mjs";

Config.setEntryPoint("src/index.ts");
Config.setVideoImageFormat("jpeg");
Config.setJpegQuality(95);
Config.setOverwriteOutput(true);
Config.setColorSpace("bt709");
Config.setMuted(true);
Config.overrideWebpackConfig(brandAlias(process.cwd()));
