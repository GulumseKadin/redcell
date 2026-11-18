import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
  spring,
  random,
} from "remotion";
import { theme } from "./theme";

export const MONO =
  "'JetBrains Mono','Fira Code','SF Mono',ui-monospace,monospace";

/* ---- backdrop: grid + vignette ---- */
export const Backdrop: React.FC<{ tint?: string }> = ({ tint }) => (
  <AbsoluteFill style={{ backgroundColor: theme.bg }}>
    <AbsoluteFill
      style={{
        backgroundImage: `linear-gradient(${theme.grid} 1px, transparent 1px),
          linear-gradient(90deg, ${theme.grid} 1px, transparent 1px)`,
        backgroundSize: "48px 48px",
        opacity: 0.5,
        maskImage:
          "radial-gradient(ellipse 80% 70% at 50% 45%, #000 40%, transparent 100%)",
      }}
    />
    {tint ? (
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse 60% 50% at 50% 50%, ${tint}22, transparent 70%)`,
        }}
      />
    ) : null}
    <AbsoluteFill
      style={{
        boxShadow: "inset 0 0 300px rgba(0,0,0,0.9)",
      }}
    />
  </AbsoluteFill>
);

/* ---- Scene wrapper: guarantees content paints ABOVE the backdrop ----
   Backdrop is position:absolute, so plain static children would paint *under*
   it (CSS paint order: positioned descendants over non-positioned ones). The
   middle AbsoluteFill is itself positioned and comes after Backdrop in DOM, so
   everything inside it reliably sits above the backdrop; overlays go last. */
export const Scene: React.FC<{
  children: React.ReactNode;
  tint?: string;
  sweep?: boolean;
}> = ({ children, tint, sweep }) => (
  <AbsoluteFill>
    <Backdrop tint={tint} />
    <AbsoluteFill
      style={{ justifyContent: "center", alignItems: "center" }}
    >
      {children}
    </AbsoluteFill>
    {sweep ? <SweepBar /> : null}
    <Scanlines />
  </AbsoluteFill>
);

/* ---- CRT scanlines + subtle flicker ---- */
export const Scanlines: React.FC = () => {
  const frame = useCurrentFrame();
  const flick = 0.06 + 0.02 * Math.sin(frame * 0.7);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", mixBlendMode: "overlay" }}>
      <AbsoluteFill
        style={{
          backgroundImage:
            "repeating-linear-gradient(0deg, rgba(255,255,255,0.08) 0px, rgba(255,255,255,0.08) 1px, transparent 1px, transparent 3px)",
          opacity: flick,
        }}
      />
    </AbsoluteFill>
  );
};

/* ---- moving scan sweep bar ---- */
export const SweepBar: React.FC<{ color?: string }> = ({
  color = theme.red,
}) => {
  const frame = useCurrentFrame();
  const { height } = useVideoConfig();
  const y = interpolate(frame % 120, [0, 120], [-0.1, 1.1]) * height;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          top: y,
          left: 0,
          right: 0,
          height: 140,
          background: `linear-gradient(${color}00, ${color}22, ${color}00)`,
        }}
      />
    </AbsoluteFill>
  );
};

/* ---- glitch text: red/green chromatic split that pulses ---- */
export const GlitchText: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
  intensity?: number;
}> = ({ children, style, intensity = 1 }) => {
  const frame = useCurrentFrame();
  const jitter = (random(`g${Math.floor(frame / 3)}`) - 0.5) * 6 * intensity;
  const active = random(`a${Math.floor(frame / 5)}`) > 0.78;
  const dx = active ? jitter : 0;
  return (
    <div style={{ position: "relative", ...style }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          color: theme.green,
          transform: `translate(${-dx}px,0)`,
          opacity: active ? 0.6 : 0,
          mixBlendMode: "screen",
        }}
      >
        {children}
      </div>
      <div
        style={{
          position: "absolute",
          inset: 0,
          color: theme.red,
          transform: `translate(${dx}px,0)`,
          opacity: active ? 0.6 : 0,
          mixBlendMode: "screen",
        }}
      >
        {children}
      </div>
      <div style={{ position: "relative" }}>{children}</div>
    </div>
  );
};

export const Cursor: React.FC<{ color?: string }> = ({
  color = theme.red,
}) => {
  const frame = useCurrentFrame();
  const on = Math.floor(frame / 15) % 2 === 0;
  return (
    <span
      style={{
        display: "inline-block",
        width: "0.6em",
        height: "1.05em",
        background: on ? color : "transparent",
        marginLeft: 4,
        transform: "translateY(3px)",
      }}
    />
  );
};

/* ---- the red scanner eye (KITT/Cylon) ---- */
export const ScannerEye: React.FC<{ cells?: number; width?: number }> = ({
  cells = 21,
  width = 520,
}) => {
  const frame = useCurrentFrame();
  const t = (frame % 60) / 60;
  const tri = t < 0.5 ? t * 2 : (1 - t) * 2; // 0..1..0
  const pos = tri * (cells - 1);
  return (
    <div style={{ display: "flex", gap: 6, width }}>
      {new Array(cells).fill(0).map((_, i) => {
        const d = Math.abs(i - pos);
        const lit = Math.max(0, 1 - d / 3);
        return (
          <div
            key={i}
            style={{
              flex: 1,
              height: 14,
              borderRadius: 2,
              background:
                lit > 0.05
                  ? `rgba(255,${Math.round(60 - lit * 40)},${Math.round(
                      60 - lit * 40
                    )},${0.15 + lit})`
                  : "#1c1f24",
              boxShadow: lit > 0.6 ? `0 0 18px ${theme.red}` : "none",
            }}
          />
        );
      })}
    </div>
  );
};

/* ---- stage pills: RECON / EXPLOIT / VERIFY / REPORT ---- */
export const StagePills: React.FC<{ stages: readonly string[]; active: number }> = ({
  stages,
  active,
}) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();
  return (
    <div style={{ display: "flex", gap: 18 }}>
      {stages.map((s, i) => {
        const on = i <= active;
        const justOn = i === active;
        const pop = justOn
          ? spring({ frame: frame - 0, fps, config: { damping: 9 } })
          : 1;
        return (
          <div
            key={s}
            style={{
              fontFamily: MONO,
              fontSize: 30,
              fontWeight: 700,
              letterSpacing: 2,
              padding: "14px 26px",
              borderRadius: 6,
              color: on ? theme.bg : theme.textFaint,
              background: on ? theme.red : "transparent",
              border: `2px solid ${on ? theme.red : "#242a30"}`,
              boxShadow: justOn ? `0 0 30px ${theme.red}` : "none",
              transform: `scale(${justOn ? 0.9 + pop * 0.1 : 1})`,
            }}
          >
            {s}
          </div>
        );
      })}
    </div>
  );
};

/* ---- radial CVSS gauge counting up to a score ---- */
export const CVSSGauge: React.FC<{
  target: number;
  severity: string;
  color: string;
  progress: number; // 0..1 animation drive
}> = ({ target, severity, color, progress }) => {
  const val = target * progress;
  const R = 150;
  const C = Math.PI * R; // semicircle length
  const frac = val / 10;
  return (
    <div style={{ position: "relative", width: 420, height: 260 }}>
      <svg width={420} height={260} viewBox="0 0 420 260">
        <path
          d={`M 40 230 A ${R} ${R} 0 0 1 380 230`}
          fill="none"
          stroke="#1c2026"
          strokeWidth={22}
          strokeLinecap="round"
        />
        <path
          d={`M 40 230 A ${R} ${R} 0 0 1 380 230`}
          fill="none"
          stroke={color}
          strokeWidth={22}
          strokeLinecap="round"
          strokeDasharray={C}
          strokeDashoffset={C * (1 - frac)}
          style={{ filter: `drop-shadow(0 0 16px ${color})` }}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          top: 70,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <div
          style={{
            fontFamily: MONO,
            fontSize: 92,
            fontWeight: 800,
            color,
            lineHeight: 1,
            textShadow: `0 0 30px ${color}88`,
          }}
        >
          {val.toFixed(1)}
        </div>
        <div
          style={{
            fontFamily: MONO,
            fontSize: 26,
            letterSpacing: 6,
            color,
            marginTop: 8,
            opacity: progress > 0.85 ? 1 : 0,
          }}
        >
          {severity}
        </div>
      </div>
    </div>
  );
};

/* ---- terminal window chrome ---- */
export const TerminalWindow: React.FC<{
  children: React.ReactNode;
  title?: string;
  style?: React.CSSProperties;
}> = ({ children, title = "redcell — run", style }) => (
  <div
    style={{
      background: theme.bgPanel,
      border: `1px solid #22272d`,
      borderRadius: 10,
      boxShadow: "0 40px 120px rgba(0,0,0,0.6)",
      overflow: "hidden",
      ...style,
    }}
  >
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "14px 20px",
        borderBottom: "1px solid #1c2026",
        background: "#0a0c0f",
      }}
    >
      <Dot c="#ff5f56" />
      <Dot c="#ffbd2e" />
      <Dot c="#27c93f" />
      <div
        style={{
          marginLeft: 14,
          fontFamily: MONO,
          fontSize: 20,
          color: theme.textDim,
        }}
      >
        {title}
      </div>
    </div>
    <div style={{ padding: "26px 30px" }}>{children}</div>
  </div>
);

const Dot: React.FC<{ c: string }> = ({ c }) => (
  <div style={{ width: 14, height: 14, borderRadius: 7, background: c }} />
);
