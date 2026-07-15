// Fixed set of simple inline-SVG icons used as the per-bullet visual element.
// Kept as plain stroked shapes (no external fonts/images) so they render
// deterministically under headless Chromium during `remotion render`.
// Names here must stay in sync with the enum the script agent LLM is
// prompted with (packages/core/src/spectacle_core/nodes/script_agent.py).

export type IconProps = {
  color: string;
  size?: number;
};

type IconFC = React.FC<IconProps>;

const stroke = (color: string) => ({
  fill: "none",
  stroke: color,
  strokeWidth: 2.4,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
});

const Lightbulb: IconFC = ({ color, size = 48 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...stroke(color)}>
    <path d="M9 18h6M10 21h4" />
    <path d="M12 2a6 6 0 0 0-3.5 10.9c.6.45 1 1.2 1 2.1h5c0-.9.4-1.65 1-2.1A6 6 0 0 0 12 2Z" />
  </svg>
);

const Target: IconFC = ({ color, size = 48 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...stroke(color)}>
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="5" />
    <circle cx="12" cy="12" r="1" fill={color} />
  </svg>
);

const Book: IconFC = ({ color, size = 48 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...stroke(color)}>
    <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5Z" />
    <path d="M4 5.5v15" />
  </svg>
);

const ChartBar: IconFC = ({ color, size = 48 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...stroke(color)}>
    <path d="M4 20V10M12 20V4M20 20v-7" />
    <path d="M2 20h20" />
  </svg>
);

const ChartLine: IconFC = ({ color, size = 48 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...stroke(color)}>
    <path d="M3 17l5-6 4 3 6-8" />
    <path d="M3 20h18" />
  </svg>
);

const Check: IconFC = ({ color, size = 48 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...stroke(color)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M8 12.5l2.5 2.5L16 9" />
  </svg>
);

const Calculator: IconFC = ({ color, size = 48 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...stroke(color)}>
    <rect x="5" y="2.5" width="14" height="19" rx="2" />
    <path d="M8 6.5h8M8 11h2M11.5 11h2M15 11h2M8 15h2M11.5 15h2M15 15v4M8 19h2" />
  </svg>
);

const Puzzle: IconFC = ({ color, size = 48 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...stroke(color)}>
    <path d="M9 3h4v2.2a1.8 1.8 0 1 0 0 3.6V11h-2.2a1.8 1.8 0 1 0-3.6 0H3V7a2 2 0 0 1 2-2h4Z" />
    <path d="M9 21h4v-2.2a1.8 1.8 0 1 1 0-3.6V13h-2.2a1.8 1.8 0 1 1-3.6 0H3v6a2 2 0 0 0 2 2h4Z" />
  </svg>
);

const Star: IconFC = ({ color, size = 48 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...stroke(color)}>
    <path d="M12 2.8l2.6 5.6 6 .7-4.5 4.1 1.2 6-5.3-3-5.3 3 1.2-6L3.4 9.1l6-.7Z" />
  </svg>
);

const ArrowRight: IconFC = ({ color, size = 48 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...stroke(color)}>
    <path d="M3 12h17M13 5l7 7-7 7" />
  </svg>
);

const Compare: IconFC = ({ color, size = 48 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...stroke(color)}>
    <path d="M7 3v14M17 7v14" />
    <path d="M3 7h8M13 17h8" />
    <circle cx="7" cy="19" r="1.6" fill={color} />
    <circle cx="17" cy="5" r="1.6" fill={color} />
  </svg>
);

const Clock: IconFC = ({ color, size = 48 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...stroke(color)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5.5l3.5 2" />
  </svg>
);

export const ICONS: Record<string, IconFC> = {
  lightbulb: Lightbulb,
  target: Target,
  book: Book,
  chart_bar: ChartBar,
  chart_line: ChartLine,
  check: Check,
  calculator: Calculator,
  puzzle: Puzzle,
  star: Star,
  arrow_right: ArrowRight,
  compare: Compare,
  clock: Clock,
};

const DEFAULT_ORDER = Object.keys(ICONS);

// Resolves an icon by name from the LLM, falling back to a deterministic
// cycle through the icon set (keyed by bullet index) so older artifacts
// without an `itemIcons` field, or an unrecognized name, still render a
// visual instead of a blank slot.
export function resolveIcon(name: string | undefined, fallbackIndex: number): IconFC {
  if (name && ICONS[name]) return ICONS[name];
  return ICONS[DEFAULT_ORDER[fallbackIndex % DEFAULT_ORDER.length]];
}
