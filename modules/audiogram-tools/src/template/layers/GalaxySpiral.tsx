import React from "react";
import {
  AbsoluteFill,
  Img,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";

interface GalaxySpiralProps {
  /** Filename in public/ directory */
  asset: string;
  /** Rotation speed multiplier (0.5 = half speed) */
  rotationSpeed?: number;
  /** Opacity of the spiral layer */
  opacity?: number;
}

/**
 * Rotating galaxy spiral overlay. The spiral image is white particles
 * on a transparent/black background, so it composites naturally over
 * a colored background.
 */
export const GalaxySpiral: React.FC<GalaxySpiralProps> = ({
  asset,
  rotationSpeed = 0.5,
  opacity = 1.0,
}) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();

  const loopDuration = fps * 20; // 20-second loop
  const loopFrame = frame % loopDuration;

  const rotation = interpolate(
    loopFrame,
    [0, loopDuration],
    [0, 360 * rotationSpeed]
  );

  const scalePulse =
    1 + Math.sin((loopFrame / loopDuration) * Math.PI * 2) * 0.02;

  const isVertical = height > width;
  const spiralSize = Math.max(width, height) * 1.1;

  // Center the spiral on the cabinet, not the frame.
  // AE horizontal: spiral centered at 50% of frame (cabinet is centered)
  // AE vertical: spiral centered at 26% of frame (cabinet is in upper half)
  const spiralCenterY = isVertical ? height * 0.26 : height / 2;

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          width: spiralSize,
          height: spiralSize,
          left: (width - spiralSize) / 2,
          top: spiralCenterY - spiralSize / 2,
          transform: `rotate(${rotation}deg) scale(${scalePulse})`,
          transformOrigin: "center center",
          opacity,
          // The source image has very low alpha (max 28%). Boost brightness
          // so the spiral particles are more visible against the green bg.
          filter: "brightness(2.5)",
        }}
      >
        <Img
          src={staticFile(asset)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
