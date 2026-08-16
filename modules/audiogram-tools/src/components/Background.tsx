import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Img,
  staticFile,
  AbsoluteFill,
} from "remotion";
import { brand } from "../brand";

interface BackgroundProps {
  /** Use the galaxy spiral image asset */
  useGalaxySpiral?: boolean;
  /** Custom background image filename (in public/). Replaces galaxy spiral when provided */
  backgroundImage?: string;
  /** Primary background color */
  primaryColor?: string;
  /** Secondary color for gradient */
  secondaryColor?: string;
  /** Accent color for floating elements */
  accentColor?: string;
  /** Rotation speed multiplier (0 = static, 1 = normal) */
  rotationSpeed?: number;
  /** Scale pulse intensity (0 = none, 1 = subtle) */
  pulseIntensity?: number;
}

/**
 * Animated background for podcast videos.
 *
 * Features:
 * - Optional galaxy spiral image (brand asset)
 * - Slow rotation animation
 * - Subtle pulse/breathing effect
 * - Floating geometric accents
 * - Responsive to 16:9 and 9:16 aspect ratios
 */
export const Background: React.FC<BackgroundProps> = ({
  useGalaxySpiral = true,
  backgroundImage,
  primaryColor = brand.colors.backgroundDark,
  secondaryColor = brand.colors.backgroundMedium,
  accentColor = brand.colors.primary,
  rotationSpeed = 0.5,
  pulseIntensity = 0.3,
}) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();

  const isVertical = height > width;
  const loopDuration = fps * 20; // 20-second animation loop
  const loopFrame = frame % loopDuration;

  // Slow rotation for galaxy spiral
  const rotation = interpolate(
    loopFrame,
    [0, loopDuration],
    [0, 360 * rotationSpeed]
  );

  // Subtle scale pulse (breathing effect)
  const scalePulse =
    1 +
    Math.sin((loopFrame / loopDuration) * Math.PI * 2) * 0.02 * pulseIntensity;

  // Galaxy spiral sizing - make it large enough to cover during rotation
  const spiralSize = Math.max(width, height) * 1.8;

  return (
    <AbsoluteFill>
      {/* Base solid background */}
      <div
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          backgroundColor: primaryColor,
        }}
      />

      {/* Radial gradient overlay for depth */}
      <div
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          background: `radial-gradient(ellipse at center, ${secondaryColor} 0%, ${primaryColor} 70%)`,
        }}
      />

      {/* Custom background image (full-bleed, no rotation) */}
      {backgroundImage && (
        <div
          style={{
            position: "absolute",
            width: "100%",
            height: "100%",
          }}
        >
          <Img
            src={staticFile(backgroundImage)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        </div>
      )}

      {/* Galaxy spiral image (used when no custom background) */}
      {!backgroundImage && useGalaxySpiral && (
        <div
          style={{
            position: "absolute",
            width: spiralSize,
            height: spiralSize,
            left: (width - spiralSize) / 2,
            top: (height - spiralSize) / 2,
            transform: `rotate(${rotation}deg) scale(${scalePulse})`,
            transformOrigin: "center center",
            opacity: 0.6,
          }}
        >
          <Img
            src={staticFile(brand.assets.galaxySpiral)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "contain",
            }}
          />
        </div>
      )}

      {/* Accent glow at center */}
      <div
        style={{
          position: "absolute",
          width: isVertical ? width * 0.8 : width * 0.5,
          height: isVertical ? width * 0.8 : width * 0.5,
          left: "50%",
          top: "50%",
          transform: "translate(-50%, -50%)",
          background: `radial-gradient(circle, ${accentColor}20 0%, transparent 70%)`,
          opacity: 0.5 + Math.sin((loopFrame / loopDuration) * Math.PI * 2) * 0.2,
        }}
      />

      {/* Floating accent particles */}
      <FloatingParticles
        count={isVertical ? 6 : 10}
        accentColor={accentColor}
        loopFrame={loopFrame}
        loopDuration={loopDuration}
        width={width}
        height={height}
      />

      {/* Vignette for cinematic depth */}
      <div
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          background:
            "radial-gradient(ellipse at center, transparent 30%, rgba(0,0,0,0.5) 100%)",
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};

interface FloatingParticlesProps {
  count: number;
  accentColor: string;
  loopFrame: number;
  loopDuration: number;
  width: number;
  height: number;
}

const FloatingParticles: React.FC<FloatingParticlesProps> = ({
  count,
  accentColor,
  loopFrame,
  loopDuration,
  width,
  height,
}) => {
  // Generate particles with deterministic positions
  const particles = Array.from({ length: count }, (_, i) => {
    const seed = i * 137.508; // Golden angle for nice distribution
    return {
      startX: ((Math.sin(seed) + 1) / 2) * width,
      startY: ((Math.cos(seed * 1.5) + 1) / 2) * height,
      size: 4 + (i % 4) * 2,
      speed: 0.3 + (i % 3) * 0.2,
      delay: (i / count) * loopDuration,
    };
  });

  return (
    <>
      {particles.map((particle, index) => {
        const adjustedFrame = (loopFrame + particle.delay) % loopDuration;
        const progress = adjustedFrame / loopDuration;

        // Gentle floating motion
        const xOffset = Math.sin(progress * Math.PI * 2) * 30 * particle.speed;
        const yOffset = Math.cos(progress * Math.PI * 2) * 20 * particle.speed;

        // Fade in/out for seamless loop
        const opacity = interpolate(
          Math.sin(progress * Math.PI * 2),
          [-1, 1],
          [0.1, 0.4]
        );

        return (
          <div
            key={index}
            style={{
              position: "absolute",
              left: particle.startX + xOffset,
              top: particle.startY + yOffset,
              width: particle.size,
              height: particle.size,
              borderRadius: "50%",
              backgroundColor: accentColor,
              opacity,
              boxShadow: `0 0 ${particle.size * 2}px ${accentColor}`,
            }}
          />
        );
      })}
    </>
  );
};

export default Background;
