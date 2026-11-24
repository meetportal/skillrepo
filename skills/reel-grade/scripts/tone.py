import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

TOE = (0.03, 0.25)
HIGH_BAND = (0.40, 0.70)
WHITE_GUARD = (0.90, 1.00)
BLACK_BAND = (0.0, 0.30)


def smooth(low, high, value):
    ramp = f"clip(({value}-{low})/{high - low},0,1)"
    return f"(pow({ramp},2)*(3-2*{ramp}))"


def tone_expression(mid=1.0, high=0.0, black=0.0, full_range=True):
    origin, span = (0.0, 255.0) if full_range else (16.0, 219.0)
    x = f"((val-{origin})/{span})"
    curve = x
    if abs(mid - 1.0) > 1e-6:
        curve = f"({x}+(pow(max({x},0),{1 / mid:.6f})-{x})*{smooth(*TOE, x)})"
    if abs(high) > 1e-6:
        curve = f"({curve}+{high / 219:.6f}*{smooth(*HIGH_BAND, curve)}*(1-{smooth(*WHITE_GUARD, curve)}))"
    if abs(black) > 1e-6:
        curve = f"({curve}+{black / 219:.6f}*(1-{smooth(*BLACK_BAND, curve)}))"
    return f"clip({origin}+{span}*{curve},0,255)"


def tone_curve(values, mid=1.0, high=0.0, black=0.0):
    import numpy as np

    def smooth_np(low, top, value):
        ramp = np.clip((value - low) / (top - low), 0, 1)
        return ramp * ramp * (3 - 2 * ramp)

    x = np.asarray(values, dtype=np.float64)
    curve = x + (np.power(np.maximum(x, 0), 1 / mid) - x) * smooth_np(*TOE, x)
    curve = curve + high / 219 * smooth_np(*HIGH_BAND, curve) * (1 - smooth_np(*WHITE_GUARD, curve))
    curve = curve + black / 219 * (1 - smooth_np(*BLACK_BAND, curve))
    return curve


def main():
    parser = argparse.ArgumentParser(description="Print the shadow-neutral tone curve (mid lift with a pinned toe, highlight pull, black offset) as a lutyuv expression and as a table.")
    parser.add_argument("--mid", type=float, default=1.0, help="mid-tone exponent like eq gamma (above 1 brightens), faded out below the toe so blacks stay put")
    parser.add_argument("--high", type=float, default=0.0, help="tv-range code values added to the upper mids and highlights (negative pulls hot skin down); pure white is untouched")
    parser.add_argument("--black", type=float, default=0.0, help="tv-range code values added at black, fading out by 30 percent grey")
    parser.add_argument("--tv", action="store_true", help="source is limited range")
    args = parser.parse_args()
    print(tone_expression(args.mid, args.high, args.black, full_range=not args.tv))
    for code in (16, 20, 30, 50, 80, 110, 140, 150, 160, 180, 200, 220, 235):
        normal = (code - 16) / 219
        mapped = float(tone_curve([normal], args.mid, args.high, args.black)[0]) * 219 + 16
        print(f"  tv {code:3d} -> {mapped:6.1f}")


if __name__ == "__main__":
    main()
