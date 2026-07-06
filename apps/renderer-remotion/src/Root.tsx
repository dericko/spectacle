import { Composition } from "remotion";
import { LayoutScene, calculateLayoutSceneMetadata, LayoutSceneProps } from "./LayoutScene";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="LayoutScene"
      component={LayoutScene}
      durationInFrames={150}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{ onScreenText: "Hello!", durationInSeconds: 5 }}
      calculateMetadata={calculateLayoutSceneMetadata}
    />
  );
};
