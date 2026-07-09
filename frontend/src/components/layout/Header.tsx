import { NavLink, useLocation } from "react-router-dom";
import { BarChart3, GitCompare, Database, LayoutDashboard, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { useBacktestStore } from "@/stores/backtestStore";
import { StatusBadge } from "@/components/ui/status-badge";
import alphaLabLogo from "@/assets/alphalab-logo.png";

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
    <header className="sticky top-0 z-50 border-b border-border/80 bg-background/90 backdrop-blur-xl shadow-[0_1px_0_hsl(var(--foreground)/0.04),0_8px_24px_-16px_hsl(var(--background)/0.9)]">
      <div className="w-full flex h-16 items-center px-4 sm:px-6 lg:px-10 xl:px-14 gap-3 md:gap-6">
        <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
          <div className="relative shrink-0">
            <img src={alphaLabLogo} alt="AlphaLab" className="h-7 sm:h-8 w-auto object-contain relative z-10" />
            <div className="absolute inset-0 blur-lg bg-primary/25 -z-0" />
          </div>
          <div className="flex flex-col leading-none">
            <span className="font-display text-[15px] font-bold tracking-tight gradient-text">AlphaLab</span>
            <span className="hidden md:block text-[9px] font-medium text-muted-foreground/70 uppercase tracking-widest mt-0.5">
              Research Workspace
            </span>
          </div>
        </div>

        <div className="hidden md:block h-6 w-px bg-border shrink-0" />

        <nav className="flex items-center gap-0.5 sm:gap-1 overflow-x-auto no-scrollbar">
          {navItems.map((item) => {
            const active = location.pathname === item.to;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={cn(
                  "relative flex items-center gap-2 px-2.5 sm:px-3 py-1.5 rounded-lg text-sm font-medium transition-all shrink-0",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                  active
                    ? "bg-primary/12 text-primary shadow-[0_0_0_1px_hsl(var(--primary)/0.25)]"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span className="hidden lg:inline">{item.label}</span>
                {active && (
                  <span className="absolute -bottom-[1px] left-2 right-2 h-[2px] rounded-full bg-gradient-to-r from-primary to-lab-secondary" />
                )}
              </NavLink>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-3 shrink-0">
          <StatusBadge
            label={isBackendOnline ? "Backend Online" : "Backend Offline"}
            tone={isBackendOnline ? "gain" : "loss"}
            dot
            pulse={isBackendOnline}
            className="hidden sm:inline-flex normal-case tracking-normal font-medium"
          />
          <span
            className={cn(
              "sm:hidden h-2.5 w-2.5 rounded-full shrink-0",
              isBackendOnline ? "bg-gain animate-pulse-gain" : "bg-loss"
            )}
          />
        </div>
      </div>
    </header>
  );
}
