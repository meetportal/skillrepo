import { useId } from "react";
import { AbsoluteFill, interpolate, interpolateColors } from "remotion";
import { z } from "zod";
import { iconSchema, timeSchema, toneSchema } from "../../lib/beatSchemas";
import { colors, fontFamilies, layout, motion, surface, type as typeTokens, zones } from "../../theme";
import type { BeatProps } from "../../types";
import { Icon, shakeOffset, stampScale, toneColor, type IconName } from "../ui";
import {
  arrive,
  clamp,
  easeInQuad,
  easeOutCubic,
  leave,
  panelSurface,
  quadPoint,
  ramp,
  relFrame,
  rgba,
  type Point,
} from "./mistake3/kit";

const boxSchema = z.object({ x0: z.number(), x1: z.number(), y0: z.number(), y1: z.number() });

export const schema = z.object({
  trays: z.tuple([z.string().min(1), z.string().min(1)]).default(["Inbox", "Spam"]),
  trayIcons: z.tuple([iconSchema, iconSchema]).default(["inbox", "warning"]),
  enterAt: timeSchema.default(0.24),
  deflectAt: timeSchema,
  landSec: z.number().min(0.2).max(1).default(0.44),
  padlockAt: timeSchema.optional(),
  padlockIcon: iconSchema.default("lock-open"),
  rejectTone: toneSchema.default("danger"),
  fromBox: boxSchema.optional(),
  coverFrames: z.number().int().min(1).max(8).default(3),
  bandTop: z.number().min(zones.safe.y0).max(900).default(280),
  bandBottom: z.number().min(700).max(zones.takeoverBand.y1).default(960),
  labelPx: z.number().min(typeTokens.cardMinPx).max(72).default(52),
  exit: z.boolean().default(true),
});

export type EnvelopeToSpamProps = z.infer<typeof schema>;

const trayGap = 80;
const trayHeight = 320;
const wellInset = 22;
const wellHeight = 188;
const baseW = 240;
const baseH = 168;
const envelopeW = 288;
const envelopeH = 202;
const landScale = 0.6;
const badgePx = 108;

const Backdrop = ({ clip, radius }: { clip: string; radius: number }) => (
  <AbsoluteFill
    style={{
      clipPath: clip,
      borderRadius: radius,
      background: `radial-gradient(70% 45% at 50% 38%, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0) 100%), ${surface.takeoverGradient}`,
    }}
  >
    <AbsoluteFill
      style={{
        backgroundImage: `radial-gradient(${rgba(colors.muted, 0.16)} 1.6px, transparent 1.8px)`,
        backgroundSize: "40px 40px",
        backgroundPosition: "20px 20px",
        WebkitMaskImage: "radial-gradient(60% 42% at 50% 40%, #000 0%, transparent 100%)",
        maskImage: "radial-gradient(60% 42% at 50% 40%, #000 0%, transparent 100%)",
      }}
    />
  </AbsoluteFill>
);

const Tray = ({
  left,
  top,
  width,
  label,
  icon,
  labelPx,
  accent,
  accentColor,
  glow,
  barrier,
  opacity,
  rise,
  tintLabel,
}: {
  left: number;
  top: number;
  width: number;
  label: string;
  icon: IconName;
  labelPx: number;
  accent: number;
  accentColor: string;
  glow: number;
  barrier: number;
  opacity: number;
  rise: number;
  tintLabel: boolean;
}) => {
  const ink = tintLabel ? interpolateColors(accent, [0, 1], [colors.muted, accentColor]) : colors.muted;
  const labelInk = tintLabel ? interpolateColors(accent, [0, 1], [colors.text, accentColor]) : colors.text;
  const border = interpolateColors(accent, [0, 1], [rgba(colors.muted, 0.24), rgba(accentColor, 0.85)]);
  return (
    <div style={{ position: "absolute", left, top: top + rise, width, height: trayHeight, opacity }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          boxSizing: "border-box",
          borderRadius: surface.cardRadius,
          border: `1px solid ${border}`,
          background: `radial-gradient(110% 60% at 50% 0%, ${rgba(accentColor, 0.16 * accent)} 0%, rgba(0,0,0,0) 70%), ${panelSurface.background}`,
          boxShadow: `${panelSurface.highlight}, ${panelSurface.shadow}${glow > 0 ? `, 0 0 ${Math.round(56 * glow)}px ${rgba(accentColor, 0.45 * glow)}` : ""}`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: wellInset,
          right: wellInset,
          top: wellInset,
          height: wellHeight,
          borderRadius: 22,
          background: `linear-gradient(180deg, ${rgba(colors.navyBottom, 0.9)} 0%, ${rgba(colors.navyPanel, 0.7)} 100%)`,
          border: `1px solid ${rgba(colors.muted, 0.14)}`,
          boxShadow: "inset 0 8px 20px rgba(0,0,0,0.55)",
        }}
      />
      {barrier > 0 ? (
        <div
          style={{
            position: "absolute",
            left: wellInset - 6,
            right: wellInset - 6,
            top: wellInset - 3,
            height: 6,
            borderRadius: 6,
            background: accentColor,
            opacity: barrier,
            boxShadow: `0 0 24px ${rgba(accentColor, 0.9)}, 0 0 60px ${rgba(accentColor, 0.5)}`,
          }}
        />
      ) : null}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: wellInset + wellHeight,
          bottom: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 18,
        }}
      >
        <Icon name={icon} size={Math.round(labelPx * 1.02)} color={ink} strokeWidth={2} />
        <div style={{ fontFamily: fontFamilies.sans, fontWeight: 700, fontSize: labelPx, lineHeight: 1, color: labelInk, transform: `translateY(${Math.round(labelPx * 0.06)}px)` }}>
          {label}
        </div>
      </div>
    </div>
  );
};

