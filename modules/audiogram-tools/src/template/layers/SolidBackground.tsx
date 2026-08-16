import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

interface SolidBackgroundProps {
  color: string;
  grain?: boolean;
}

/**
 * Full-bleed solid color background with optional grain texture.
 * Grain uses a repeating SVG noise pattern for subtle film-stock texture.
 */
export const SolidBackground: React.FC<SolidBackgroundProps> = ({
  color,
  grain = false,
}) => {
  const frame = useCurrentFrame();

  // Shift the grain pattern slightly each frame for organic movement
  const grainOffset = grain ? (frame * 0.7) % 200 : 0;

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          backgroundColor: color,
        }}
      />
      {grain && (
        <div
          style={{
            position: "absolute",
            width: "100%",
            height: "100%",
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
            backgroundPosition: `${grainOffset}px ${grainOffset}px`,
            opacity: 0.06,
            mixBlendMode: "overlay",
          }}
        />
      )}
    </AbsoluteFill>
  );
};
