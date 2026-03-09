import { NavLink, useLocation } from "react-router-dom";
import { BarChart3, GitCompare, Database, LayoutDashboard, Activity, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { useBacktestStore } from "@/stores/backtestStore";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/backtest", label: "Backtest", icon: BarChart3 },
  { to: "/compare", label: "Compare", icon: GitCompare },
  { to: "/data", label: "Data", icon: Database },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Header() {
  const location = useLocation();
  const isBackendOnline = useBacktestStore((s) => s.isBackendOnline);

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-card/80 backdrop-blur-md">
      <div className="flex h-14 items-center px-6 gap-8">
        <div className="flex items-center gap-2.5">
          <Activity className="h-6 w-6 text-primary" />
          <span className="font-display text-lg font-bold tracking-tight">AlphaLab</span>
        </div>

        <nav className="flex items-center gap-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={cn(
                "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                location.pathname === item.to
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <div
              className={cn(
                "h-2 w-2 rounded-full",
                isBackendOnline ? "bg-gain animate-pulse-gain" : "bg-loss"
              )}
            />
            {isBackendOnline ? "Backend Online" : "Backend Offline"}
          </div>
        </div>
      </div>
    </header>
  );
}
