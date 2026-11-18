import React from "react";
import { Composition } from "remotion";
import { RedcellPromo } from "./RedcellPromo";
import { FPS, WIDTH, HEIGHT } from "./theme";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="RedcellPromo"
      component={RedcellPromo}
      durationInFrames={780}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  );
};
