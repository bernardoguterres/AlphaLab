import { useEffect, useState } from "react";
import { toast } from "sonner";
import type { HeatmapResponse, ParameterOptimizeResponse, ParameterOptimizeResult, StrategyType, WalkForwardResult } from "@/types";
import { Button } from "@/components/ui/button";
import { Table, Td, Th } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { KeyValue, KeyValueList } from "@/components/ui/key-value";
import { Label } from "@/components/ui/label";
import { Section } from "@/components/ui/section";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Stat, StatGrid } from "@/components/ui/stat";
import { Switch } from "@/components/ui/switch";
import { errorMessage, generateHeatmap, optimizeParameters } from "@/services/api";
import { downloadJson, isoDate } from "@/utils/download";
import { formatNumber, formatPercent, pnlColor } from "@/utils/formatters";
import { STRATEGIES, optimizeRanges, paramLabel } from "@/utils/strategies";

type Target = "sharpe_ratio" | "total_return_pct" | "max_drawdown_pct" | "win_rate";
type Range = { min: number; max: number; step: number };
type OptimizeData = ParameterOptimizeResponse["data"];

const TARGETS: { value: Target; label: string }[] = [
  { value: "sharpe_ratio", label: "Sharpe ratio" },
  { value: "total_return_pct", label: "Total return" },
  { value: "max_drawdown_pct", label: "Max drawdown (smaller is better)" },
  { value: "win_rate", label: "Win rate" },
];

/** Every value from min to max in `step` increments; callers check step > 0 first. */
function gridValues({ min, max, step }: Range): number[] {
  const values: number[] = [];
  for (let v = min; v <= max; v += step) values.push(v);
  return values;
}

/** The heatmap starts on the first two swept parameters. */
function defaultAxes(ranges: Record<string, Range>): [string, string] {
  const [x, y = x] = Object.keys(ranges);
  return [x, y];
}

/** The first parameter whose step would make the grid loop forever. */
function invalidStep(ranges: Record<string, Range>, keys = Object.keys(ranges)): string | undefined {
  return keys.find((k) => !(ranges[k]?.step > 0));
}

interface ParameterOptimizeProps {
  ticker: string;
  strategy: StrategyType;
  startDate: string;
  endDate: string;
  initialCapital: number;
  onApplyParams: (params: Record<string, number>) => void;
}

