import { Config } from "@remotion/cli/config";

Config.setEntryPoint("src/index.ts");
Config.setChromiumOpenGlRenderer("swangle");
Config.setMuted(true);
Config.setColorSpace("bt709");
Config.setOverwriteOutput(true);
