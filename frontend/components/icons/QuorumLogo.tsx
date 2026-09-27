interface QuorumLogoProps {
  className?: string;
}

/**
 * Three overlapping circles ("agents agreeing") in the accent gradient.
 * Circles are semi-transparent so their overlaps blend into a fourth,
 * central tone — a quorum forming from individual agents.
 */
export default function QuorumLogo({ className = "h-8 w-8" }: QuorumLogoProps) {
  return (
    <svg viewBox="0 0 48 48" fill="none" className={className} aria-hidden="true">
      <circle cx="19" cy="18" r="13" fill="rgb(var(--color-accent-from))" fillOpacity="0.75" />
      <circle cx="29" cy="18" r="13" fill="rgb(var(--color-accent-via))" fillOpacity="0.75" />
      <circle cx="24" cy="29" r="13" fill="rgb(var(--color-accent-to))" fillOpacity="0.75" />
    </svg>
  );
}
