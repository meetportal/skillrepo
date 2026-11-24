import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";
import { brandAlias } from "./brand-webpack.mjs";

const usage = `usage: node caption_boxes.mjs --props props.json --public-dir DIR --out qa/captions_bbox.json
Lays out the caption pages with the renderer's own code and fonts and writes one box per visible page
(output seconds, pixels) in the reel-qa captions_bbox.json format.`;

const { values } = parseArgs({
  options: {
    props: { type: "string" },
    "public-dir": { type: "string" },
    out: { type: "string" },
    help: { type: "boolean", short: "h" },
  },
});

if (values.help) {
  console.log(usage);
  process.exit(0);
}
if (!values.props || !values["public-dir"] || !values.out) {
  console.error(usage);
  process.exit(2);
}

const projectDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../remotion");
const require = createRequire(path.join(projectDir, "package.json"));
const { bundle } = require("@remotion/bundler");
const { selectComposition } = require("@remotion/renderer");

const inputProps = JSON.parse(fs.readFileSync(values.props, "utf8"));
const fps = inputProps.fps;
const serveUrl = await bundle({
  entryPoint: path.join(projectDir, "src/index.ts"),
  publicDir: path.resolve(values["public-dir"]),
  symlinkPublicDir: true,
  webpackOverride: brandAlias(projectDir),
});
const composition = await selectComposition({ serveUrl, id: "CaptionBoxes", inputProps });
fs.rmSync(serveUrl, { recursive: true, force: true });

const layouts = composition.props.captionBoxes;
if (!Array.isArray(layouts)) {
  console.error("CaptionBoxes returned no caption layout");
  process.exit(1);
}
const round = (value, digits) => Number(value.toFixed(digits));
const pages = layouts
  .filter((page) => page.visibleFrames.length > 0)
  .map((page) => ({
    text: page.text,
    start: round(page.visibleFrames[0] / fps, 3),
    end: round((page.visibleFrames[page.visibleFrames.length - 1] + 1) / fps, 3),
    bbox: page.bbox.map((value) => round(value, 1)),
    firstFrame: page.firstFrame,
    endFrame: page.endFrame,
    visibleFrameCount: page.visibleFrames.length,
    scale: round(page.scale, 4),
    centerY: page.centerY,
  }));
const hidden = layouts.length - pages.length;
fs.mkdirSync(path.dirname(path.resolve(values.out)), { recursive: true });
fs.writeFileSync(values.out, JSON.stringify({ fps, source: path.resolve(values.props), pages }, null, 1) + "\n");
console.log(`caption boxes: ${pages.length} pages (${hidden} fully hidden) -> ${values.out}`);
