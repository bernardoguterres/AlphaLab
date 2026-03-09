import { useState } from "react";
import type { RiskSettings } from "@/types";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { AlertTriangle } from "lucide-react";

interface RiskSettingsPanelProps {
  settings: RiskSettings;
  onChange: (settings: RiskSettings) => void;
}

export function RiskSettingsPanel({ settings, onChange }: RiskSettingsPanelProps) {
  const updateSetting = <K extends keyof RiskSettings>(key: K, value: RiskSettings[K]) => {
    onChange({ ...settings, [key]: value });
  };

  const showStopLossWarning = settings.stop_loss_pct > settings.take_profit_pct;

  return (
    <Accordion type="single" collapsible className="w-full">
      <AccordionItem value="risk-settings" className="border rounded-lg px-4">
        <AccordionTrigger className="hover:no-underline">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">Risk Settings</span>
            <span className="text-xs text-muted-foreground">(Optional)</span>
          </div>
        </AccordionTrigger>
        <AccordionContent className="pt-4 pb-2">
          <div className="grid grid-cols-2 gap-4">
            {/* Stop Loss */}
            <div className="space-y-1.5">
              <Label htmlFor="stop-loss" className="text-xs">
                Stop Loss %
                <span className="text-muted-foreground ml-1">(0.1 - 50)</span>
              </Label>
              <Input
                id="stop-loss"
                type="number"
                step="0.1"
                min="0.1"
                max="50"
                value={settings.stop_loss_pct}
                onChange={(e) => updateSetting("stop_loss_pct", parseFloat(e.target.value) || 2.0)}
                className="h-8 text-sm"
              />
            </div>

            {/* Take Profit */}
            <div className="space-y-1.5">
              <Label htmlFor="take-profit" className="text-xs">
                Take Profit %
                <span className="text-muted-foreground ml-1">(0.5 - 100)</span>
              </Label>
              <Input
                id="take-profit"
                type="number"
                step="0.5"
                min="0.5"
                max="100"
                value={settings.take_profit_pct}
                onChange={(e) => updateSetting("take_profit_pct", parseFloat(e.target.value) || 5.0)}
                className="h-8 text-sm"
              />
            </div>

            {/* Max Position Size */}
            <div className="space-y-1.5">
              <Label htmlFor="max-position" className="text-xs">
                Max Position Size %
                <span className="text-muted-foreground ml-1">(1 - 100)</span>
              </Label>
              <Input
                id="max-position"
                type="number"
                step="1"
                min="1"
                max="100"
                value={settings.max_position_size_pct}
                onChange={(e) => updateSetting("max_position_size_pct", parseFloat(e.target.value) || 10.0)}
                className="h-8 text-sm"
              />
            </div>

            {/* Max Daily Loss */}
            <div className="space-y-1.5">
              <Label htmlFor="max-daily-loss" className="text-xs">
                Max Daily Loss %
                <span className="text-muted-foreground ml-1">(0.5 - 20)</span>
              </Label>
              <Input
                id="max-daily-loss"
                type="number"
                step="0.5"
                min="0.5"
                max="20"
                value={settings.max_daily_loss_pct}
                onChange={(e) => updateSetting("max_daily_loss_pct", parseFloat(e.target.value) || 3.0)}
                className="h-8 text-sm"
              />
            </div>

            {/* Max Open Positions */}
            <div className="space-y-1.5">
              <Label htmlFor="max-open" className="text-xs">
                Max Open Positions
                <span className="text-muted-foreground ml-1">(1 - 50)</span>
              </Label>
              <Input
                id="max-open"
                type="number"
                step="1"
                min="1"
                max="50"
                value={settings.max_open_positions}
                onChange={(e) => updateSetting("max_open_positions", parseInt(e.target.value) || 5)}
                className="h-8 text-sm"
              />
            </div>

            {/* Commission */}
            <div className="space-y-1.5">
              <Label htmlFor="commission" className="text-xs">
                Commission per Trade ($)
                <span className="text-muted-foreground ml-1">(0 - 50)</span>
              </Label>
              <Input
                id="commission"
                type="number"
                step="0.01"
                min="0"
                max="50"
                value={settings.commission_per_trade}
                onChange={(e) => updateSetting("commission_per_trade", parseFloat(e.target.value) || 0.0)}
                className="h-8 text-sm"
              />
              <p className="text-[10px] text-muted-foreground">
                Alpaca: $0 · Other brokers: $0.65-$5.00
              </p>
            </div>

            {/* Trailing Stop Toggle */}
            <div className="col-span-2 space-y-2 pt-2 border-t">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="trailing-stop"
                  checked={settings.trailing_stop_enabled}
                  onCheckedChange={(checked) => updateSetting("trailing_stop_enabled", !!checked)}
                />
                <Label htmlFor="trailing-stop" className="text-xs font-normal cursor-pointer">
                  Enable Trailing Stop
                </Label>
              </div>

              {settings.trailing_stop_enabled && (
                <div className="space-y-1.5 ml-6">
                  <Label htmlFor="trailing-pct" className="text-xs">
                    Trailing Stop %
                    <span className="text-muted-foreground ml-1">(0.1 - 50)</span>
                  </Label>
                  <Input
                    id="trailing-pct"
                    type="number"
                    step="0.5"
                    min="0.1"
                    max="50"
                    value={settings.trailing_stop_pct}
                    onChange={(e) => updateSetting("trailing_stop_pct", parseFloat(e.target.value) || 3.0)}
                    className="h-8 text-sm max-w-xs"
                  />
                </div>
              )}
            </div>
          </div>

          {/* Warning if stop loss > take profit */}
          {showStopLossWarning && (
            <div className="mt-4 flex items-start gap-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded-md">
              <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
              <div className="text-xs">
                <p className="font-medium text-amber-500">Warning</p>
                <p className="text-muted-foreground mt-0.5">
                  Stop loss ({settings.stop_loss_pct}%) is greater than take profit ({settings.take_profit_pct}%).
                  This is uncommon but valid for some strategies.
                </p>
              </div>
            </div>
          )}

          <div className="mt-4 p-3 bg-muted/50 rounded-md">
            <p className="text-[10px] text-muted-foreground">
              <strong>Note:</strong> Risk settings apply position limits and stop-loss/take-profit levels.
              Commission is applied on both entry and exit (2× per round trip).
              These settings will be included in the exported strategy config.
            </p>
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
