import React from "react";
import {
  AbsoluteFill,
  Series,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/JetBrainsMono";
import { theme } from "./theme";
import {
  Scene,
  GlitchText,
  Cursor,
  ScannerEye,
  StagePills,
  CVSSGauge,
  TerminalWindow,
  MONO,
} from "./ui";
import { SCOPE, STAGES, LOG_LINES, FINDING, STATS, FEATURES } from "./data";

loadFont("normal", {
  weights: ["400", "700", "800"],
  subsets: ["latin"],
  ignoreTooManyRequestsWarning: true,
});

/* hard "tak" pop-in */
const pop = (frame: number, fps: number, delay = 0) =>
  spring({ frame: frame - delay, fps, config: { damping: 11, mass: 0.6 } });

const Eyebrow: React.FC<{ children: React.ReactNode; show: number }> = ({
  children,
  show,
}) => (
  <div
    style={{
      fontFamily: MONO,
      fontSize: 30,
      letterSpacing: 4,
      color: theme.textDim,
      marginBottom: 26,
      opacity: show,
    }}
  >
    {children}
  </div>
);

/* ============================ SCENE 1 — BOOT ============================ */
const SceneBoot: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const logoIn = pop(frame, fps, 20);
  const subIn = interpolate(frame, [38, 55], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const eyeIn = interpolate(frame, [0, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <Scene tint={theme.red}>
      <div style={{ opacity: eyeIn, marginBottom: 46 }}>
        <ScannerEye />
      </div>
      <GlitchText
        style={{
          fontFamily: MONO,
          fontSize: 190,
          fontWeight: 800,
          letterSpacing: 10,
          color: theme.text,
          transform: `scale(${0.8 + logoIn * 0.2})`,
          opacity: logoIn,
        }}
      >
        RED<span style={{ color: theme.red }}>CELL</span>
      </GlitchText>
      <div
        style={{
          marginTop: 18,
          fontFamily: MONO,
          fontSize: 34,
          letterSpacing: 8,
          color: theme.textDim,
          opacity: subIn,
        }}
      >
        AUTHORIZED RED-TEAM AGENT
      </div>
    </Scene>
  );
};

/* ============================ SCENE 2 — SCOPE ============================ */
const SceneScope: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const card = pop(frame, fps, 6);
  const stamp = pop(frame, fps, 34);
  const lines = [
    { t: `name: "${SCOPE.name}"`, c: theme.text },
    { t: `authorization_ref: "${SCOPE.auth}"`, c: theme.textDim },
    { t: "allow:", c: theme.green },
    { t: `  domains: ["${SCOPE.domain}"]`, c: theme.green },
    { t: "deny:  { hosts: [] }", c: theme.textDim },
  ];
  return (
    <Scene>
      <Eyebrow show={interpolate(frame, [0, 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}>
        01 · DEFINE THE SCOPE
      </Eyebrow>
      <div style={{ transform: `translateY(${(1 - card) * 40}px)`, opacity: card }}>
        <TerminalWindow title="scope.yaml" style={{ width: 920 }}>
          {lines.map((l, i) => {
            const show = interpolate(frame, [10 + i * 6, 16 + i * 6], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            return (
              <div
                key={i}
                style={{
                  fontFamily: MONO,
                  fontSize: 34,
                  lineHeight: 1.7,
                  color: l.c,
                  opacity: show,
                }}
              >
                {l.t}
              </div>
            );
          })}
        </TerminalWindow>
      </div>
      <div
        style={{
          marginTop: 34,
          fontFamily: MONO,
          fontSize: 32,
          color: theme.red,
          fontWeight: 700,
          letterSpacing: 2,
          transform: `scale(${0.8 + stamp * 0.2})`,
          opacity: stamp,
          border: `2px solid ${theme.red}`,
          padding: "10px 22px",
          borderRadius: 6,
        }}
      >
        ✖ NOTHING RUNS OUT OF SCOPE
      </div>
    </Scene>
  );
};

/* ============================ SCENE 3 — STAGES ============================ */
const CMD = 'redcell run "fingerprint scanme.nmap.org" --ui';
const SceneStages: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cmdChars = Math.floor(
    interpolate(frame, [6, 44], [0, CMD.length], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    })
  );
  const active = Math.min(3, Math.floor(interpolate(frame, [52, 100], [-1, 4])));
  const title = pop(frame, fps, 0);
  return (
    <Scene tint={theme.red} sweep>
      <Eyebrow show={title}>02 · ONE COMMAND</Eyebrow>
      <div style={{ transform: "translateZ(0)" }}>
        <TerminalWindow title="redcell — run" style={{ width: 1180, marginBottom: 54 }}>
          <div style={{ fontFamily: MONO, fontSize: 34, color: theme.text }}>
            <span style={{ color: theme.green }}>$ </span>
            {CMD.slice(0, cmdChars)}
            {cmdChars < CMD.length ? <Cursor color={theme.green} /> : null}
          </div>
        </TerminalWindow>
      </div>
      <StagePills stages={STAGES} active={active} />
      <div
        style={{
          marginTop: 30,
          fontFamily: MONO,
          fontSize: 26,
          color: theme.textDim,
          letterSpacing: 2,
          opacity: active >= 3 ? 1 : 0,
        }}
      >
        four specialized agents · one state-driven loop
      </div>
    </Scene>
  );
};

/* ============================ SCENE 4 — LIVE LOG ============================ */
const SceneLog: React.FC = () => {
  const frame = useCurrentFrame();
  const colorFor = (k: string) =>
    k === "stage"
      ? theme.red
      : k === "act"
      ? "#51b8ff"
      : k === "ok"
      ? theme.green
      : k === "audit"
      ? theme.amber
      : k === "data"
      ? theme.text
      : theme.textDim;
  return (
    <Scene>
      <div style={{ transform: "translateZ(0)" }}>
        <TerminalWindow title="redcell — live" style={{ width: 1320 }}>
          <div style={{ minHeight: 540 }}>
            {LOG_LINES.map((l, i) => {
              const at = 6 + i * 10;
              const show = interpolate(frame, [at, at + 5], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              const x = interpolate(frame, [at, at + 6], [-18, 0], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              const big = l.kind === "stage" || l.kind === "audit";
              return (
                <div
                  key={i}
                  style={{
                    fontFamily: MONO,
                    fontSize: big ? 34 : 30,
                    fontWeight: big ? 700 : 400,
                    lineHeight: 1.75,
                    color: colorFor(l.kind),
                    opacity: show,
                    transform: `translateX(${x}px)`,
                    textShadow: l.kind === "data" ? `0 0 18px ${theme.red}55` : "none",
                  }}
                >
                  {l.text}
                </div>
              );
            })}
          </div>
        </TerminalWindow>
      </div>
    </Scene>
  );
};

/* ============================ SCENE 5 — FINDING ============================ */
const SceneFinding: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const card = pop(frame, fps, 4);
  const gauge = interpolate(frame, [20, 70], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  return (
    <Scene tint={theme.red} sweep>
      <div
        style={{
          display: "flex",
          gap: 70,
          alignItems: "center",
          transform: `translateY(${(1 - card) * 40}px)`,
          opacity: card,
        }}
      >
        <CVSSGauge
          target={FINDING.score}
          severity={FINDING.severity}
          color={theme.critical}
          progress={gauge}
        />
        <div style={{ width: 760 }}>
          <div style={{ fontFamily: MONO, fontSize: 26, letterSpacing: 3, color: theme.red, marginBottom: 14 }}>
            FINDING · {FINDING.host}
          </div>
          <div
            style={{
              fontFamily: MONO,
              fontSize: 46,
              fontWeight: 800,
              color: theme.text,
              lineHeight: 1.2,
              marginBottom: 22,
            }}
          >
            {FINDING.title}
          </div>
          <div
            style={{
              fontFamily: MONO,
              fontSize: 28,
              color: theme.green,
              background: "#0c120d",
              border: "1px solid #173a22",
              borderRadius: 6,
              padding: "12px 18px",
              marginBottom: 18,
            }}
          >
            {FINDING.evidence}
          </div>
          <div style={{ fontFamily: MONO, fontSize: 20, color: theme.textFaint, wordBreak: "break-all" }}>
            {FINDING.vector}
          </div>
        </div>
      </div>
    </Scene>
  );
};

/* ============================ SCENE 6 — STATS ============================ */
const SceneStats: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <Scene>
      <div style={{ display: "flex", gap: 34 }}>
        {STATS.map((s, i) => {
          const p = pop(frame, fps, 6 + i * 7);
          return (
            <div
              key={i}
              style={{
                width: 360,
                height: 300,
                background: theme.bgPanel,
                border: `1px solid #22272d`,
                borderRadius: 12,
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                alignItems: "center",
                transform: `scale(${0.85 + p * 0.15})`,
                opacity: p,
                boxShadow: `0 0 0 1px ${theme.red}22, 0 30px 80px rgba(0,0,0,0.5)`,
              }}
            >
              <div
                style={{
                  fontFamily: MONO,
                  fontSize: 120,
                  fontWeight: 800,
                  color: i === 1 ? theme.green : theme.red,
                  textShadow: `0 0 34px ${(i === 1 ? theme.green : theme.red)}66`,
                }}
              >
                {s.value}
              </div>
              <div
                style={{
                  fontFamily: MONO,
                  fontSize: 24,
                  color: theme.textDim,
                  letterSpacing: 2,
                  textAlign: "center",
                  padding: "0 22px",
                }}
              >
                {s.label}
              </div>
            </div>
          );
        })}
      </div>
    </Scene>
  );
};

/* ============================ SCENE 7 — FEATURES ============================ */
const SceneFeatures: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <Scene tint={theme.red}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 26, width: 1480 }}>
        {FEATURES.map((f, i) => {
          const p = pop(frame, fps, 4 + i * 6);
          return (
            <div
              key={i}
              style={{
                background: theme.bgPanel,
                border: "1px solid #22272d",
                borderLeft: `4px solid ${theme.red}`,
                borderRadius: 10,
                padding: "28px 30px",
                transform: `translateX(${(1 - p) * -30}px)`,
                opacity: p,
              }}
            >
              <div
                style={{
                  fontFamily: MONO,
                  fontSize: 34,
                  fontWeight: 800,
                  color: theme.text,
                  letterSpacing: 1,
                  marginBottom: 10,
                }}
              >
                {f.k}
              </div>
              <div style={{ fontFamily: MONO, fontSize: 24, color: theme.textDim }}>{f.v}</div>
            </div>
          );
        })}
      </div>
    </Scene>
  );
};

