import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";
import { brandAlias } from "./brand-webpack.mjs";

const usage = `usage: node stills.mjs --props props.json --public-dir DIR --out DIR (--times 0.0,1.2 | --frames 0,30) [--image-format png|jpeg] [--composition Reel]
Bundles once and renders every requested still (times in seconds or frame numbers).`;

const { values } = parseArgs({
  options: {
    props: { type: "string" },
    "public-dir": { type: "string" },
    out: { type: "string" },
    times: { type: "string" },
    frames: { type: "string" },
    "image-format": { type: "string", default: "png" },
    composition: { type: "string", default: "Reel" },
    help: { type: "boolean", short: "h" },
  },
});

if (values.help) {
  console.log(usage);
  process.exit(0);
}
if (!values.props || !values["public-dir"] || !values.out || (!values.times && !values.frames)) {
  console.error(usage);
  process.exit(2);
}

const projectDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../remotion");
const require = createRequire(path.join(projectDir, "package.json"));
const { bundle } = require("@remotion/bundler");
const { renderStill, selectComposition } = require("@remotion/renderer");

const inputProps = JSON.parse(fs.readFileSync(values.props, "utf8"));
const fps = inputProps.fps;
const requests = values.frames
  ? values.frames.split(",").map((frame) => ({ label: `f${frame}`, frame: Number(frame) }))
  : values.times.split(",").map((time) => ({ label: `${time}s`, frame: Math.round(Number(time) * fps) }));

const serveUrl = await bundle({
  entryPoint: path.join(projectDir, "src/index.ts"),
  publicDir: path.resolve(values["public-dir"]),
  symlinkPublicDir: true,
  webpackOverride: brandAlias(projectDir),
});
const composition = await selectComposition({ serveUrl, id: values.composition, inputProps });
fs.mkdirSync(values.out, { recursive: true });
for (const request of requests) {
  const output = path.join(values.out, `still_${request.label}.${values["image-format"]}`);
  await renderStill({ serveUrl, composition, inputProps, frame: request.frame, output, imageFormat: values["image-format"], overwrite: true });
  console.log(`still ${request.label} (frame ${request.frame}) -> ${output}`);
}
fs.rmSync(serveUrl, { recursive: true, force: true });
