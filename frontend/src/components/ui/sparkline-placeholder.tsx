interface SparklinePlaceholderProps {
  data: number[];
  className?: string;
  strokeClassName?: string;
  fill?: boolean;
  height?: number;
}

// Lightweight inline SVG line chart — no charting library dependency.
// Renders whatever numeric series it's given (real equity curve values,
// derived stats, etc). Callers are responsible for only passing real data.
export function SparklinePlaceholder({
  data,
  className,
  strokeClassName = "text-primary",
  fill = true,
  height = 56,
}: SparklinePlaceholderProps) {
  const w = 200;
  const h = height;

  if (data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 6) - 3;
    return [x, y];
  });

  const linePath = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L${w},${h} L0,${h} Z`;
  const gradId = `spk-${strokeClassName.replace(/[^a-z0-9]/gi, "")}`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={className} preserveAspectRatio="none">
      {fill && (
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.35" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>
      )}
      {fill && <path d={areaPath} fill={`url(#${gradId})`} className={strokeClassName} />}
      <path d={linePath} fill="none" stroke="currentColor" strokeWidth={1.75} className={strokeClassName} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
