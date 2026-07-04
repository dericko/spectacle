import { AbsoluteFill, useVideoConfig, interpolate, useCurrentFrame } from "remotion";

export type LayoutSceneProps = {
  onScreenText: string;
  durationInSeconds: number;
};

export const calculateLayoutSceneMetadata = ({ props }: { props: LayoutSceneProps }) => {
  const fps = 30;
  return {
    fps,
    durationInFrames: Math.round(props.durationInSeconds * fps),
  };
};

export const LayoutScene: React.FC<LayoutSceneProps> = ({ onScreenText }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = interpolate(
    frame,
    [0, 15, durationInFrames - 15, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#0b1021", justifyContent: "center", alignItems: "center" }}>
      <div style={{ opacity, color: "white", fontSize: 64, fontFamily: "sans-serif", textAlign: "center", padding: "0 80px" }}>
        {onScreenText}
      </div>
    </AbsoluteFill>
  );
};
