import { useState, useEffect } from "react";
import {
  getNotificationSettings,
  saveNotificationSettings,
  testTelegramConnection,
  testAlpacaConnection,
} from "@/services/api";
import type { NotificationSettings } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { StatusBadge } from "@/components/ui/status-badge";
import { toast } from "sonner";
import {
  Loader2, ChevronDown, Save, ExternalLink, Send, LineChart, ShieldAlert, Info, ShieldCheck, KeyRound,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function Settings() {
  const [settings, setSettings] = useState<NotificationSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState({ telegram: false, alpaca: false });
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setIsLoading(true);
    try {
      const response = await getNotificationSettings();
      setSettings(response.data);
    } catch (err: any) {
      toast.error(err.message || "Failed to load settings");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    if (!settings) return;

    setIsSaving(true);
    try {
      await saveNotificationSettings(settings);
      toast.success("Settings saved successfully!");
    } catch (err: any) {
      toast.error(err.message || "Failed to save settings");
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestTelegram = async () => {
    setIsTesting({ ...isTesting, telegram: true });
    try {
      const response = await testTelegramConnection();
      toast.success(response.message || "Test message sent successfully!");
    } catch (err: any) {
      toast.error(err.message || "Telegram test failed");
    } finally {
      setIsTesting({ ...isTesting, telegram: false });
    }
  };

  const handleTestAlpaca = async () => {
    setIsTesting({ ...isTesting, alpaca: true });
    try {
      const response = await testAlpacaConnection();
      if (response.data) {
        toast.success(
          `Connection successful! Account: ${response.data.account_number}, ` +
          `Status: ${response.data.status}, ` +
          `Buying Power: $${response.data.buying_power?.toFixed(2)}`
        );
      } else {
        toast.success(response.message || "Connection successful!");
      }
    } catch (err: any) {
      toast.error(err.message || "Alpaca test failed");
    } finally {
      setIsTesting({ ...isTesting, alpaca: false });
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <p className="text-muted-foreground">Failed to load settings</p>
      </div>
    );
  }

  // How many of the 2 known Alpaca credential flags are actually configured — real, derived.
  const alpacaKeysConfigured = [settings.alpaca.api_key_configured, settings.alpaca.secret_key_configured].filter(Boolean).length;

  return (
    <div className="h-[calc(100vh-4rem)] overflow-y-auto">
      <div className="page-shell py-8 space-y-6 animate-in-stagger">
        {/* Page header / command strip */}
        <div className="hero-panel px-6 py-6 sm:px-8 sm:py-7">
          <div className="glow-blob h-36 w-36 -bottom-14 right-1/4 opacity-20 bg-lab-secondary" />
          <div className="flex items-start justify-between flex-wrap gap-5 relative">
            <div className="max-w-2xl">
              <div className="flex items-center gap-2 mb-2.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-60" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
                </span>
                <span className="text-[11px] font-semibold text-primary uppercase tracking-widest">Operations Settings</span>
              </div>
              <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight gradient-text leading-tight">
                Settings
              </h1>
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                Notifications, broker connections, and execution safety for AlphaLive.
              </p>
              <div className="flex items-center gap-2 mt-4 flex-wrap">
                <StatusBadge
                  label={settings.telegram.enabled ? "Telegram Enabled" : "Telegram Disabled"}
                  tone={settings.telegram.enabled ? "gain" : "neutral"}
                  dot
                  className="normal-case tracking-normal"
                />
                <StatusBadge
                  label={settings.alpaca.paper_trading ? "Paper Trading" : "Live Trading"}
                  tone={settings.alpaca.paper_trading ? "gain" : "loss"}
                  dot
                  pulse={!settings.alpaca.paper_trading}
                  className="normal-case tracking-normal"
                />
                <StatusBadge
                  label={`${alpacaKeysConfigured}/2 Alpaca keys configured`}
                  tone={alpacaKeysConfigured === 2 ? "gain" : alpacaKeysConfigured === 1 ? "warning" : "neutral"}
                  className="normal-case tracking-normal"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Help Panel */}
        <Collapsible open={helpOpen} onOpenChange={setHelpOpen}>
          <div className="card-elevated p-4">
            <CollapsibleTrigger className="flex items-center justify-between w-full">
              <div className="flex items-center gap-2">
                <Info className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold">How to Set Up API Keys</h3>
              </div>
              <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", helpOpen && "rotate-180")} />
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-4 space-y-4 text-sm">
              <div>
                <h4 className="section-label mb-2">Telegram Bot Setup</h4>
                <ol className="list-decimal list-inside space-y-1 text-muted-foreground text-xs">
                  <li>Open Telegram and search for <code className="bg-secondary px-1 rounded">@BotFather</code></li>
                  <li>Send <code className="bg-secondary px-1 rounded">/newbot</code> and follow the prompts</li>
                  <li>Copy the bot token (format: <code className="bg-secondary px-1 rounded">123456:ABC-DEF...</code>)</li>
                  <li>Add to your <code className="bg-secondary px-1 rounded">.env</code> file:
                    <pre className="bg-secondary p-2 rounded mt-1 text-[11px] font-mono-numbers">
                      TELEGRAM_BOT_TOKEN=your_token_here
                    </pre>
                  </li>
                  <li>To get your Chat ID:
                    <ul className="list-disc list-inside ml-4 mt-1">
                      <li>Search for <code className="bg-secondary px-1 rounded">@userinfobot</code> on Telegram</li>
                      <li>Start a chat and it will display your Chat ID</li>
                      <li>Add to <code className="bg-secondary px-1 rounded">.env</code>:
                        <pre className="bg-secondary p-2 rounded mt-1 text-[11px] font-mono-numbers">
                          TELEGRAM_CHAT_ID=your_chat_id_here
                        </pre>
                      </li>
                    </ul>
                  </li>
                </ol>
                <a
                  href="https://core.telegram.org/bots#6-botfather"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline flex items-center gap-1 mt-2 text-xs"
                >
                  Telegram Bot Documentation <ExternalLink className="h-3 w-3" />
                </a>
              </div>

              <div className="divider-fade" />

              <div>
                <h4 className="section-label mb-2">Alpaca API Setup</h4>
                <ol className="list-decimal list-inside space-y-1 text-muted-foreground text-xs">
                  <li>Go to <a
                    href="https://alpaca.markets/signup"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    alpaca.markets/signup
                  </a></li>
                  <li>Create a <strong className="text-foreground">Paper Trading</strong> account (free, no real money)</li>
                  <li>Navigate to <strong className="text-foreground">Your API Keys</strong> in the dashboard</li>
                  <li>Generate API keys and copy them</li>
                  <li>Add to your <code className="bg-secondary px-1 rounded">.env</code> file:
                    <pre className="bg-secondary p-2 rounded mt-1 text-[11px] font-mono-numbers">
                      ALPACA_API_KEY=your_api_key_here{"\n"}
                      ALPACA_SECRET_KEY=your_secret_key_here
                    </pre>
                  </li>
                </ol>
                <a
                  href="https://docs.alpaca.markets/docs/getting-started"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline flex items-center gap-1 mt-2 text-xs"
                >
                  Alpaca Getting Started Guide <ExternalLink className="h-3 w-3" />
                </a>
              </div>

              <div className="divider-fade" />

              <div className="flex items-start gap-2.5 rounded-lg border border-warning/30 bg-warning/[0.06] p-3">
                <ShieldAlert className="h-4 w-4 text-warning shrink-0 mt-0.5" />
                <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs">
                  <li><strong className="text-foreground">Never commit your .env file to git</strong> — it contains secrets</li>
                  <li>API keys are stored as environment variables only (not in the UI or database)</li>
                  <li>This page saves only alert toggles and thresholds (non-sensitive)</li>
                  <li>Restart the backend after updating .env for changes to take effect</li>
                </ul>
              </div>
            </CollapsibleContent>
          </div>
        </Collapsible>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 items-start">
          {/* Telegram Settings */}
          <div className="card-elevated p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="rounded-lg bg-gradient-to-br from-primary to-lab-deep p-2 shadow-lg">
                  <Send className="h-4 w-4 text-white" />
                </div>
                <div>
                  <h2 className="text-[15px] font-bold tracking-tight">Telegram Notifications</h2>
                  <p className="text-xs text-muted-foreground">Real-time alerts for trades, errors, and portfolio events</p>
                </div>
              </div>
              <Switch
                checked={settings.telegram.enabled}
                onCheckedChange={(enabled) =>
                  setSettings({
                    ...settings,
                    telegram: { ...settings.telegram, enabled },
                  })
                }
              />
            </div>

            {/* Bot Token Status — honest: the backend doesn't currently expose whether
                TELEGRAM_BOT_TOKEN is actually set, so we don't assert a configured/not-configured
                state we can't verify. Use "Test Telegram Connection" below for ground truth. */}
            <div className="flex items-center gap-2 p-3 bg-secondary/40 rounded-lg border border-border/60">
              <StatusBadge label="Configuration unverified — use Test Connection below" tone="neutral" dot className="normal-case tracking-normal" />
            </div>

            {/* Alert Toggles */}
            {settings.telegram.enabled && (
              <div className="space-y-3 pl-4 border-l-2 border-border">
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Trade Executions</Label>
                  <Switch
                    checked={settings.telegram.alert_trades}
                    onCheckedChange={(alert_trades) =>
                      setSettings({
                        ...settings,
                        telegram: { ...settings.telegram, alert_trades },
                      })
                    }
                  />
                </div>

                <div className="flex items-center justify-between">
                  <Label className="text-sm">Daily Portfolio Summary</Label>
                  <Switch
                    checked={settings.telegram.alert_daily_summary}
                    onCheckedChange={(alert_daily_summary) =>
                      setSettings({
                        ...settings,
                        telegram: { ...settings.telegram, alert_daily_summary },
                      })
                    }
                  />
                </div>

                <div className="flex items-center justify-between">
                  <Label className="text-sm">Error Alerts</Label>
                  <Switch
                    checked={settings.telegram.alert_errors}
                    onCheckedChange={(alert_errors) =>
                      setSettings({
                        ...settings,
                        telegram: { ...settings.telegram, alert_errors },
                      })
                    }
                  />
                </div>

                <div className="flex items-center justify-between">
                  <Label className="text-sm">Drawdown Warnings</Label>
                  <Switch
                    checked={settings.telegram.alert_drawdown}
                    onCheckedChange={(alert_drawdown) =>
                      setSettings({
                        ...settings,
                        telegram: { ...settings.telegram, alert_drawdown },
                      })
                    }
                  />
                </div>

                {settings.telegram.alert_drawdown && (
                  <div className="pl-4 space-y-2">
                    <Label className="text-sm">Drawdown Warning Threshold (%)</Label>
                    <Input
                      type="number"
                      min={0.1}
                      max={50}
                      step={0.5}
                      value={settings.telegram.drawdown_threshold_pct}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          telegram: {
                            ...settings.telegram,
                            drawdown_threshold_pct: parseFloat(e.target.value) || 5.0,
                          },
                        })
                      }
                    />
                    <p className="text-xs text-muted-foreground">
                      Alert when portfolio drawdown exceeds this percentage
                    </p>
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <Label className="text-sm">Strategy Signal Alerts</Label>
                  <Switch
                    checked={settings.telegram.alert_signals}
                    onCheckedChange={(alert_signals) =>
                      setSettings({
                        ...settings,
                        telegram: { ...settings.telegram, alert_signals },
                      })
                    }
                  />
                </div>
              </div>
            )}

            {/* Test Button */}
            <Button
              onClick={handleTestTelegram}
              disabled={isTesting.telegram}
              variant="outline"
              className="w-full"
            >
              {isTesting.telegram ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Testing...
                </>
              ) : (
                "Test Telegram Connection"
              )}
            </Button>
          </div>

          {/* Alpaca Settings */}
          <div className="card-elevated p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="rounded-lg bg-gradient-to-br from-lab-secondary to-primary p-2 shadow-lg">
                  <LineChart className="h-4 w-4 text-white" />
                </div>
                <div>
                  <h2 className="text-[15px] font-bold tracking-tight">Alpaca Trading</h2>
                  <p className="text-xs text-muted-foreground">Connection to Alpaca for live/paper trading execution</p>
                </div>
              </div>
              <StatusBadge
                label={settings.alpaca.paper_trading ? "Paper" : "Live"}
                tone={settings.alpaca.paper_trading ? "gain" : "loss"}
                dot
                pulse={!settings.alpaca.paper_trading}
              />
            </div>

            {/* API Key Status */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <div className="flex items-center gap-2 p-3 bg-secondary/40 rounded-lg border border-border/60">
                {settings.alpaca.api_key_configured ? (
                  <StatusBadge label="API key set" tone="gain" dot className="normal-case" />
                ) : (
                  <StatusBadge label="API key missing" tone="loss" dot className="normal-case" />
                )}
              </div>

              <div className="flex items-center gap-2 p-3 bg-secondary/40 rounded-lg border border-border/60">
                {settings.alpaca.secret_key_configured ? (
                  <StatusBadge label="Secret key set" tone="gain" dot className="normal-case" />
                ) : (
                  <StatusBadge label="Secret key missing" tone="loss" dot className="normal-case" />
                )}
              </div>
            </div>

            {/* Paper Trading Toggle */}
            <div className="flex items-center justify-between pt-1">
              <div>
                <Label>Paper Trading Mode</Label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Use Alpaca paper trading account (recommended for testing)
                </p>
              </div>
              <Switch
                checked={settings.alpaca.paper_trading}
                onCheckedChange={(paper_trading) =>
                  setSettings({
                    ...settings,
                    alpaca: { ...settings.alpaca, paper_trading },
                  })
                }
              />
            </div>

            {!settings.alpaca.paper_trading && (
              <div className="flex items-start gap-2.5 rounded-lg border-2 border-loss/40 bg-loss/[0.08] p-3.5">
                <ShieldAlert className="h-5 w-5 text-loss shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-bold text-loss">Live trading mode enabled</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Real money will be used. Ensure you have tested thoroughly in paper trading mode first.
                  </p>
                </div>
              </div>
            )}

            {/* Test Button */}
            <Button
              onClick={handleTestAlpaca}
              disabled={isTesting.alpaca}
              variant="outline"
              className="w-full"
            >
              {isTesting.alpaca ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Testing...
                </>
              ) : (
                "Test Alpaca Connection"
              )}
            </Button>
          </div>
        </div>

        {/* Safety / execution risk module — presentation only, no logic change */}
        <div
          className={cn(
            "card-elevated p-5",
            !settings.alpaca.paper_trading && "border-loss/40 bg-loss/[0.03]"
          )}
        >
          <div className="flex items-center gap-2.5 mb-4">
            <div className={cn("rounded-lg p-2", !settings.alpaca.paper_trading ? "bg-loss/15 text-loss" : "bg-gain/15 text-gain")}>
              <ShieldCheck className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-[15px] font-bold tracking-tight">Execution Safety</h2>
              <p className="text-xs text-muted-foreground">Current risk posture for live order execution</p>
            </div>
            <StatusBadge
              label={settings.alpaca.paper_trading ? "Safe — Paper Mode" : "At Risk — Live Mode"}
              tone={settings.alpaca.paper_trading ? "gain" : "loss"}
              dot
              pulse={!settings.alpaca.paper_trading}
              className="normal-case tracking-normal ml-auto"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="flex items-start gap-2.5 rounded-lg border border-border/50 bg-secondary/20 p-3">
              <KeyRound className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-semibold">Credentials</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  {alpacaKeysConfigured}/2 Alpaca env vars configured. Secrets never touch the UI or database.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-2.5 rounded-lg border border-border/50 bg-secondary/20 p-3">
              <ShieldAlert className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-semibold">Before going live</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Validate walk-forward Sharpe &gt; 0.8 in paper mode before flipping this switch.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-2.5 rounded-lg border border-border/50 bg-secondary/20 p-3">
              <Info className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-semibold">Applying changes</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Restart the AlphaLive backend after updating any .env credential.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Save footer — sticky within the scroll container */}
        <div className="sticky bottom-0 -mx-4 sm:-mx-6 lg:-mx-10 xl:-mx-14 mt-2">
          <div className="bg-background/90 backdrop-blur-md border-t border-border px-4 sm:px-6 lg:px-10 xl:px-14 py-3.5 flex justify-end">
            <Button onClick={handleSave} disabled={isSaving} size="lg" className="gap-2">
              {isSaving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  Save Settings
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