const Envelope = ({ tint }: { tint: number }) => {
  const id = useId().replace(/:/g, "");
  const edge = interpolateColors(tint, [0, 1], ["#C9D1DF", "#F2B7C0"]);
  return (
    <svg width={envelopeW} height={envelopeH} viewBox={`0 0 ${baseW} ${baseH}`} style={{ display: "block", overflow: "visible" }}>
      <defs>
        <linearGradient id={`paper-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#FFFFFF" />
          <stop offset="100%" stopColor="#DCE3EE" />
        </linearGradient>
        <linearGradient id={`flap-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#EEF2F8" />
          <stop offset="100%" stopColor="#D2DAE7" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width={baseW - 4} height={baseH - 4} rx="20" fill={`url(#paper-${id})`} stroke={edge} strokeWidth="2" />
      <path d={`M14 ${baseH - 14} L${baseW / 2 - 26} 92 M${baseW - 14} ${baseH - 14} L${baseW / 2 + 26} 92`} stroke="#B5C0D2" strokeWidth="3" strokeLinecap="round" fill="none" />
      <path d={`M8 16 L${baseW / 2} 100 L${baseW - 8} 16 Z`} fill={`url(#flap-${id})`} />
      <path d={`M12 18 L${baseW / 2} 100 L${baseW - 12} 18`} stroke="#8F9BB2" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  );
};

const PadlockBadge = ({ frame, start, color, icon }: { frame: number; start: number; color: string; icon: IconName }) => {
  const opacity = interpolate(frame, [start, start + 2], [0, 1], clamp);
  const ring = interpolate(frame, [start + 2, start + 14], [0, 1], clamp);
  return (
    <div style={{ position: "relative", width: badgePx, height: badgePx }}>
      {ring > 0 && ring < 1 ? (
        <div
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: "50%",
            border: `3px solid ${color}`,
            opacity: interpolate(ring, [0, 1], [0.7, 0], clamp),
            transform: `scale(${interpolate(ring, [0, 1], [1, 1.7], { ...clamp, easing: easeOutCubic })})`,
          }}
        />
      ) : null}
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          opacity,
          transform: `scale(${stampScale(frame, start)})`,
          background: `linear-gradient(180deg, ${color} 0%, ${rgba(color, 0.78)} 100%)`,
          border: `3px solid ${colors.navyBottom}`,
          boxShadow: `0 10px 26px rgba(0,0,0,0.5), 0 0 30px ${rgba(color, 0.55)}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Icon name={icon} size={Math.round(badgePx * 0.54)} color={colors.text} strokeWidth={2.4} />
      </div>
    </div>
  );
};

const EnvelopeToSpam = ({ props, frame, durationInFrames, fps, beat, toFrame }: BeatProps<EnvelopeToSpamProps>) => {
  const context = { beat, toFrame };
  const reject = toneColor(props.rejectTone);
  const bandLeft = zones.safe.x0;
  const bandRight = zones.safe.x1;
  const trayWidth = Math.floor((bandRight - bandLeft - trayGap) / 2);
  const trayTop = props.bandBottom - trayHeight;
  const inboxLeft = bandLeft;
  const spamLeft = bandRight - trayWidth;
  const centreX = Math.round((bandLeft + bandRight) / 2);

  const cover = ramp(frame, 0, props.coverFrames);
  const box = props.fromBox;
  const clip = box
    ? `inset(${box.y0 * (1 - cover)}px ${(layout.width - box.x1) * (1 - cover)}px ${(layout.height - box.y1) * (1 - cover)}px ${box.x0 * (1 - cover)}px round ${surface.cardRadius * (1 - cover)}px)`
    : "none";
  const backdropOpacity = box ? 1 : interpolate(frame, [0, props.coverFrames], [0, 1], clamp);

  const enter = relFrame(context, props.enterAt);
  const deflect = relFrame(context, props.deflectAt);
  const land = deflect + Math.max(4, Math.round(props.landSec * fps));
  const padlock = props.padlockAt === undefined ? undefined : relFrame(context, props.padlockAt);

  const start: Point = { x: centreX, y: props.bandTop + envelopeH / 2 };
  const hit: Point = { x: inboxLeft + trayWidth / 2, y: trayTop - envelopeH / 2 - 8 };
  const approachControl: Point = { x: start.x - 150, y: start.y + 20 };
  const target: Point = { x: spamLeft + trayWidth / 2, y: trayTop + wellInset + wellHeight / 2 };
  const bounceControl: Point = { x: centreX, y: hit.y - 300 };

  const entrance = arrive(frame, enter);
  const approachStart = enter + 4;
  const approach = interpolate(frame, [approachStart, deflect], [0, 1], { ...clamp, easing: easeInQuad });
  const bounce = ramp(frame, deflect, land - deflect, easeOutCubic);
  const flying = frame >= deflect;
  const position = flying ? quadPoint(hit, bounceControl, target, bounce) : quadPoint(start, approachControl, hit, approach);
  const rotate = flying ? interpolate(bounce, [0, 0.45, 1], [-7, 14, 0], clamp) : -7 * approach;
  const scale = (flying ? interpolate(bounce, [0, 1], [1, landScale], clamp) : 1) * entrance.scale;
  const routeDraw = ramp(frame, enter + 2, 10);
  const routeFade = interpolate(frame, [deflect, deflect + 4], [1, 0], clamp);
  const barrier = interpolate(frame, [deflect - 1, deflect, deflect + 10], [0, 1, 0], clamp);
  const inboxShake = shakeOffset(frame, deflect, 2, 6);
  const spamAccent = ramp(frame, land - 1, 4);
  const spamGlow = interpolate(frame, [land - 1, land + 1, land + 14], [0, 1, 0.3], clamp);
  const landShake = shakeOffset(frame, land, 2, 4);
  const tint = padlock === undefined ? 0 : ramp(frame, padlock, 4);
  const exit = leave(frame, durationInFrames, props.exit, 0);
  const trayIn = (index: number) => arrive(frame, Math.max(props.coverFrames, enter - 4) + index * motion.staggerFrames);

  const routePath = `M${start.x} ${start.y} Q${approachControl.x} ${approachControl.y} ${hit.x} ${hit.y}`;
  const radians = (rotate * Math.PI) / 180;
  const badgeOffset = { x: envelopeW * 0.4 * scale, y: -envelopeH * 0.42 * scale };
  const badgeCentre = {
    x: position.x + badgeOffset.x * Math.cos(radians) - badgeOffset.y * Math.sin(radians),
    y: position.y + badgeOffset.x * Math.sin(radians) + badgeOffset.y * Math.cos(radians),
  };
  const envelopeX = Math.round(position.x - envelopeW / 2 + (flying ? landShake.x : 0));
  const envelopeY = Math.round(position.y - envelopeH / 2 + (flying ? landShake.y : 0)) + Math.round(entrance.rise * 0.5);

  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity: exit.opacity }}>
      <AbsoluteFill style={{ opacity: backdropOpacity }}>
        <Backdrop clip={clip} radius={0} />
      </AbsoluteFill>
      <svg width={layout.width} height={layout.height} style={{ position: "absolute", inset: 0, opacity: routeFade * entrance.opacity }}>
        <path
          d={routePath}
          fill="none"
          stroke={rgba(colors.text, 0.5)}
          strokeWidth={6}
          strokeLinecap="round"
          strokeDasharray="1 22"
          opacity={routeDraw}
        />
      </svg>
      {[0, 1].map((index) => {
        const motionIn = trayIn(index);
        const isSpam = index === 1;
        const shake = isSpam ? { x: 0, y: 0 } : inboxShake;
        return (
          <Tray
            key={index}
            left={(isSpam ? spamLeft : inboxLeft) + shake.x}
            top={trayTop + shake.y}
            width={trayWidth}
            label={isSpam ? props.trays[1] : props.trays[0]}
            icon={isSpam ? props.trayIcons[1] : props.trayIcons[0]}
            labelPx={props.labelPx}
            accent={isSpam ? spamAccent : barrier * 0.9}
            accentColor={reject}
            glow={isSpam ? spamGlow : 0}
            barrier={isSpam ? 0 : barrier}
            opacity={motionIn.opacity}
            rise={motionIn.rise}
            tintLabel={isSpam}
          />
        );
      })}
      {frame >= enter ? (
        <div
          style={{
            position: "absolute",
            left: envelopeX,
            top: envelopeY,
            width: envelopeW,
            height: envelopeH,
            opacity: entrance.opacity,
            transform: `rotate(${rotate}deg) scale(${scale})`,
            filter: `drop-shadow(0 ${Math.round(22 * scale)}px ${Math.round(34 * scale)}px rgba(0,0,0,0.5))`,
          }}
        >
          <Envelope tint={tint} />
        </div>
      ) : null}
      {padlock !== undefined && frame >= padlock ? (
        <div style={{ position: "absolute", left: Math.round(badgeCentre.x - badgePx / 2), top: Math.round(badgeCentre.y - badgePx / 2) }}>
          <PadlockBadge frame={frame} start={padlock} color={reject} icon={props.padlockIcon} />
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

export default EnvelopeToSpam;
