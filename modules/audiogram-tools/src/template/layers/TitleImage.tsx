import React from "react";
import { AbsoluteFill, Img, staticFile, useVideoConfig } from "remotion";

interface TitleImageProps {
  /** Title image asset filename in public/ directory */
  asset: string;
  /** Layout mode: flanking (left/right of cabinet) or stacked (below) */
  layout: "flanking" | "stacked";
  /** Left word image for flanking layout (e.g. "wonder.png") */
  leftAsset?: string;
  /** Right word image for flanking layout (e.g. "cabinet.png") */
  rightAsset?: string;
}

/**
 * Show title image with orientation-aware layout.
 *
 * - flanking: "WONDER" left + "CABINET" right of the cabinet (horizontal videos).
 *   Uses the pre-split word assets (wonder.png, cabinet.png) already in public/.
 * - stacked: Full title image centered below the cabinet (vertical videos).
 */
export const TitleImage: React.FC<TitleImageProps> = ({
  asset,
  layout,
  leftAsset,
  rightAsset,
}) => {
  const { width, height } = useVideoConfig();

  if (layout === "flanking" && leftAsset && rightAsset) {
    // AE ref: measured WONDER wordmark width = 535px on 1920 frame.
    // wonder.png aspect after trim = 2314/261 = 8.866. Target render
    // height = 535 / 8.866 = 60.3px = 5.58% of 1080. Use 0.057 to match.
    const wordHeight = height * 0.057;
    return (
      <AbsoluteFill>
        <div
          style={{
            position: "absolute",
            left: width * 0.025,
            top: "41.5%",
            transform: "translateY(-50%)",
            height: wordHeight,
          }}
        >
          <Img
            src={staticFile(leftAsset)}
            style={{ height: "100%", width: "auto" }}
          />
        </div>
        <div
          style={{
            position: "absolute",
            right: width * 0.025,
            top: "41.5%",
            transform: "translateY(-50%)",
            height: wordHeight,
          }}
        >
          <Img
            src={staticFile(rightAsset)}
            style={{ height: "100%", width: "auto" }}
          />
        </div>
      </AbsoluteFill>
    );
  }

  // Stacked layout — title below cabinet.
  // TODO: vertical layout needs dedicated tuning pass (see issue #3)
  const titleWidth = width * 0.85;
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          bottom: height * 0.08,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "center",
        }}
      >
        <Img
          src={staticFile(asset)}
          style={{ width: titleWidth, height: "auto" }}
        />
      </div>
    </AbsoluteFill>
  );
};
