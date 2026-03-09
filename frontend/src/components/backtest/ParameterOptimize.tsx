import { useState } from "react";
import { optimizeParameters, generateHeatmap } from "@/services/api";
import type {
  ParameterOptimizeRequest,
  ParameterOptimizeResponse,
  HeatmapRequest,
  HeatmapResponse,
  StrategyType,
} from "@/types";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Loader2, Download, Check } from "lucide-react";
import { toast } from "sonner";
import { formatPercent, formatNumber } from "@/utils/formatters";

interface ParameterOptimizeProps {
  ticker: string;
  strategy: StrategyType;
  startDate: string;
  endDate: string;
  initialCapital: number;
  onApplyParams: (params: Record<string, number>) => void;
}

export default function ParameterOptimize({
  ticker,
  strategy,
  startDate,
  endDate,
  initialCapital,
  onApplyParams,
}: ParameterOptimizeProps) {
  // Optimization settings
  const [optimizationTarget, setOptimizationTarget] = useState<"sharpe_ratio" | "total_return_pct" | "max_drawdown_pct" | "win_rate">("sharpe_ratio");
  const [walkForward, setWalkForward] = useState(false);
  const [nFolds, setNFolds] = useState(5);

  // Parameter ranges (example for MA Crossover)
  const [paramRanges, setParamRanges] = useState<Record<string, { min: number; max: number; step: number }>>({
    short_window: { min: 20, max: 50, step: 10 },
    long_window: { min: 100, max: 200, step: 50 },
  });

  // Heatmap settings
  const [param1, setParam1] = useState("short_window");
  const [param2, setParam2] = useState("long_window");

  // Results
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [isGeneratingHeatmap, setIsGeneratingHeatmap] = useState(false);
  const [optimizeResult, setOptimizeResult] = useState<ParameterOptimizeResponse["data"] | null>(null);
  const [heatmapResult, setHeatmapResult] = useState<HeatmapResponse["data"] | null>(null);

  const handleOptimize = async () => {
    if (!ticker || !strategy) {
      toast.error("Please select ticker and strategy first");
      return;
    }

    setIsOptimizing(true);
    try {
      // Build param grid from ranges
      const paramGrid: Record<string, number[]> = {};
      for (const [paramName, range] of Object.entries(paramRanges)) {
        const values: number[] = [];
        for (let val = range.min; val <= range.max; val += range.step) {
          values.push(val);
        }
        paramGrid[paramName] = values;
      }

      const request: ParameterOptimizeRequest = {
        ticker,
        strategy,
        start_date: startDate,
        end_date: endDate,
        param_grid: paramGrid,
        initial_capital: initialCapital,
        optimization_target: optimizationTarget,
        walk_forward: walkForward,
        n_folds: nFolds,
      };

      const response = await optimizeParameters(request);
      setOptimizeResult(response.data);
      toast.success("Optimization complete!");
    } catch (err: any) {
      toast.error(err.message || "Optimization failed");
    } finally {
      setIsOptimizing(false);
    }
  };

  const handleGenerateHeatmap = async () => {
    if (!ticker || !strategy) {
      toast.error("Please select ticker and strategy first");
      return;
    }

    // Need exactly 2 parameters for heatmap
    const paramKeys = Object.keys(paramRanges);
    if (paramKeys.length < 2) {
      toast.error("Heatmap requires at least 2 parameters");
      return;
    }

    setIsGeneratingHeatmap(true);
    try {
      const range1 = paramRanges[param1];
      const range2 = paramRanges[param2];

      // Get fixed params (all params except the two being varied)
      const fixedParams: Record<string, number> = {};
      for (const [key, range] of Object.entries(paramRanges)) {
        if (key !== param1 && key !== param2) {
          fixedParams[key] = range.min; // Use min value as default
        }
      }

      const request: HeatmapRequest = {
        ticker,
        strategy,
        start_date: startDate,
        end_date: endDate,
        param1_name: param1,
        param1_min: range1.min,
        param1_max: range1.max,
        param1_step: range1.step,
        param2_name: param2,
        param2_min: range2.min,
        param2_max: range2.max,
        param2_step: range2.step,
        fixed_params: fixedParams,
        initial_capital: initialCapital,
      };

      const response = await generateHeatmap(request);
      setHeatmapResult(response.data);
      toast.success("Heatmap generated!");
    } catch (err: any) {
      toast.error(err.message || "Heatmap generation failed");
    } finally {
      setIsGeneratingHeatmap(false);
    }
  };

  const handleApplyBestParams = () => {
    if (optimizeResult) {
      onApplyParams(optimizeResult.best_params);
      toast.success("Best parameters applied!");
    }
  };

  const handleExportBest = () => {
    if (optimizeResult) {
      const exportData = {
        ticker,
        strategy,
        optimization_target: optimizeResult.optimization_target,
        walk_forward: optimizeResult.walk_forward,
        best_params: optimizeResult.best_params,
        best_score: optimizeResult.best_score,
        final_backtest: optimizeResult.final_backtest,
      };
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `optimized_${strategy}_${ticker}_${new Date().toISOString().split("T")[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Best parameters exported!");
    }
  };

  const updateParamRange = (paramName: string, field: "min" | "max" | "step", value: number) => {
    setParamRanges(prev => ({
      ...prev,
      [paramName]: {
        ...prev[paramName],
        [field]: value,
      },
    }));
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2">
        {/* Configuration */}
        <Card className="p-6 space-y-4">
          <h3 className="font-semibold text-lg">Optimization Settings</h3>

          {/* Optimization Target */}
          <div className="space-y-2">
            <Label>Optimization Target</Label>
            <Select value={optimizationTarget} onValueChange={(v: any) => setOptimizationTarget(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="sharpe_ratio">Sharpe Ratio</SelectItem>
                <SelectItem value="total_return_pct">Total Return %</SelectItem>
                <SelectItem value="max_drawdown_pct">Max Drawdown % (Lower is Better)</SelectItem>
                <SelectItem value="win_rate">Win Rate</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Walk-Forward Toggle */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Walk-Forward Validation</Label>
              <p className="text-sm text-muted-foreground">
                Prevent overfitting with out-of-sample testing
              </p>
            </div>
            <Switch checked={walkForward} onCheckedChange={setWalkForward} />
          </div>

          {/* N Folds (only if walk-forward enabled) */}
          {walkForward && (
            <div className="space-y-2">
              <Label>Number of Folds</Label>
              <Input
                type="number"
                min={2}
                max={10}
                value={nFolds}
                onChange={(e) => setNFolds(parseInt(e.target.value) || 5)}
              />
            </div>
          )}

          {/* Parameter Ranges */}
          <div className="space-y-4 pt-4 border-t">
            <h4 className="text-sm font-semibold">Parameter Ranges</h4>
            {Object.entries(paramRanges).map(([paramName, range]) => (
              <div key={paramName} className="space-y-2">
                <Label className="text-sm font-medium">{paramName}</Label>
                <div className="grid grid-cols-3 gap-2">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Min</Label>
                    <Input
                      type="number"
                      value={range.min}
                      onChange={(e) => updateParamRange(paramName, "min", parseFloat(e.target.value))}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Max</Label>
                    <Input
                      type="number"
                      value={range.max}
                      onChange={(e) => updateParamRange(paramName, "max", parseFloat(e.target.value))}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Step</Label>
                    <Input
                      type="number"
                      value={range.step}
                      onChange={(e) => updateParamRange(paramName, "step", parseFloat(e.target.value))}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Optimize Button */}
          <Button onClick={handleOptimize} disabled={isOptimizing} className="w-full">
            {isOptimizing ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Optimizing...
              </>
            ) : (
              "Run Optimization"
            )}
          </Button>
        </Card>

        {/* Results Summary */}
        {optimizeResult && (
          <Card className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-lg">Best Parameters</h3>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={handleApplyBestParams}>
                  <Check className="mr-2 h-4 w-4" />
                  Apply
                </Button>
                <Button size="sm" variant="outline" onClick={handleExportBest}>
                  <Download className="mr-2 h-4 w-4" />
                  Export
                </Button>
              </div>
            </div>

            {/* Best Params */}
            <div className="space-y-2">
              {Object.entries(optimizeResult.best_params).map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <span className="text-sm text-muted-foreground">{key}</span>
                  <span className="text-sm font-mono font-bold">{value}</span>
                </div>
              ))}
            </div>

            {/* Score */}
            <div className="pt-4 border-t">
              <div className="text-sm text-muted-foreground">Best Score ({optimizeResult.optimization_target})</div>
              <div className="text-2xl font-bold">
                {optimizeResult.optimization_target.includes("pct")
                  ? formatPercent(optimizeResult.best_score / 100)
                  : formatNumber(optimizeResult.best_score)}
              </div>
            </div>

            {/* Final Backtest (walk-forward only) */}
            {optimizeResult.walk_forward && optimizeResult.final_backtest && (
              <div className="space-y-2 pt-4 border-t">
                <h4 className="text-sm font-semibold">Full Data Performance</h4>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <div className="text-muted-foreground text-xs">Return</div>
                    <div className="font-bold text-green-600">
                      {formatPercent(optimizeResult.final_backtest.total_return_pct / 100)}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-xs">Sharpe</div>
                    <div className="font-bold">{optimizeResult.final_backtest.sharpe_ratio.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-xs">Max DD</div>
                    <div className="font-bold text-red-600">
                      {formatPercent(optimizeResult.final_backtest.max_drawdown_pct / 100)}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </Card>
        )}
      </div>

      {/* Top Results Table */}
      {optimizeResult && optimizeResult.all_results.length > 0 && (
        <Card className="p-6">
          <h3 className="font-semibold text-lg mb-4">
            Top 10 Parameter Combinations
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2">Rank</th>
                  {Object.keys(optimizeResult.best_params).map(key => (
                    <th key={key} className="text-left py-2">{key}</th>
                  ))}
                  <th className="text-right py-2">Score</th>
                  {!optimizeResult.walk_forward && (
                    <>
                      <th className="text-right py-2">Return %</th>
                      <th className="text-right py-2">Sharpe</th>
                      <th className="text-right py-2">Trades</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {optimizeResult.all_results.slice(0, 10).map((result: any, idx) => (
                  <tr key={idx} className="border-b hover:bg-muted/50">
                    <td className="py-2">{idx + 1}</td>
                    {Object.keys(optimizeResult.best_params).map(key => (
                      <td key={key} className="py-2 font-mono text-xs">{result.params[key]}</td>
                    ))}
                    <td className="text-right py-2 font-bold">
                      {optimizeResult.walk_forward
                        ? formatNumber(result.avg_out_of_sample_score)
                        : formatNumber(result.score)}
                    </td>
                    {!optimizeResult.walk_forward && (
                      <>
                        <td className="text-right py-2">{formatPercent(result.total_return_pct / 100)}</td>
                        <td className="text-right py-2">{result.sharpe_ratio.toFixed(2)}</td>
                        <td className="text-right py-2">{result.total_trades}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Heatmap Section */}
      {Object.keys(paramRanges).length >= 2 && (
        <Card className="p-6 space-y-4">
          <h3 className="font-semibold text-lg">Parameter Heatmap</h3>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>X-Axis Parameter</Label>
              <Select value={param1} onValueChange={setParam1}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.keys(paramRanges).map(key => (
                    <SelectItem key={key} value={key}>{key}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Y-Axis Parameter</Label>
              <Select value={param2} onValueChange={setParam2}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.keys(paramRanges).map(key => (
                    <SelectItem key={key} value={key}>{key}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button onClick={handleGenerateHeatmap} disabled={isGeneratingHeatmap} className="w-full">
            {isGeneratingHeatmap ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating Heatmap...
              </>
            ) : (
              "Generate Heatmap"
            )}
          </Button>

          {/* Simple Heatmap Display */}
          {heatmapResult && (
            <div className="pt-4">
              <div className="text-sm text-muted-foreground mb-2">
                Sharpe Ratio Heatmap ({heatmapResult.param2_name} vs {heatmapResult.param1_name})
              </div>
              <div className="overflow-x-auto">
                <table className="border-collapse">
                  <thead>
                    <tr>
                      <th className="border p-1 text-xs"></th>
                      {heatmapResult.param1_values.map((val, i) => (
                        <th key={i} className="border p-1 text-xs font-mono">{val}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {heatmapResult.heatmap_data.map((row, rowIdx) => (
                      <tr key={rowIdx}>
                        <th className="border p-1 text-xs font-mono">
                          {heatmapResult.param2_values[rowIdx]}
                        </th>
                        {row.map((cell, cellIdx) => {
                          const value = cell !== null ? cell : 0;
                          const colorIntensity = value > 0
                            ? Math.min(Math.max((value / 2) * 100, 0), 100)
                            : 0;
                          return (
                            <td
                              key={cellIdx}
                              className="border p-1 text-xs font-mono text-center"
                              style={{
                                backgroundColor: cell !== null
                                  ? `rgba(34, 197, 94, ${colorIntensity / 100})`
                                  : "#f1f5f9",
                                color: colorIntensity > 50 ? "white" : "black",
                              }}
                            >
                              {cell !== null ? cell.toFixed(2) : "—"}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