/* ============================ SCENE 8 — OUTRO ============================ */
const SceneOutro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const logo = pop(frame, fps, 4);
  return (
    <Scene tint={theme.red}>
      <div
        style={{
          marginBottom: 40,
          opacity: interpolate(frame, [0, 14], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <ScannerEye width={420} />
      </div>
      <GlitchText
        intensity={1.6}
        style={{
          fontFamily: MONO,
          fontSize: 160,
          fontWeight: 800,
          letterSpacing: 10,
          color: theme.text,
          transform: `scale(${0.85 + logo * 0.15})`,
          opacity: logo,
        }}
      >
        RED<span style={{ color: theme.red }}>CELL</span>
      </GlitchText>
      <div
        style={{
          marginTop: 26,
          fontFamily: MONO,
          fontSize: 30,
          letterSpacing: 6,
          color: theme.textDim,
          opacity: interpolate(frame, [26, 44], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        scope-gated · multi-agent · evidence-grade
      </div>
      <div
        style={{
          marginTop: 40,
          fontFamily: MONO,
          fontSize: 26,
          color: theme.green,
          opacity: interpolate(frame, [40, 58], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        $ redcell run
        <Cursor color={theme.green} />
      </div>
    </Scene>
  );
};

/* faint author watermark, bottom-right, on every frame */
const Watermark: React.FC = () => (
  <AbsoluteFill style={{ pointerEvents: "none" }}>
    <div
      style={{
        position: "absolute",
        right: 56,
        bottom: 40,
        fontFamily: MONO,
        fontSize: 24,
        letterSpacing: 1,
        color: "rgba(232,236,236,0.13)",
        display: "flex",
        alignItems: "center",
        gap: 8,
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: 4,
          background: "rgba(255,43,43,0.35)",
        }}
      />
      @serifhaniskl
    </div>
  </AbsoluteFill>
);

/* ============================ ROOT COMPOSITION ============================ */
export const RedcellPromo: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: theme.bg }}>
    <Series>
      <Series.Sequence durationInFrames={90}>
        <SceneBoot />
      </Series.Sequence>
      <Series.Sequence durationInFrames={78}>
        <SceneScope />
      </Series.Sequence>
      <Series.Sequence durationInFrames={108}>
        <SceneStages />
      </Series.Sequence>
      <Series.Sequence durationInFrames={120}>
        <SceneLog />
      </Series.Sequence>
      <Series.Sequence durationInFrames={120}>
        <SceneFinding />
      </Series.Sequence>
      <Series.Sequence durationInFrames={78}>
        <SceneStats />
      </Series.Sequence>
      <Series.Sequence durationInFrames={96}>
        <SceneFeatures />
      </Series.Sequence>
      <Series.Sequence durationInFrames={90}>
        <SceneOutro />
      </Series.Sequence>
    </Series>
    <Watermark />
  </AbsoluteFill>
);
