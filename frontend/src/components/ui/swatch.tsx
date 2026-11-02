/** A short line in a chart series colour, for legends and table rows. */
export function Swatch({ color }: { color: string }) {
  return <span className="mr-1.5 inline-block h-0.5 w-3 align-middle" style={{ backgroundColor: color }} aria-hidden />;
}
