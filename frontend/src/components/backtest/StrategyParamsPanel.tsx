import type { StrategyParams, StrategyType } from "@/types";
import { Checkbox } from "@/components/ui/checkbox";
import { Disclosure } from "@/components/ui/disclosure";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { STRATEGIES, paramSummary } from "@/utils/strategies";

interface StrategyParamsPanelProps {
  strategy: StrategyType;
  params: StrategyParams;
  onChange: (key: string, value: number | boolean) => void;
}

/** The parameter form for any strategy, generated from its registry entry. */
export function StrategyParamsPanel({ strategy, params, onChange }: StrategyParamsPanelProps) {
  const values = params as unknown as Record<string, number | boolean>;
  const visible = STRATEGIES[strategy].params.filter((p) => !p.shownWhen || values[p.shownWhen]);

  return (
    <Disclosure title="Strategy parameters" summary={paramSummary(strategy, params)}>
      <div className="grid max-w-3xl gap-x-10 gap-y-4 sm:grid-cols-2">
        {visible.map((p) => {
          const id = `param-${p.key}`;
          if (p.kind === "boolean") {
            return (
              <div key={p.key} className="flex items-center gap-2">
                <Checkbox id={id} checked={values[p.key] as boolean} onCheckedChange={(v) => onChange(p.key, v === true)} />
                <Label htmlFor={id} className="text-[13px] font-normal">
                  {p.label}
                </Label>
              </div>
            );
          }
          return (
            <div key={p.key}>
              <div className="mb-2 flex items-baseline justify-between text-[13px]">
                <Label htmlFor={id} className="font-normal text-muted-foreground">
                  {p.label}
                </Label>
                <span className="num">{values[p.key] as number}</span>
              </div>
              <Slider
                id={id}
                value={[values[p.key] as number]}
                onValueChange={([v]) => onChange(p.key, v)}
                min={p.min}
                max={p.max}
                step={p.step}
              />
            </div>
          );
        })}
      </div>
    </Disclosure>
  );
}
