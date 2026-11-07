import type { PositionSizing, StrategyType } from "@/types";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { INTERVALS, SIZINGS } from "@/utils/defaults";
import { STRATEGIES, STRATEGY_TYPES } from "@/utils/strategies";

/** Form fields that Backtest, Compare and Batch all ask for. */

export function StrategyField({ value, onChange }: { value: StrategyType; onChange: (value: StrategyType) => void }) {
  return (
    <Field label="Strategy" htmlFor="strategy" hint={STRATEGIES[value].category}>
      <Select value={value} onValueChange={(v) => onChange(v as StrategyType)}>
        <SelectTrigger id="strategy">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {STRATEGY_TYPES.map((id) => (
            <SelectItem key={id} value={id}>
              {STRATEGIES[id].name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
}

export function TickerField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <Field label="Ticker" htmlFor="ticker">
      <Input id="ticker" className="num uppercase" value={value} onChange={(e) => onChange(e.target.value.toUpperCase())} />
    </Field>
  );
}

export function CapitalField({ value, onChange }: { value: number; onChange: (value: number) => void }) {
  return (
    <Field label="Starting capital" htmlFor="capital">
      <Input
        id="capital"
        type="number"
        min={1000}
        step={1000}
        className="num"
        value={value}
        onChange={(e) => onChange(e.target.valueAsNumber || 0)}
      />
    </Field>
  );
}

interface DateRangeFieldsProps {
  start: string;
  end: string;
  onStartChange: (value: string) => void;
  onEndChange: (value: string) => void;
}

export function DateRangeFields({ start, end, onStartChange, onEndChange }: DateRangeFieldsProps) {
  return (
    <>
      <Field label="From" htmlFor="start-date">
        <Input id="start-date" type="date" className="num" value={start} onChange={(e) => onStartChange(e.target.value)} />
      </Field>
      <Field label="To" htmlFor="end-date">
        <Input id="end-date" type="date" className="num" value={end} onChange={(e) => onEndChange(e.target.value)} />
      </Field>
    </>
  );
}

interface IntervalSelectProps {
  value: string;
  onChange: (value: string) => void;
  id?: string;
  className?: string;
}

export function IntervalSelect({ value, onChange, id, className }: IntervalSelectProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger id={id} aria-label={id ? undefined : "Bar interval"} className={className}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {INTERVALS.map((i) => (
          <SelectItem key={i.value} value={i.value}>
            {i.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function SizingField({ value, onChange }: { value: PositionSizing; onChange: (value: PositionSizing) => void }) {
  return (
    <Field label="Sizing" htmlFor="sizing">
      <Select value={value} onValueChange={(v) => onChange(v as PositionSizing)}>
        <SelectTrigger id="sizing">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {SIZINGS.map((s) => (
            <SelectItem key={s.value} value={s.value}>
              {s.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
}

export function DrawdownHaltField({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <div className="flex items-center gap-2">
      <Checkbox id="drawdown-halt" checked={checked} onCheckedChange={(v) => onChange(v === true)} />
      <Label htmlFor="drawdown-halt" className="text-[13px] font-normal">
        Halt new entries after a 10% drawdown
      </Label>
      <span className="text-2xs text-muted-foreground">(not exportable)</span>
    </div>
  );
}
