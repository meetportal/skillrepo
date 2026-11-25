import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

GEOMETRY_TAGS = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}


def icon_elements(icon_path):
    root = ET.parse(icon_path).getroot()
    view_box = [float(v) for v in root.get("viewBox", "0 0 24 24").split()]
    parts = []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag not in GEOMETRY_TAGS:
            continue
        attrs = " ".join(f'{k}="{v}"' for k, v in element.attrib.items())
        parts.append(f"<{tag} {attrs}/>")
    return "".join(parts), view_box[2]


def instance(font_path, wght, opsz):
    font = TTFont(font_path)
    if "fvar" not in font:
        return font
    axes = {a.axisTag for a in font["fvar"].axes}
    location = {k: v for k, v in {"wght": wght, "opsz": opsz}.items() if k in axes}
    return instantiateVariableFont(font, location)


def outline_word(font, word, font_px, tracking_em):
    upm = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    glyphs = font.getGlyphSet()
    hmtx = font["hmtx"]
    scale = font_px / upm
    pen = SVGPathPen(glyphs)
    bounds = BoundsPen(glyphs)
    x = 0.0
    for i, ch in enumerate(word):
        name = cmap[ord(ch)]
        transform = (scale, 0, 0, -scale, x, 0)
        glyphs[name].draw(TransformPen(pen, transform))
        glyphs[name].draw(TransformPen(bounds, transform))
        x += hmtx[name][0] * scale
        if i < len(word) - 1:
            x += tracking_em * font_px
    cap = font["OS/2"].sCapHeight * scale
    return pen.getCommands(), bounds.bounds, cap


def lockup(icon, icon_units, d, width, height, text_x, baseline, icon_px, icon_color, text_color):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.2f} {height:.2f}" '
            f'width="{width:.2f}" height="{height:.2f}">'
            f'<g transform="scale({icon_px / icon_units})" fill="none" stroke="{icon_color}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">{icon}</g>'
            f'<g transform="translate({text_x:.3f} {baseline:.3f})" fill="{text_color}"><path d="{d}"/></g></svg>')


def main():
    parser = argparse.ArgumentParser(description="Rebuild a website header logo (outline icon plus wordmark) as outlined SVGs.")
    parser.add_argument("--font", required=True)
    parser.add_argument("--icon", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--word", default="Mailinfra")
    parser.add_argument("--prefix", default="mailinfra")
    parser.add_argument("--wght", type=float, default=700)
    parser.add_argument("--opsz", type=float, default=14)
    parser.add_argument("--font-px", type=float, default=24.0)
    parser.add_argument("--icon-px", type=float, default=32.0)
    parser.add_argument("--gap-px", type=float, default=12.0)
    parser.add_argument("--tracking-em", type=float, default=-0.025)
    parser.add_argument("--pad-px", type=float, default=2.0)
    parser.add_argument("--light-icon", default="#0000FF")
    parser.add_argument("--light-text", default="#1A1A1A")
    parser.add_argument("--dark", default="#FFFFFF")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    icon, icon_units = icon_elements(args.icon)
    font = instance(args.font, args.wght, args.opsz)
    d, (_, _, x1, _), cap = outline_word(font, args.word, args.font_px, args.tracking_em)
    height = args.icon_px
    text_x = args.icon_px + args.gap_px
    baseline = height / 2 + cap / 2
    width = text_x + x1 + args.pad_px
    shared = (icon, icon_units, d, width, height, text_x, baseline, args.icon_px)

    (out / f"{args.prefix}-logo-white.svg").write_text(lockup(*shared, args.dark, args.dark))
    (out / f"{args.prefix}-logo-color.svg").write_text(lockup(*shared, args.light_icon, args.light_text))
    (out / f"{args.prefix}-icon-white.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {icon_units:g} {icon_units:g}" '
        f'width="{icon_units:g}" height="{icon_units:g}" fill="none" stroke="{args.dark}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">{icon}</svg>')
    print(f"width {width:.2f} height {height:.2f} cap {cap:.2f} icon_split {(args.icon_px + args.gap_px / 2) / width:.3f}")


if __name__ == "__main__":
    main()
