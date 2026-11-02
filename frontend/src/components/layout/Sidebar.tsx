import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useBacktestStore } from "@/stores/backtestStore";

const NAV = [
  { to: "/", label: "Overview" },
  { to: "/backtest", label: "Backtest" },
  { to: "/compare", label: "Compare" },
  { to: "/data", label: "Data" },
  { to: "/settings", label: "Settings" },
];

const STATUS: Record<string, { dot: string; label: string }> = {
  true: { dot: "bg-gain", label: "API connected" },
  false: { dot: "bg-loss", label: "API offline" },
  null: { dot: "bg-muted-foreground", label: "Checking API…" },
};

export function Sidebar() {
  const online = useBacktestStore((s) => s.isBackendOnline);

  return (
    <aside className="flex shrink-0 items-center gap-6 border-b border-border px-4 py-3 md:sticky md:top-0 md:h-screen md:w-44 md:flex-col md:items-stretch md:border-b-0 md:border-r md:px-5 md:py-6">
      <span className="text-[15px] font-medium tracking-tight">AlphaLab</span>

      <nav className="flex gap-4 overflow-x-auto text-[13px] md:mt-6 md:flex-col md:gap-0.5">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end
            className={({ isActive }) =>
              cn(
                "whitespace-nowrap border-b-2 py-1 md:-ml-5 md:border-b-0 md:border-l-2 md:pl-[18px]",
                isActive ? "border-signal text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <p className="ml-auto flex shrink-0 items-center gap-2 text-2xs text-muted-foreground md:ml-0 md:mt-auto">
        <span className={cn("h-1.5 w-1.5 rounded-full", STATUS[String(online)].dot)} aria-hidden />
        <span className="sr-only md:not-sr-only">{STATUS[String(online)].label}</span>
      </p>
    </aside>
  );
}
