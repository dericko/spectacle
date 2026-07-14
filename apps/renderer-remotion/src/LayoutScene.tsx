import { AbsoluteFill, useVideoConfig, interpolate, useCurrentFrame } from "remotion";

export type LayoutSceneProps = {
  onScreenText: string;
  durationInSeconds: number;
  items?: string[];
  sceneType?: string;
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

const SCENE_META: Record<string, { badge: string; color: string }> = {
  intro: { badge: "Introduction", color: "#60a5fa" },
  concept_explanation: { badge: "Key Concept", color: "#a78bfa" },
  worked_example: { badge: "Worked Example", color: "#fb923c" },
  guided_practice: { badge: "Try It!", color: "#facc15" },
  recap: { badge: "Recap", color: ACCENT },
};

function getBadgeMeta(sceneType?: string) {
  if (!sceneType) return null;
  // Accept both "concept_explanation" and "concept_explanation_1" style IDs
  for (const [key, meta] of Object.entries(SCENE_META)) {
    if (sceneType === key || sceneType.startsWith(key + "_")) {
      return meta;
    }
  }
  return null;
}

export const LayoutScene: React.FC<LayoutSceneProps> = ({
  onScreenText,
  items,
  sceneType,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const badgeMeta = getBadgeMeta(sceneType);

  const globalFadeOut = interpolate(
    frame,
    [durationInFrames - 18, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const headerOpacity = interpolate(frame, [0, 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const titleOpacity = interpolate(frame, [8, 26], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const titleY = interpolate(frame, [8, 26], [14, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const dividerScale = interpolate(frame, [20, 36], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  if (items && items.length > 0) {
    return (
      <AbsoluteFill
        style={{
          backgroundColor: BG,
          padding: "72px 112px 80px",
          flexDirection: "column",
          justifyContent: "center",
          opacity: globalFadeOut,
        }}
      >
        {/* Top accent stripe */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: 5,
            background: badgeMeta ? badgeMeta.color : ACCENT,
            opacity: headerOpacity,
          }}
        />

        {/* Scene type badge */}
        {badgeMeta && (
          <div
            style={{
              opacity: headerOpacity,
              display: "inline-flex",
              alignItems: "center",
              alignSelf: "flex-start",
              gap: 8,
              padding: "5px 14px",
              borderRadius: 99,
              background: badgeMeta.color + "22",
              border: `1px solid ${badgeMeta.color}55`,
              marginBottom: 28,
            }}
          >
            <div
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: badgeMeta.color,
              }}
            />
            <span
              style={{
                color: badgeMeta.color,
                fontSize: 22,
                fontFamily: "sans-serif",
                fontWeight: 700,
                letterSpacing: "0.05em",
                textTransform: "uppercase",
              }}
            >
              {badgeMeta.badge}
            </span>
          </div>
        )}

        {/* Title */}
        <h1
          style={{
            opacity: titleOpacity,
            transform: `translateY(${titleY}px)`,
            color: "white",
            fontSize: 62,
            fontFamily: "sans-serif",
            fontWeight: 800,
            margin: 0,
            marginBottom: 32,
            lineHeight: 1.15,
          }}
        >
          {onScreenText}
        </h1>

        {/* Divider */}
        <div
          style={{
            height: 2,
            background: "rgba(255,255,255,0.12)",
            marginBottom: 44,
            transform: `scaleX(${dividerScale})`,
            transformOrigin: "left",
          }}
        />

        {/* Bullet items */}
        <div style={{ display: "flex", flexDirection: "column", gap: 26 }}>
          {items.map((item, i) => {
            const delay = 38 + i * 20;
            const itemOpacity = interpolate(frame, [delay, delay + 16], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const itemX = interpolate(frame, [delay, delay + 16], [-16, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const accentColor = badgeMeta ? badgeMeta.color : ACCENT;
            return (
              <div
                key={i}
                style={{
                  opacity: itemOpacity,
                  transform: `translateX(${itemX}px)`,
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 22,
                }}
              >
                {/* Number badge */}
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: "50%",
                    background: accentColor + "25",
                    border: `2px solid ${accentColor}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    marginTop: 4,
                  }}
                >
                  <span
                    style={{
                      color: accentColor,
                      fontSize: 18,
                      fontFamily: "sans-serif",
                      fontWeight: 700,
                    }}
                  >
                    {i + 1}
                  </span>
                </div>
                <span
                  style={{
                    color: "rgba(255,255,255,0.92)",
                    fontSize: 40,
                    fontFamily: "sans-serif",
                    lineHeight: 1.3,
                    fontWeight: 500,
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

  // Fallback: centered title card
  const opacity = interpolate(
    frame,
    [0, 18, durationInFrames - 18, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const scale = interpolate(frame, [0, 18], [0.94, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{ backgroundColor: BG, justifyContent: "center", alignItems: "center" }}
    >
      {/* Top stripe */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 5,
          background: badgeMeta ? badgeMeta.color : ACCENT,
          opacity,
        }}
      />

      <div
        style={{
          opacity,
          transform: `scale(${scale})`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 20,
          padding: "0 120px",
          textAlign: "center",
        }}
      >
        {badgeMeta && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "5px 16px",
              borderRadius: 99,
              background: badgeMeta.color + "22",
              border: `1px solid ${badgeMeta.color}55`,
              marginBottom: 8,
            }}
          >
            <div
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: badgeMeta.color,
              }}
            />
            <span
              style={{
                color: badgeMeta.color,
                fontSize: 20,
                fontFamily: "sans-serif",
                fontWeight: 700,
                letterSpacing: "0.05em",
                textTransform: "uppercase",
              }}
            >
              {badgeMeta.badge}
            </span>
          </div>
        )}
        <div
          style={{
            color: "white",
            fontSize: 72,
            fontFamily: "sans-serif",
            fontWeight: 800,
            lineHeight: 1.15,
          }}
        >
          {onScreenText}
        </div>
      </div>
    </AbsoluteFill>
  );
};
