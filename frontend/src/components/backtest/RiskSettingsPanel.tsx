import type { RiskSettings } from "@/types";
import { Checkbox } from "@/components/ui/checkbox";
import { Disclosure } from "@/components/ui/disclosure";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { riskSummary } from "@/utils/runSettings";

type NumericSetting = Exclude<keyof RiskSettings, "trailing_stop_enabled">;

const FIELDS: { key: NumericSetting; label: string; min: number; max: number; step: number; hint?: string }[] = [
  { key: "stop_loss_pct", label: "Stop loss %", min: 0.1, max: 50, step: 0.1 },
  { key: "take_profit_pct", label: "Take profit %", min: 0.5, max: 100, step: 0.5 },
  { key: "max_position_size_pct", label: "Max position size %", min: 1, max: 100, step: 1 },
  { key: "max_daily_loss_pct", label: "Max daily loss %", min: 0.5, max: 20, step: 0.5 },
  { key: "max_open_positions", label: "Max open positions", min: 1, max: 50, step: 1 },
  { key: "commission_per_trade", label: "Commission per trade ($)", min: 0, max: 50, step: 0.01, hint: "Charged on entry and exit." },
];

interface RiskSettingsPanelProps {
  settings: RiskSettings;
  onChange: (settings: RiskSettings) => void;
}

export function RiskSettingsPanel({ settings, onChange }: RiskSettingsPanelProps) {
  const update = <K extends keyof RiskSettings>(key: K, value: RiskSettings[K]) => onChange({ ...settings, [key]: value });

  // An empty or invalid box keeps the previous value rather than sending NaN.
  const numberInput = (key: NumericSetting, min: number, max: number, step: number) => (
    <Input
      id={`risk-${key}`}
      type="number"
      className="num"
      min={min}
      max={max}
      step={step}
      value={settings[key]}
      onChange={(e) => {
        const value = e.target.valueAsNumber;
        if (!Number.isNaN(value)) update(key, value);
      }}
    />
  );

  return (
    <Disclosure title="Risk settings" summary={riskSummary(settings)}>
      <div className="grid max-w-3xl gap-x-6 gap-y-4 sm:grid-cols-3">
        {FIELDS.map((f) => (
          <Field key={f.key} label={f.label} htmlFor={`risk-${f.key}`} hint={f.hint}>
            {numberInput(f.key, f.min, f.max, f.step)}
          </Field>
        ))}
        <div className="flex items-center gap-2 self-end pb-2">
          <Checkbox
            id="risk-trailing"
            checked={settings.trailing_stop_enabled}
            onCheckedChange={(v) => update("trailing_stop_enabled", v === true)}
          />
          <Label htmlFor="risk-trailing" className="text-[13px] font-normal">
            Trailing stop
          </Label>
        </div>
        {settings.trailing_stop_enabled && (
          <Field label="Trailing stop %" htmlFor="risk-trailing_stop_pct">
            {numberInput("trailing_stop_pct", 0.1, 50, 0.5)}
          </Field>
        )}
      </div>
      {settings.stop_loss_pct > settings.take_profit_pct && (
        <Notice tone="warning" title="Stop loss is wider than take profit" className="mt-4">
          Unusual, but valid for some strategies.
        </Notice>
      )}
      <p className="mt-4 text-2xs text-muted-foreground">These settings are included in an AlphaLive export.</p>
    </Disclosure>
  );
}
