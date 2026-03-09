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
import { Card } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { toast } from "sonner";
import { Loader2, CheckCircle, XCircle, ChevronDown, Save, ExternalLink } from "lucide-react";

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
      <div className="flex items-center justify-center h-[calc(100vh-3.5rem)]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-3.5rem)]">
        <p className="text-muted-foreground">Failed to load settings</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-[calc(100vh-3.5rem)]">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Configure notifications and trading connections for AlphaLive
        </p>
      </div>

      {/* Help Panel */}
      <Collapsible open={helpOpen} onOpenChange={setHelpOpen}>
        <Card className="p-4">
          <CollapsibleTrigger className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold">How to Set Up API Keys</h3>
            </div>
            <ChevronDown
              className={`h-5 w-5 transition-transform ${helpOpen ? "rotate-180" : ""}`}
            />
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-4 space-y-4 text-sm">
            <div>
              <h4 className="font-semibold mb-2">Telegram Bot Setup</h4>
              <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
                <li>Open Telegram and search for <code className="bg-muted px-1 rounded">@BotFather</code></li>
                <li>Send <code className="bg-muted px-1 rounded">/newbot</code> and follow the prompts</li>
                <li>Copy the bot token (format: <code className="bg-muted px-1 rounded">123456:ABC-DEF...</code>)</li>
                <li>Add to your <code className="bg-muted px-1 rounded">.env</code> file:
                  <pre className="bg-muted p-2 rounded mt-1 text-xs">
                    TELEGRAM_BOT_TOKEN=your_token_here
                  </pre>
                </li>
                <li>To get your Chat ID:
                  <ul className="list-disc list-inside ml-4 mt-1">
                    <li>Search for <code className="bg-muted px-1 rounded">@userinfobot</code> on Telegram</li>
                    <li>Start a chat and it will display your Chat ID</li>
                    <li>Add to <code className="bg-muted px-1 rounded">.env</code>:
                      <pre className="bg-muted p-2 rounded mt-1 text-xs">
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
                className="text-blue-600 hover:underline flex items-center gap-1 mt-2"
              >
                Telegram Bot Documentation <ExternalLink className="h-3 w-3" />
              </a>
            </div>

            <div className="border-t pt-4">
              <h4 className="font-semibold mb-2">Alpaca API Setup</h4>
              <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
                <li>Go to <a
                  href="https://alpaca.markets/signup"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  alpaca.markets/signup
                </a></li>
                <li>Create a <strong>Paper Trading</strong> account (free, no real money)</li>
                <li>Navigate to <strong>Your API Keys</strong> in the dashboard</li>
                <li>Generate API keys and copy them</li>
                <li>Add to your <code className="bg-muted px-1 rounded">.env</code> file:
                  <pre className="bg-muted p-2 rounded mt-1 text-xs">
                    ALPACA_API_KEY=your_api_key_here{"\n"}
                    ALPACA_SECRET_KEY=your_secret_key_here
                  </pre>
                </li>
              </ol>
              <a
                href="https://docs.alpaca.markets/docs/getting-started"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline flex items-center gap-1 mt-2"
              >
                Alpaca Getting Started Guide <ExternalLink className="h-3 w-3" />
              </a>
            </div>

            <div className="border-t pt-4">
              <h4 className="font-semibold mb-2">Important Security Notes</h4>
              <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                <li><strong>NEVER commit your .env file to git</strong> — it contains secrets</li>
                <li>API keys are stored as environment variables only (not in the UI or database)</li>
                <li>This Settings page saves only alert toggles and thresholds (non-sensitive)</li>
                <li>Restart the backend after updating .env for changes to take effect</li>
              </ul>
            </div>
          </CollapsibleContent>
        </Card>
      </Collapsible>

      {/* Telegram Settings */}
      <Card className="p-6 space-y-4">
        <div>
          <h2 className="text-xl font-semibold mb-2">Telegram Notifications</h2>
          <p className="text-sm text-muted-foreground">
            Receive real-time alerts for trades, errors, and portfolio events
          </p>
        </div>

        {/* Bot Token Status */}
        <div className="flex items-center gap-2 p-3 bg-muted rounded-lg">
          {settings.telegram ? (
            <>
              <CheckCircle className="h-5 w-5 text-green-600" />
              <span className="text-sm font-medium">TELEGRAM_BOT_TOKEN configured</span>
            </>
          ) : (
            <>
              <XCircle className="h-5 w-5 text-red-600" />
              <span className="text-sm font-medium">
                TELEGRAM_BOT_TOKEN not set — add to your .env file
              </span>
            </>
          )}
        </div>

        {/* Enable Toggle */}
        <div className="flex items-center justify-between">
          <div>
            <Label>Enable Telegram Notifications</Label>
            <p className="text-sm text-muted-foreground">
              Turn on to receive alerts via Telegram
            </p>
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

        {/* Alert Toggles */}
        {settings.telegram.enabled && (
          <div className="space-y-3 pl-4 border-l-2">
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
      </Card>

      {/* Alpaca Settings */}
      <Card className="p-6 space-y-4">
        <div>
          <h2 className="text-xl font-semibold mb-2">Alpaca Trading</h2>
          <p className="text-sm text-muted-foreground">
            Configure connection to Alpaca for live trading
          </p>
        </div>

        {/* API Key Status */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 p-3 bg-muted rounded-lg">
            {settings.alpaca.api_key_configured ? (
              <>
                <CheckCircle className="h-5 w-5 text-green-600" />
                <span className="text-sm font-medium">ALPACA_API_KEY configured</span>
              </>
            ) : (
              <>
                <XCircle className="h-5 w-5 text-red-600" />
                <span className="text-sm font-medium">
                  ALPACA_API_KEY not set — add to your .env file
                </span>
              </>
            )}
          </div>

          <div className="flex items-center gap-2 p-3 bg-muted rounded-lg">
            {settings.alpaca.secret_key_configured ? (
              <>
                <CheckCircle className="h-5 w-5 text-green-600" />
                <span className="text-sm font-medium">ALPACA_SECRET_KEY configured</span>
              </>
            ) : (
              <>
                <XCircle className="h-5 w-5 text-red-600" />
                <span className="text-sm font-medium">
                  ALPACA_SECRET_KEY not set — add to your .env file
                </span>
              </>
            )}
          </div>
        </div>

        {/* Paper Trading Toggle */}
        <div className="flex items-center justify-between">
          <div>
            <Label>Paper Trading Mode</Label>
            <p className="text-sm text-muted-foreground">
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
          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
            <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
              ⚠️ Live trading mode enabled
            </p>
            <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-1">
              Real money will be used. Ensure you have tested thoroughly in paper trading mode first.
            </p>
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
      </Card>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              Save Settings
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
