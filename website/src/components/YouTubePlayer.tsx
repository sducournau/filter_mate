import React from "react";
import styles from "./YouTubePlayer.module.css";

interface YouTubePlayerProps {
  /** YouTube video ID (the part after v= in the URL) */
  videoId: string;
  /** Optional title for accessibility */
  title?: string;
  /** Optional aspect ratio: '16:9' (default) or '4:3' */
  aspectRatio?: "16:9" | "4:3";
  /** Start time in seconds */
  start?: number;
  /** Enable privacy-enhanced mode (no cookies until play) */
  privacyMode?: boolean;
}

/**
 * Responsive YouTube Player component with privacy-enhanced mode.
 *
 * Usage in MDX:
 * ```mdx
 * import YouTubePlayer from '@site/src/components/YouTubePlayer';
 *
 * <YouTubePlayer videoId="2gOEPrdl2Bo" title="FilterMate Demo" />
 * ```
 */
export default function YouTubePlayer({
  videoId,
  title = "YouTube video player",
  aspectRatio = "16:9",
  start = 0,
  privacyMode = true,
}: YouTubePlayerProps): JSX.Element {
  // Use privacy-enhanced mode by default (no cookies until play)
  const baseUrl = privacyMode
    ? "https://www.youtube-nocookie.com/embed"
    : "https://www.youtube.com/embed";

  const params = new URLSearchParams({
    rel: "0", // Don't show related videos from other channels
    modestbranding: "1", // Minimal YouTube branding
    ...(start > 0 && { start: start.toString() }),
  });

  const embedUrl = `${baseUrl}/${videoId}?${params.toString()}`;

  const aspectRatioClass =
    aspectRatio === "4:3" ? styles.aspectRatio4x3 : styles.aspectRatio16x9;

  return (
    <div className={`${styles.videoContainer} ${aspectRatioClass}`}>
      <iframe
        className={styles.videoIframe}
        src={embedUrl}
        title={title}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowFullScreen
        loading="lazy"
      />
    </div>
  );
}
