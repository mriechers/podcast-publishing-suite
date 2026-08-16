import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { Background } from "./Background";
import { brand } from "../brand";

export interface ThumbnailProps {
  guestName?: string;
  episodeNumber?: string | number;
  episodeTitle?: string;
  showLogo?: boolean;
  backgroundImage?: string;
}

export const Thumbnail: React.FC<ThumbnailProps> = ({
  guestName,
  episodeNumber,
  episodeTitle,
  showLogo = true,
  backgroundImage,
}) => {
  const textShadow =
    "0 3px 30px rgba(0,0,0,0.8), 0 6px 60px rgba(0,0,0,0.5)";

  return (
    <AbsoluteFill>
      {/* Background */}
      <Background
        useGalaxySpiral={!backgroundImage}
        backgroundImage={backgroundImage}
        primaryColor={brand.colors.backgroundDark}
        secondaryColor={brand.colors.backgroundMedium}
        accentColor={brand.colors.primary}
        rotationSpeed={0}
        pulseIntensity={0}
      />

      {/* Dark gradient for text legibility */}
      {backgroundImage && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            background:
              "linear-gradient(to bottom, rgba(0,0,0,0.7) 0%, rgba(0,0,0,0.3) 50%, rgba(0,0,0,0.6) 100%)",
            pointerEvents: "none",
          }}
        />
      )}

      {/* Text content */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 80px",
        }}
      >
        {/* Logo */}
        {showLogo && (
          <Img
            src={staticFile(brand.assets.logoWordmark)}
            style={{
              height: 225,
              width: "auto",
              marginBottom: 50,
              filter: "drop-shadow(0 4px 20px rgba(0,0,0,0.5))",
            }}
          />
        )}

        {/* Episode number badge */}
        {episodeNumber && (
          <div
            style={{
              fontSize: 90,
              fontWeight: brand.typography.weights.semibold,
              color: brand.colors.primary,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              textShadow,
              marginBottom: 40,
              fontFamily: brand.typography.fontHeadline,
            }}
          >
            {`${episodeNumber} Episode`}
          </div>
        )}

        {/* Guest name — large and bold */}
        {guestName && (
          <div
            style={{
              fontSize: 220,
              fontWeight: brand.typography.weights.bold,
              color: brand.colors.textPrimary,
              textAlign: "center",
              textShadow,
              textTransform: "uppercase" as const,
              letterSpacing: "0.05em",
              marginBottom: 40,
              lineHeight: 1.1,
              fontFamily: brand.typography.fontHeadline,
            }}
          >
            {guestName}
          </div>
        )}

        {/* Episode title */}
        {episodeTitle && (
          <div
            style={{
              fontSize: 105,
              fontWeight: brand.typography.weights.medium,
              color: brand.colors.textSecondary,
              textAlign: "center",
              textShadow,
              maxWidth: "90%",
              lineHeight: 1.3,
              fontFamily: brand.typography.fontHeadline,
            }}
          >
            {episodeTitle}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

export default Thumbnail;