export default function ParameterOptimize({ ticker, strategy, startDate, endDate, initialCapital, onApplyParams }: ParameterOptimizeProps) {
  const [target, setTarget] = useState<Target>("sharpe_ratio");
  const [walkForward, setWalkForward] = useState(false);
  const [folds, setFolds] = useState(5);
  const [ranges, setRanges] = useState(() => optimizeRanges(strategy));
  const [axes, setAxes] = useState(() => defaultAxes(ranges));
  const [optimizing, setOptimizing] = useState(false);
  const [mapping, setMapping] = useState(false);
  const [result, setResult] = useState<OptimizeData | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapResponse["data"] | null>(null);

  // Each strategy sweeps different parameters, so start over when it changes.
  useEffect(() => {
    const next = optimizeRanges(strategy);
    setRanges(next);
    setAxes(defaultAxes(next));
    setResult(null);
    setHeatmap(null);
  }, [strategy]);

  const keys = Object.keys(ranges);
  const label = (key: string) => paramLabel(strategy, key);
  const updateRange = (key: string, field: keyof Range, value: number) =>
    setRanges((r) => ({ ...r, [key]: { ...r[key], [field]: value } }));

  const handleOptimize = async () => {
    const bad = invalidStep(ranges);
    if (bad) {
      toast.error(`${label(bad)}: step must be greater than 0`);
      return;
    }
    setOptimizing(true);
    try {
      const response = await optimizeParameters({
        ticker,
        strategy,
        start_date: startDate,
        end_date: endDate,
        param_grid: Object.fromEntries(keys.map((k) => [k, gridValues(ranges[k])])),
        initial_capital: initialCapital,
        optimization_target: target,
        walk_forward: walkForward,
        n_folds: folds,
      });
      setResult(response.data);
    } catch (error) {
      toast.error(errorMessage(error, "Optimization failed"));
    } finally {
      setOptimizing(false);
    }
  };

  const handleHeatmap = async () => {
    const [x, y] = axes;
    const bad = invalidStep(ranges, axes);
    if (bad) {
      toast.error(`${label(bad)}: step must be greater than 0`);
      return;
    }
    setMapping(true);
    try {
      const response = await generateHeatmap({
        ticker,
        strategy,
        start_date: startDate,
        end_date: endDate,
        param1_name: x,
        param1_min: ranges[x].min,
        param1_max: ranges[x].max,
        param1_step: ranges[x].step,
        param2_name: y,
        param2_min: ranges[y].min,
        param2_max: ranges[y].max,
        param2_step: ranges[y].step,
        // Parameters off the two axes are held at the bottom of their range.
        fixed_params: Object.fromEntries(keys.filter((k) => k !== x && k !== y).map((k) => [k, ranges[k].min])),
        initial_capital: initialCapital,
      });
      setHeatmap(response.data);
    } catch (error) {
      toast.error(errorMessage(error, "Heatmap failed"));
    } finally {
      setMapping(false);
    }
  };

  return (
    <div className="space-y-10">
      <p className="text-[13px] text-muted-foreground">
        Grid search over {STRATEGIES[strategy].name} on <span className="num text-foreground">{ticker}</span>, {startDate} to {endDate}. Ticker,
        strategy and window come from the Single run tab.
      </p>

      <div className="grid gap-10 lg:grid-cols-2">
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Optimize for" htmlFor="opt-target">
              <Select value={target} onValueChange={(v) => setTarget(v as Target)}>
                <SelectTrigger id="opt-target">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TARGETS.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            {walkForward && (
              <Field label="Folds" htmlFor="opt-folds">
                <Input
                  id="opt-folds"
                  type="number"
                  min={2}
                  max={10}
                  className="num"
                  value={folds}
                  onChange={(e) => setFolds(e.target.valueAsNumber || 5)}
                />
              </Field>
            )}
          </div>
          <div className="flex items-start gap-3">
            <Switch id="opt-wf" checked={walkForward} onCheckedChange={setWalkForward} />
            <Label htmlFor="opt-wf" className="text-[13px] font-normal leading-5">
              Walk-forward validation
              <span className="block text-2xs text-muted-foreground">Each fold picks parameters on its training window and is scored on held-out data.</span>
            </Label>
          </div>

          <Table>
            <thead>
              <tr>
                <Th>Parameter</Th>
                <Th>Min</Th>
                <Th>Max</Th>
                <Th>Step</Th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key}>
                  <Td className="text-muted-foreground">{label(key)}</Td>
                  {(["min", "max", "step"] as const).map((field) => (
                    <Td key={field} className="pr-2">
                      <Input
                        type="number"
                        step="any"
                        aria-label={`${label(key)} ${field}`}
                        className="num h-8 w-24"
                        value={ranges[key][field]}
                        onChange={(e) => updateRange(key, field, e.target.valueAsNumber)}
                      />
                    </Td>
                  ))}
                </tr>
              ))}
            </tbody>
          </Table>

          <Button onClick={handleOptimize} disabled={optimizing}>
            {optimizing ? "Optimizing…" : "Run optimization"}
          </Button>
        </div>

        {result ? (
          <BestParameters
            result={result}
            keys={keys}
            label={label}
            onApply={() => {
              onApplyParams(result.best_params);
              toast.success("Best parameters applied to the Single run tab");
            }}
            onExport={() => {
              const { optimization_target, walk_forward, best_params, best_score, final_backtest } = result;
              const summary = { ticker, strategy, optimization_target, walk_forward, best_params, best_score, final_backtest };
              downloadJson(summary, `optimized_${strategy}_${ticker}_${isoDate()}.json`);
            }}
          />
        ) : (
          <EmptyState title="No optimization yet" description="The best parameter set and its score will appear here." />
        )}
      </div>

      {result && result.all_results.length > 0 && (
        <Section title={result.walk_forward ? "Walk-forward folds" : "Top 10 combinations"}>
          {result.walk_forward ? (
            <FoldsTable folds={result.all_results as WalkForwardResult[]} keys={keys} label={label} />
          ) : (
            <TopResultsTable rows={(result.all_results as ParameterOptimizeResult[]).slice(0, 10)} keys={keys} label={label} />
          )}
        </Section>
      )}

      {keys.length >= 2 && (
        <Section title="Sharpe heatmap">
          <div className="mb-5 flex flex-wrap items-end gap-4">
            {(["Columns", "Rows"] as const).map((axis, i) => (
              <Field key={axis} label={axis} htmlFor={`axis-${i}`} className="w-48">
                <Select value={axes[i]} onValueChange={(v) => setAxes(i === 0 ? [v, axes[1]] : [axes[0], v])}>
                  <SelectTrigger id={`axis-${i}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {keys.map((k) => (
                      <SelectItem key={k} value={k}>
                        {label(k)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            ))}
            <Button variant="outline" onClick={handleHeatmap} disabled={mapping}>
              {mapping ? "Generating…" : "Generate heatmap"}
            </Button>
          </div>
          {heatmap ? (
            <Heatmap data={heatmap} label={label} />
          ) : (
            <p className="text-[13px] text-muted-foreground">
              Sharpe ratio across every {label(axes[0])} × {label(axes[1])} pair. Other parameters are held at their minimum.
            </p>
          )}
        </Section>
      )}
    </div>
  );
}

interface BestParametersProps {
  result: OptimizeData;
  /** The swept parameters; best_params also echoes the fixed ones. */
  keys: string[];
  label: (key: string) => string;
  onApply: () => void;
  onExport: () => void;
}

function BestParameters({ result, keys, label, onApply, onExport }: BestParametersProps) {
  const score = result.optimization_target.includes("pct") ? formatPercent(result.best_score) : formatNumber(result.best_score);
  const full = result.walk_forward ? result.final_backtest : null;

  return (
    <Section
      title="Best parameters"
      aside={
        <>
          <Button variant="link" size="sm" onClick={onApply}>
            Apply
          </Button>
          <Button variant="link" size="sm" onClick={onExport}>
            Export JSON
          </Button>
        </>
      }
    >
      <KeyValueList>
        {keys.map((key) => (
          <KeyValue key={key} label={label(key)} value={result.best_params[key]} />
        ))}
      </KeyValueList>
      <StatGrid className="mt-6">
        <Stat label={`Best ${TARGETS.find((t) => t.value === result.optimization_target)?.label.toLowerCase() ?? "score"}`} value={score} />
        {full && <Stat label="Full-period return" value={formatPercent(full.total_return_pct)} tone={pnlColor(full.total_return_pct)} />}
        {full && <Stat label="Full-period Sharpe" value={formatNumber(full.sharpe_ratio)} />}
        {full && <Stat label="Full-period max drawdown" value={formatPercent(full.max_drawdown_pct)} />}
      </StatGrid>
    </Section>
  );
}

function TopResultsTable({ rows, keys, label }: { rows: ParameterOptimizeResult[]; keys: string[]; label: (k: string) => string }) {
  return (
    <Table>
      <thead>
        <tr>
          <Th>#</Th>
          {keys.map((k) => (
            <Th key={k} align="right">
              {label(k)}
            </Th>
          ))}
          <Th align="right">Score</Th>
          <Th align="right">Return</Th>
          <Th align="right">Sharpe</Th>
          <Th align="right">Trades</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            <Td num className="text-muted-foreground">
              {i + 1}
            </Td>
            {keys.map((k) => (
              <Td key={k} num align="right">
                {r.params[k]}
              </Td>
            ))}
            <Td num align="right">
              {formatNumber(r.score)}
            </Td>
            <Td num align="right" className={pnlColor(r.total_return_pct)}>
              {formatPercent(r.total_return_pct)}
            </Td>
            <Td num align="right">
              {formatNumber(r.sharpe_ratio)}
            </Td>
            <Td num align="right">
              {r.total_trades}
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function FoldsTable({ folds, keys, label }: { folds: WalkForwardResult[]; keys: string[]; label: (k: string) => string }) {
  return (
    <Table>
      <thead>
        <tr>
          <Th>Fold</Th>
          <Th>Test window</Th>
          {keys.map((k) => (
            <Th key={k} align="right">
              {label(k)}
            </Th>
          ))}
          <Th align="right">Train score</Th>
          <Th align="right">Out-of-sample</Th>
        </tr>
      </thead>
      <tbody>
        {folds.map((f) => (
          <tr key={f.fold}>
            <Td num>{f.fold + 1}</Td>
            <Td num className="text-muted-foreground">
              {f.test_start?.slice(0, 10)} – {f.test_end?.slice(0, 10)}
            </Td>
            {keys.map((k) => (
              <Td key={k} num align="right">
                {f.selected_params[k]}
              </Td>
            ))}
            <Td num align="right">
              {formatNumber(f.train_score)}
            </Td>
            <Td num align="right">
              {f.avg_out_of_sample_score === null ? "-" : formatNumber(f.avg_out_of_sample_score)}
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

/** Green tint grows with Sharpe up to 2; non-positive cells stay untinted. */
function Heatmap({ data, label }: { data: HeatmapResponse["data"]; label: (k: string) => string }) {
  return (
    <Table>
      <thead>
        <tr>
          <Th>
            {label(data.param2_name)} ↓ / {label(data.param1_name)} →
          </Th>
          {data.param1_values.map((v) => (
            <Th key={v} align="right">
              {v}
            </Th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.heatmap_data.map((row, r) => (
          <tr key={data.param2_values[r]}>
            <Td num className="text-muted-foreground">
              {data.param2_values[r]}
            </Td>
            {row.map((cell, c) => (
              <Td
                key={c}
                num
                align="right"
                style={cell !== null && cell > 0 ? { backgroundColor: `hsl(var(--gain) / ${Math.min(cell / 2, 1) * 0.45})` } : undefined}
              >
                {formatNumber(cell)}
              </Td>
            ))}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
