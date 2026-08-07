from .moving_average_crossover import MovingAverageCrossover
from .rsi_mean_reversion import RSIMeanReversion
from .momentum_breakout import MomentumBreakout
from .bollinger_breakout import BollingerBreakout
from .vwap_reversion import VWAPReversion

# NEW: Simple, frequent-trading strategies (1-3 trades/day optimized)
from .rsi_simple import RSISimple
from .bollinger_rsi_combo import BollingerRSICombo
from .trend_adaptive_rsi import TrendAdaptiveRSI

# Value factor strategies (weekly timeframe, weeks/months holding)
from .greenblatt_weekly import GreenblattWeekly
