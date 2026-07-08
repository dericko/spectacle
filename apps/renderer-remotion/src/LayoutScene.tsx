import { AbsoluteFill, useVideoConfig, interpolate, useCurrentFrame } from "remotion";

export type LayoutSceneProps = {
  onScreenText: string;
  durationInSeconds: number;
  items?: string[];
};

export const calculateLayoutSceneMetadata = ({ props }: { props: LayoutSceneProps }) => {
  const fps = 30;
  return {
    fps,
    durationInFrames: Math.round(props.durationInSeconds * fps),
  };
};

const BG = "#0b1021";
const ACCENT = "#4ade80";

export const LayoutScene: React.FC<LayoutSceneProps> = ({ onScreenText, items }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const globalFadeOut = interpolate(
    frame,
    [durationInFrames - 20, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  if (items && items.length > 0) {
    const titleOpacity = interpolate(frame, [0, 20], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });

    return (
      <AbsoluteFill
        style={{
          backgroundColor: BG,
          padding: "80px 120px",
          justifyContent: "center",
          opacity: globalFadeOut,
        }}
      >
        {/* Title */}
        <h1
          style={{
            opacity: titleOpacity,
            color: "white",
            fontSize: 56,
            fontFamily: "sans-serif",
            fontWeight: 700,
            margin: 0,
            marginBottom: 40,
            lineHeight: 1.2,
          }}
        >
          {onScreenText}
        </h1>

        {/* Divider */}
        <div
          style={{
            opacity: titleOpacity,
            height: 2,
            background: "rgba(255,255,255,0.15)",
            marginBottom: 40,
          }}
        />

        {/* Bullet items */}
        <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
          {items.map((item, i) => {
            const delay = 30 + i * 22;
            const itemOpacity = interpolate(frame, [delay, delay + 18], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const itemY = interpolate(frame, [delay, delay + 18], [18, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            return (
              <div
                key={i}
                style={{
                  opacity: itemOpacity,
                  transform: `translateY(${itemY}px)`,
                  display: "flex",
                  alignItems: "center",
                  gap: 20,
                }}
              >
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    background: ACCENT,
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    color: "rgba(255,255,255,0.9)",
                    fontSize: 38,
                    fontFamily: "sans-serif",
                    lineHeight: 1.3,
                  }}
                >
                  {item}
                </span>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    );
  }

  // Fallback: centered single-text with fade in/out
  const opacity = interpolate(
    frame,
    [0, 15, durationInFrames - 15, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill
      style={{ backgroundColor: BG, justifyContent: "center", alignItems: "center" }}
    >
      <div
        style={{
          opacity,
          color: "white",
          fontSize: 64,
          fontFamily: "sans-serif",
          textAlign: "center",
          padding: "0 80px",
        }}
      >
        {onScreenText}
      </div>
    </AbsoluteFill>
  );
};
