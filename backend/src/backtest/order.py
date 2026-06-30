"""Order model and enums for the backtesting engine."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OrderType(Enum):
    MARKET = "market"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Represents a single order in the backtest."""

    ticker: str
    side: OrderSide
    shares: int
    order_type: OrderType = OrderType.MARKET
    status: OrderStatus = OrderStatus.PENDING
    filled_price: float | None = None
    commission: float = 0.0
    slippage: float = 0.0
    timestamp: datetime | None = None
    filled_timestamp: datetime | None = None
    reason: str = ""

    @property
    def total_cost(self) -> float:
        """Total cost including price, commission, and slippage."""
        if self.filled_price is None:
            return 0.0
        base = self.filled_price * self.shares
        return base + self.commission + self.slippage

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "side": self.side.value,
            "shares": self.shares,
            "order_type": self.order_type.value,
            "status": self.status.value,
            "filled_price": self.filled_price,
            "commission": round(self.commission, 4),
            "slippage": round(self.slippage, 4),
            "timestamp": str(self.timestamp) if self.timestamp else None,
            "filled_timestamp": (
                str(self.filled_timestamp) if self.filled_timestamp else None
            ),
            "reason": self.reason,
        }
