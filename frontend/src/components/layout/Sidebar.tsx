import { NavLink, useLocation } from "react-router-dom";
import { BarChart3, GitCompare, Database, LayoutDashboard, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { useBacktestStore } from "@/stores/backtestStore";
import alphaLabLogo from "@/assets/alphalab-logo.png";

const navItems = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/backtest", label: "Backtest", icon: BarChart3 },
  { to: "/compare", label: "Compare", icon: GitCompare },
  { to: "/data", label: "Data", icon: Database },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const location = useLocation();
  const isBackendOnline = useBacktestStore((s) => s.isBackendOnline);

  return (
    <aside className="sticky top-0 h-screen shrink-0 w-14 md:w-[200px] border-r border-border/70 bg-card/40 backdrop-blur-xl flex flex-col">
      <div className="flex items-center gap-2.5 px-3 md:px-4 h-16 shrink-0 border-b border-border/50">
        <img src={alphaLabLogo} alt="AlphaLab" className="h-7 w-auto object-contain shrink-0" />
        <div className="hidden md:flex flex-col leading-none min-w-0">
          <span className="text-[14px] font-bold tracking-tight text-foreground truncate">AlphaLab</span>
          <span className="text-[9px] font-medium text-muted-foreground/70 uppercase tracking-widest mt-0.5">
            Research Workspace
          </span>
        </div>
      </div>

      <nav className="flex-1 py-3 px-2 md:px-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const active = location.pathname === item.to;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              title={item.label}
              className={cn(
                "flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm font-medium transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50",
                active
                  ? "bg-primary/12 text-primary border border-primary/25"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary/60 border border-transparent"
              )}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              <span className="hidden md:inline truncate">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="p-2 md:p-3 border-t border-border/50 shrink-0">
        <div
          className={cn(
            "flex items-center gap-2 rounded-lg border px-2.5 py-2 text-[11px] font-semibold",
            isBackendOnline ? "bg-gain/10 text-gain border-gain/30" : "bg-loss/10 text-loss border-loss/30"
          )}
          title={isBackendOnline ? "Backend Online" : "Backend Offline"}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", isBackendOnline ? "bg-gain animate-pulse-gain" : "bg-loss")} />
          <span className="hidden md:inline truncate uppercase tracking-wide">
            {isBackendOnline ? "Backend Online" : "Backend Offline"}
          </span>
        </div>
      </div>
    </aside>
  );
}
