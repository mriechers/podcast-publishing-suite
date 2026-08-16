import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
  Img,
  staticFile,
} from "remotion";
import { brand } from "../brand";

interface TextOverlayProps {
  guestName?: string;
  episodeNumber?: string | number;
  episodeTitle?: string;
  showLogo?: boolean;
  animateIn?: boolean;
  position?: "top" | "center" | "bottom";
}

/**
 * Text overlay component for podcast episode metadata.
 * Includes show logo, episode info, and guest name.
 * Responsive to aspect ratio with appropriate text sizing and positioning.
 */
export const TextOverlay: React.FC<TextOverlayProps> = ({
  guestName,
  episodeNumber,
  episodeTitle,
  showLogo = true,
  animateIn = true,
  position = "center",
}) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const isVertical = height > width;

  // Animation timing (frames)
  const logoDelay = 0;
  const episodeDelay = 15;
  const guestDelay = 25;
  const titleDelay = 35;

  // Scale factors based on orientation
  const scaleFactor = isVertical ? 0.85 : 1;

  // Font sizes
  const episodeSize = (isVertical ? 22 : 28) * scaleFactor;
  const guestSize = (isVertical ? 44 : 56) * scaleFactor;
  const titleSize = (isVertical ? 22 : 28) * scaleFactor;
  const logoHeight = (isVertical ? 60 : 80) * scaleFactor;

  // Position calculations
  const getContainerTop = () => {
    switch (position) {
      case "top":
        return isVertical ? height * 0.1 : height * 0.12;
      case "bottom":
        return isVertical ? height * 0.5 : height * 0.45;
      case "center":
      default:
        return isVertical ? height * 0.28 : height * 0.25;
    }
  };

  // Animation helper
  const getEntryAnimation = (delay: number) => {
    if (!animateIn) return { opacity: 1, translateY: 0 };

    const opacity = interpolate(frame - delay, [0, 20], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });

    const translateY = interpolate(frame - delay, [0, 25], [25, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    });

    return { opacity, translateY };
  };

  const containerStyle: React.CSSProperties = {
    position: "absolute",
    top: getContainerTop(),
    left: 0,
    right: 0,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    padding: isVertical ? "0 28px" : "0 60px",
  };

  const textShadow = "0 2px 20px rgba(0,0,0,0.6), 0 4px 40px rgba(0,0,0,0.4)";

  return (
    <div style={containerStyle}>
      {/* Show Logo */}
      {showLogo && (
        <AnimatedElement animation={getEntryAnimation(logoDelay)}>
          <Img
            src={staticFile(brand.assets.logoWordmark)}
            style={{
              height: logoHeight,
              width: "auto",
              marginBottom: 20,
              filter: "drop-shadow(0 2px 10px rgba(0,0,0,0.5))",
            }}
          />
        </AnimatedElement>
      )}

      {/* Episode Number */}
      {episodeNumber && (
        <AnimatedText
          text={`Episode ${episodeNumber}`}
          animation={getEntryAnimation(episodeDelay)}
          style={{
            fontSize: episodeSize,
            fontWeight: brand.typography.weights.medium,
            color: brand.colors.primary,
            letterSpacing: "0.15em",
            textTransform: "uppercase",
            textShadow,
            marginBottom: 16,
            fontFamily: brand.typography.fontHeadline,
          }}
        />
      )}

      {/* Guest Name - Primary focal point */}
      {guestName && (
        <AnimatedText
          text={guestName}
          animation={getEntryAnimation(guestDelay)}
          style={{
            fontSize: guestSize,
            fontWeight: brand.typography.weights.bold,
            color: brand.colors.textPrimary,
            textAlign: "center",
            textShadow,
            marginBottom: 12,
            lineHeight: 1.15,
            maxWidth: isVertical ? "100%" : "85%",
            fontFamily: brand.typography.fontHeadline,
          }}
        />
      )}

      {/* Episode Title */}
      {episodeTitle && (
        <AnimatedText
          text={episodeTitle}
          animation={getEntryAnimation(titleDelay)}
          style={{
            fontSize: titleSize,
            fontWeight: brand.typography.weights.regular,
            fontStyle: "italic",
            color: brand.colors.textSecondary,
            fontFamily: brand.typography.fontBody,
            textAlign: "center",
            textShadow,
            maxWidth: isVertical ? "100%" : "75%",
            lineHeight: 1.4,
          }}
        />
      )}
    </div>
  );
};

interface AnimatedTextProps {
  text: string;
  animation: { opacity: number; translateY: number };
  style: React.CSSProperties;
}

const AnimatedText: React.FC<AnimatedTextProps> = ({
  text,
  animation,
  style,
}) => {
  return (
    <div
      style={{
        ...style,
        opacity: animation.opacity,
        transform: `translateY(${animation.translateY}px)`,
      }}
    >
      {text}
    </div>
  );
};

interface AnimatedElementProps {
  animation: { opacity: number; translateY: number };
  children: React.ReactNode;
}

const AnimatedElement: React.FC<AnimatedElementProps> = ({
  animation,
  children,
}) => {
  return (
    <div
      style={{
        opacity: animation.opacity,
        transform: `translateY(${animation.translateY}px)`,
      }}
    >
      {children}
    </div>
  );
};

/**
 * Minimal text overlay for social clips - just the guest name and hook text.
 */
export const SocialTextOverlay: React.FC<{
  guestName?: string;
  hookText?: string;
  showLogo?: boolean;
  position?: "top" | "center" | "bottom";
}> = ({ guestName, hookText, showLogo = true, position = "top" }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const isVertical = height > width;

  // Animation
  const opacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateRight: "clamp",
  });

  const translateY = interpolate(frame, [0, 25], [-20, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const getTop = () => {
    switch (position) {
      case "top":
        return isVertical ? height * 0.1 : height * 0.12;
      case "bottom":
        return isVertical ? height * 0.7 : height * 0.65;
      case "center":
      default:
        return isVertical ? height * 0.35 : height * 0.3;
    }
  };

  const textShadow = "0 2px 20px rgba(0,0,0,0.7), 0 4px 40px rgba(0,0,0,0.5)";
  const logoHeight = isVertical ? 50 : 60;

  return (
    <div
      style={{
        position: "absolute",
        top: getTop(),
        left: 0,
        right: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "0 28px",
        opacity,
        transform: `translateY(${translateY}px)`,
      }}
    >
      {showLogo && (
        <Img
          src={staticFile(brand.assets.logoIcon)}
          style={{
            height: logoHeight,
            width: "auto",
            marginBottom: 16,
            filter: "drop-shadow(0 2px 10px rgba(0,0,0,0.5))",
          }}
        />
      )}
      {guestName && (
        <div
          style={{
            fontSize: isVertical ? 38 : 48,
            fontWeight: brand.typography.weights.bold,
            color: brand.colors.textPrimary,
            textShadow,
            textAlign: "center",
            marginBottom: hookText ? 14 : 0,
            fontFamily: brand.typography.fontHeadline,
          }}
        >
          {guestName}
        </div>
      )}
      {hookText && (
        <div
          style={{
            fontSize: isVertical ? 22 : 28,
            fontWeight: brand.typography.weights.medium,
            color: brand.colors.primary,
            textShadow,
            textAlign: "center",
            maxWidth: "90%",
            lineHeight: 1.35,
            fontFamily: brand.typography.fontHeadline,
          }}
        >
          "{hookText}"
        </div>
      )}
    </div>
  );
};

export default TextOverlay;
