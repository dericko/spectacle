import { AbsoluteFill, useVideoConfig, interpolate, useCurrentFrame } from "remotion";
import { resolveIcon } from "./icons";

export type LayoutSceneProps = {
  onScreenText: string;
  durationInSeconds: number;
  items?: string[];
  sceneType?: string;
  // Seconds into the narration when each item's sentence begins speaking,
  // computed from actual narration word timing (see render_scene.py).
  // Falls back to an even stagger when absent so old artifacts still render.
  itemStartTimesS?: number[];
  // Name of a fixed icon (see icons.tsx) picked by the script LLM for each
  // bullet's visual element. Falls back to a deterministic icon cycle when
  // absent/unrecognized so old artifacts still render a visual.
  itemIcons?: string[];
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

const SCENE_META: Record<string, { badge: string; color: string; layout: "spotlight" | "cards" | "timeline" }> = {
  intro: { badge: "Introduction", color: "#60a5fa", layout: "cards" },
  concept_explanation: { badge: "Key Concept", color: "#a78bfa", layout: "spotlight" },
  worked_example: { badge: "Worked Example", color: "#fb923c", layout: "timeline" },
  guided_practice: { badge: "Try It!", color: "#facc15", layout: "timeline" },
  recap: { badge: "Recap", color: ACCENT, layout: "cards" },
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

// Which bullet's sentence is currently being narrated, so the "spotlight"
// and "timeline" layouts can highlight/update their visual in sync with
// speech rather than just fading every bullet in once and leaving them all.
function currentItemIndex(frame: number, fps: number, itemStartTimesS: number[] | undefined, count: number) {
  if (!itemStartTimesS || itemStartTimesS.length === 0) return 0;
  const t = frame / fps;
  let idx = 0;
  for (let i = 0; i < count; i++) {
    if (itemStartTimesS[i] != null && t >= itemStartTimesS[i]) idx = i;
  }
  return idx;
}

function itemDelay(i: number, itemStartTimesS: number[] | undefined, fps: number, minStartBase = 38, minStartStep = 8) {
  const minStart = minStartBase + i * minStartStep;
  return itemStartTimesS?.[i] != null
    ? Math.max(Math.round(itemStartTimesS[i] * fps), minStart)
    : 38 + i * 20;
}

function Header({
  headerOpacity,
  titleOpacity,
  titleY,
  dividerScale,
  badgeMeta,
  onScreenText,
}: {
  headerOpacity: number;
  titleOpacity: number;
  titleY: number;
  dividerScale: number;
  badgeMeta: { badge: string; color: string } | null;
  onScreenText: string;
}) {
  return (
    <>
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
          <div style={{ width: 7, height: 7, borderRadius: "50%", background: badgeMeta.color }} />
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
      <div
        style={{
          height: 2,
          background: "rgba(255,255,255,0.12)",
          marginBottom: 44,
          transform: `scaleX(${dividerScale})`,
          transformOrigin: "left",
        }}
      />
    </>
  );
}

// "Spotlight" layout: bullets stacked on the left; a large icon panel on the
// right shows the visual for whichever bullet is currently being narrated,
// crossfading as the active bullet changes.
function SpotlightLayout({
  items, itemIcons, itemStartTimesS, frame, fps, accentColor,
}: {
  items: string[]; itemIcons: string[] | undefined; itemStartTimesS: number[] | undefined;
  frame: number; fps: number; accentColor: string;
}) {
  const activeIdx = currentItemIndex(frame, fps, itemStartTimesS, items.length);

  return (
    <div style={{ display: "flex", flex: 1, gap: 56, alignItems: "center" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 26, flex: 1.2 }}>
        {items.map((item, i) => {
          const delay = itemDelay(i, itemStartTimesS, fps);
          const opacity = interpolate(frame, [delay, delay + 16], [0, 1], {
            extrapolateLeft: "clamp", extrapolateRight: "clamp",
          });
          const x = interpolate(frame, [delay, delay + 16], [-16, 0], {
            extrapolateLeft: "clamp", extrapolateRight: "clamp",
          });
          const isActive = i === activeIdx;
          return (
            <div
              key={i}
              style={{
                opacity,
                transform: `translateX(${x}px)`,
                display: "flex",
                alignItems: "flex-start",
                gap: 22,
              }}
            >
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "50%",
                  background: (isActive ? accentColor : accentColor) + (isActive ? "45" : "25"),
                  border: `2px solid ${accentColor}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  marginTop: 4,
                }}
              >
                <span style={{ color: accentColor, fontSize: 18, fontFamily: "sans-serif", fontWeight: 700 }}>
                  {i + 1}
                </span>
              </div>
              <span
                style={{
                  color: isActive ? "rgba(255,255,255,0.98)" : "rgba(255,255,255,0.75)",
                  fontSize: 40,
                  fontFamily: "sans-serif",
                  lineHeight: 1.3,
                  fontWeight: isActive ? 600 : 500,
                }}
              >
                {item}
              </span>
            </div>
          );
        })}
      </div>

      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", position: "relative", height: 320 }}>
        {items.map((_, i) => {
          const Icon = resolveIcon(itemIcons?.[i], i);
          const isActive = i === activeIdx;
          const opacity = interpolate(frame, [0, 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) * (isActive ? 1 : 0);
          const scale = isActive ? 1 : 0.85;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                opacity,
                transform: `scale(${scale})`,
                width: 260,
                height: 260,
                borderRadius: 32,
                background: accentColor + "14",
                border: `2px solid ${accentColor}55`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Icon color={accentColor} size={120} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

// "Cards" layout: bullets shown as a horizontal row of cards, each with its
// own icon; the card for the currently-narrated bullet scales up.
function CardsLayout({
  items, itemIcons, itemStartTimesS, frame, fps, accentColor,
}: {
  items: string[]; itemIcons: string[] | undefined; itemStartTimesS: number[] | undefined;
  frame: number; fps: number; accentColor: string;
}) {
  const activeIdx = currentItemIndex(frame, fps, itemStartTimesS, items.length);
  return (
    <div style={{ display: "flex", flex: 1, alignItems: "center", justifyContent: "center", gap: 32 }}>
      {items.map((item, i) => {
        const delay = itemDelay(i, itemStartTimesS, fps);
        const opacity = interpolate(frame, [delay, delay + 16], [0, 1], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        });
        const y = interpolate(frame, [delay, delay + 16], [24, 0], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        });
        const isActive = i === activeIdx;
        const Icon = resolveIcon(itemIcons?.[i], i);
        return (
          <div
            key={i}
            style={{
              opacity,
              transform: `translateY(${y}px) scale(${isActive ? 1.06 : 1})`,
              flex: 1,
              maxWidth: 340,
              background: isActive ? accentColor + "1c" : "rgba(255,255,255,0.04)",
              border: `2px solid ${isActive ? accentColor : "rgba(255,255,255,0.12)"}`,
              borderRadius: 24,
              padding: "36px 28px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 22,
              textAlign: "center",
            }}
          >
            <div
              style={{
                width: 96,
                height: 96,
                borderRadius: "50%",
                background: accentColor + "22",
                border: `2px solid ${accentColor}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Icon color={accentColor} size={48} />
            </div>
            <span style={{ color: "rgba(255,255,255,0.92)", fontSize: 30, fontFamily: "sans-serif", fontWeight: 600, lineHeight: 1.3 }}>
              {item}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// "Timeline" layout: bullets laid out along a horizontal connecting line
// with icon nodes, used for sequential/step-like scenes.
function TimelineLayout({
  items, itemIcons, itemStartTimesS, frame, fps, accentColor,
}: {
  items: string[]; itemIcons: string[] | undefined; itemStartTimesS: number[] | undefined;
  frame: number; fps: number; accentColor: string;
}) {
  const activeIdx = currentItemIndex(frame, fps, itemStartTimesS, items.length);
  const lineProgress = interpolate(frame, [30, 30 + items.length * 20], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <div style={{ display: "flex", flex: 1, flexDirection: "column", justifyContent: "center", gap: 48, position: "relative" }}>
      <div style={{ position: "relative", display: "flex", justifyContent: "space-between", paddingTop: 12 }}>
        <div style={{ position: "absolute", left: 48, right: 48, top: 48, height: 3, background: "rgba(255,255,255,0.12)" }} />
        <div
          style={{
            position: "absolute", left: 48, top: 48, height: 3, background: accentColor,
            width: `calc((100% - 96px) * ${lineProgress})`,
          }}
        />
        {items.map((_, i) => {
          const delay = itemDelay(i, itemStartTimesS, fps);
          const opacity = interpolate(frame, [delay, delay + 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const scale = interpolate(frame, [delay, delay + 14], [0.6, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const isActive = i === activeIdx;
          const Icon = resolveIcon(itemIcons?.[i], i);
          return (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 18, flex: 1, opacity, transform: `scale(${scale})` }}>
              <div
                style={{
                  width: 96, height: 96, borderRadius: "50%",
                  background: isActive ? accentColor + "33" : "rgba(255,255,255,0.05)",
                  border: `3px solid ${isActive ? accentColor : "rgba(255,255,255,0.25)"}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  zIndex: 1,
                }}
              >
                <Icon color={isActive ? accentColor : "rgba(255,255,255,0.55)"} size={44} />
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", gap: 24 }}>
        {items.map((item, i) => {
          const delay = itemDelay(i, itemStartTimesS, fps);
          const opacity = interpolate(frame, [delay, delay + 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const isActive = i === activeIdx;
          return (
            <span
              key={i}
              style={{
                opacity,
                flex: 1,
                textAlign: "center",
                color: isActive ? "rgba(255,255,255,0.96)" : "rgba(255,255,255,0.65)",
                fontSize: 28,
                fontFamily: "sans-serif",
                fontWeight: isActive ? 600 : 500,
                lineHeight: 1.35,
              }}
            >
              {item}
            </span>
          );
        })}
      </div>
    </div>
  );
}

export const LayoutScene: React.FC<LayoutSceneProps> = ({
  onScreenText,
  items,
  sceneType,
  itemStartTimesS,
  itemIcons,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();

  const badgeMeta = getBadgeMeta(sceneType);
  const layoutKind = badgeMeta?.layout ?? "spotlight";
  const accentColor = badgeMeta ? badgeMeta.color : ACCENT;

  const globalFadeOut = interpolate(
    frame,
    [durationInFrames - 18, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const headerOpacity = interpolate(frame, [0, 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const titleOpacity = interpolate(frame, [8, 26], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const titleY = interpolate(frame, [8, 26], [14, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const dividerScale = interpolate(frame, [20, 36], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  if (items && items.length > 0) {
    return (
      <AbsoluteFill
        style={{
          backgroundColor: BG,
          padding: "72px 112px 80px",
          flexDirection: "column",
          opacity: globalFadeOut,
        }}
      >
        <Header
          headerOpacity={headerOpacity}
          titleOpacity={titleOpacity}
          titleY={titleY}
          dividerScale={dividerScale}
          badgeMeta={badgeMeta}
          onScreenText={onScreenText}
        />

        {layoutKind === "cards" && (
          <CardsLayout items={items} itemIcons={itemIcons} itemStartTimesS={itemStartTimesS} frame={frame} fps={fps} accentColor={accentColor} />
        )}
        {layoutKind === "timeline" && (
          <TimelineLayout items={items} itemIcons={itemIcons} itemStartTimesS={itemStartTimesS} frame={frame} fps={fps} accentColor={accentColor} />
        )}
        {layoutKind === "spotlight" && (
          <SpotlightLayout items={items} itemIcons={itemIcons} itemStartTimesS={itemStartTimesS} frame={frame} fps={fps} accentColor={accentColor} />
        )}
      </AbsoluteFill>
    );
  }

  // Fallback: centered title card (no bullets to visualize)
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
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 5,
          background: accentColor,
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
            <div style={{ width: 7, height: 7, borderRadius: "50%", background: badgeMeta.color }} />
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
