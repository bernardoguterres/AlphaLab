import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { optimizePortfolio } from "@/services/api";
import type {
  PortfolioOptimizeRequest,
  PortfolioOptimizeResponse,
  PortfolioStrategy,
  PortfolioConstraints,
} from "@/types";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Card } from "@/components/ui/card";
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip, ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Line, LineChart } from "recharts";
import { formatPercent, formatNumber } from "@/utils/formatters";
import { Loader2, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

const OPTIMIZATION_METHODS = [
  { value: "max_sharpe", label: "Maximum Sharpe Ratio", description: "Maximize risk-adjusted returns" },
  { value: "min_variance", label: "Minimum Variance", description: "Minimize portfolio volatility" },
  { value: "risk_parity", label: "Risk Parity", description: "Equal risk contribution from each strategy" },
  { value: "equal_weight", label: "Equal Weight", description: "Simple 1/N allocation" },
];

const COLORS = ["#2563eb", "#dc2626", "#16a34a", "#ca8a04", "#9333ea", "#0891b2", "#f97316", "#ec4899"];

export default function Portfolio() {
  const location = useLocation();
  const navigate = useNavigate();

  // Get strategies from location state (passed from Compare page)
  const initialStrategies: PortfolioStrategy[] = location.state?.strategies || [];

  const [method, setMethod] = useState<PortfolioOptimizeRequest["method"]>("max_sharpe");
  const [maxWeight, setMaxWeight] = useState(0.4);
  const [minWeight, setMinWeight] = useState(0.05);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [result, setResult] = useState<PortfolioOptimizeResponse["data"] | null>(null);

  const handleOptimize = async () => {
    if (initialStrategies.length === 0) {
      toast.error("No strategies provided. Please use Compare page first.");
      return;
    }

    setIsOptimizing(true);
    try {
      const constraints: PortfolioConstraints = {
        max_weight_per_strategy: maxWeight,
        min_weight_per_strategy: minWeight,
        target_return: null,
      };

      const request: PortfolioOptimizeRequest = {
        strategies: initialStrategies,
        method,
        constraints,
      };

      const response = await optimizePortfolio(request);
      setResult(response.data);
      toast.success("Portfolio optimized!");
    } catch (err: any) {
      toast.error(err.message || "Optimization failed");
    } finally {
      setIsOptimizing(false);
    }
  };

  if (initialStrategies.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-8rem)] space-y-4">
        <h2 className="text-2xl font-bold">No Strategies Selected</h2>
        <p className="text-muted-foreground">Please run comparisons first to use portfolio optimization.</p>
        <Button onClick={() => navigate("/compare")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Go to Compare
        </Button>
      </div>
    );
  }

  // Prepare pie chart data
  const pieData = result
    ? result.optimal_weights.map((weight, i) => ({
        name: result.strategy_labels[i] || `Strategy ${i + 1}`,
        value: weight * 100,
        weight,
      }))
    : [];

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-[calc(100vh-3.5rem)]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Portfolio Optimization</h1>
          <p className="text-muted-foreground">
            Optimize capital allocation across {initialStrategies.length} strategies
          </p>
        </div>
        <Button variant="outline" onClick={() => navigate("/compare")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Compare
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {/* Configuration */}
        <Card className="p-6 space-y-4">
          <h3 className="font-semibold text-lg">Configuration</h3>

          {/* Method Selection */}
          <div className="space-y-2">
            <Label>Optimization Method</Label>
            <Select value={method} onValueChange={(v) => setMethod(v as any)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {OPTIMIZATION_METHODS.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-sm text-muted-foreground">
              {OPTIMIZATION_METHODS.find((m) => m.value === method)?.description}
            </p>
          </div>

          {/* Constraints */}
          <div className="space-y-4 pt-4 border-t">
            <h4 className="text-sm font-semibold">Constraints</h4>

            <div className="space-y-2">
              <div className="flex justify-between">
                <Label className="text-sm">Max Weight per Strategy</Label>
                <span className="text-sm font-mono">{formatPercent(maxWeight)}</span>
              </div>
              <Slider
                value={[maxWeight * 100]}
                onValueChange={(v) => setMaxWeight(v[0] / 100)}
                min={10}
                max={100}
                step={5}
              />
            </div>

            <div className="space-y-2">
              <div className="flex justify-between">
                <Label className="text-sm">Min Weight per Strategy</Label>
                <span className="text-sm font-mono">{formatPercent(minWeight)}</span>
              </div>
              <Slider
                value={[minWeight * 100]}
                onValueChange={(v) => setMinWeight(v[0] / 100)}
                min={0}
                max={20}
                step={1}
              />
            </div>
          </div>

          {/* Optimize Button */}
          <Button onClick={handleOptimize} disabled={isOptimizing} className="w-full">
            {isOptimizing ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Optimizing...
              </>
            ) : (
              "Optimize Portfolio"
            )}
          </Button>
        </Card>

        {/* Results */}
        {result && (
          <>
            {/* Metrics */}
            <Card className="p-6 space-y-4">
              <h3 className="font-semibold text-lg">Portfolio Metrics</h3>
              <div className="space-y-3">
                <div>
                  <div className="text-sm text-muted-foreground">Expected Return (Annual)</div>
                  <div className="text-2xl font-bold text-green-600">{formatPercent(result.expected_return)}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Expected Risk (Annual Std Dev)</div>
                  <div className="text-2xl font-bold">{formatPercent(result.expected_risk)}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Sharpe Ratio</div>
                  <div className="text-2xl font-bold">{result.sharpe_ratio.toFixed(2)}</div>
                </div>
              </div>
            </Card>

            {/* Weights Table */}
            <Card className="p-6 space-y-4">
              <h3 className="font-semibold text-lg">Optimal Weights</h3>
              <div className="space-y-2">
                {result.strategy_labels.map((label, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: COLORS[i % COLORS.length] }}
                      />
                      <span className="text-sm font-medium">{label}</span>
                    </div>
                    <span className="text-sm font-bold">{formatPercent(result.optimal_weights[i])}</span>
                  </div>
                ))}
              </div>
            </Card>
          </>
        )}
      </div>

      {/* Charts */}
      {result && (
        <div className="grid gap-6 md:grid-cols-2">
          {/* Pie Chart */}
          <Card className="p-6">
            <h3 className="font-semibold text-lg mb-4">Weight Allocation</h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value }) => `${name.split("_")[0]}: ${value.toFixed(1)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: any) => `${value.toFixed(2)}%`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Card>

          {/* Efficient Frontier */}
          <Card className="p-6">
            <h3 className="font-semibold text-lg mb-4">Efficient Frontier</h3>
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="risk"
                  name="Risk"
                  label={{ value: "Annual Risk (%)", position: "bottom" }}
                  tickFormatter={(v) => (v * 100).toFixed(0)}
                />
                <YAxis
                  type="number"
                  dataKey="return"
                  name="Return"
                  label={{ value: "Annual Return (%)", angle: -90, position: "left" }}
                  tickFormatter={(v) => (v * 100).toFixed(0)}
                />
                <Tooltip
                  formatter={(value: any, name: string) =>
                    name === "Sharpe" ? value.toFixed(2) : `${(value * 100).toFixed(1)}%`
                  }
                  labelFormatter={() => ""}
                />
                {/* Efficient frontier points */}
                <Scatter
                  name="Efficient Frontier"
                  data={result.efficient_frontier}
                  fill="#94a3b8"
                  shape="circle"
                />
                {/* Optimal portfolio */}
                <Scatter
                  name="Optimal Portfolio"
                  data={[{ risk: result.expected_risk, return: result.expected_return }]}
                  fill="#16a34a"
                  shape="star"
                  legendType="star"
                />
              </ScatterChart>
            </ResponsiveContainer>
          </Card>
        </div>
      )}
    </div>
  );
}
