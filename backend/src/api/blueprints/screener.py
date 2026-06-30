"""Fundamental screener endpoints."""

from flask import Blueprint, jsonify, request

from ...screener import FundamentalScreener
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.api.screener")

screener_bp = Blueprint("screener", __name__)


@screener_bp.route("/api/screener/greenblatt", methods=["POST"])
def run_greenblatt_screen():
    """Run Greenblatt Magic Formula screen on a list of tickers.

    Body: {"tickers": [...], "top_n": 20, "min_market_cap_b": 1.0, "max_debt_to_equity": 2.0}
    Returns ranked candidates sorted by combined Greenblatt rank.
    """
    body = request.get_json(force=True) or {}
    tickers = body.get("tickers")
    if not tickers or not isinstance(tickers, list):
        return jsonify({"status": "error", "message": "tickers list required"}), 400

    top_n = int(body.get("top_n", 20))
    min_cap = float(body.get("min_market_cap_b", 1.0))
    max_dte = float(body.get("max_debt_to_equity", 2.0))

    logger.info("Greenblatt screen: %d tickers, top_n=%d", len(tickers), top_n)
    try:
        screener = FundamentalScreener(
            universe=tickers,
            min_market_cap_b=min_cap,
            max_debt_to_equity=max_dte,
        )
        results = screener.screen(top_n=top_n)
        return jsonify({
            "status": "ok",
            "data": {
                "candidates": [
                    {
                        "rank": r.combined_rank,
                        "ticker": r.ticker,
                        "company": r.company_name,
                        "sector": r.sector,
                        "earnings_yield_pct": round(r.earnings_yield * 100, 2),
                        "roe_pct": round(r.return_on_equity * 100, 2),
                        "pe_ratio": round(r.pe_ratio, 2),
                        "market_cap_b": round(r.market_cap_b, 2),
                        "debt_to_equity": round(r.debt_to_equity, 2),
                        "ey_rank": r.earnings_yield_rank,
                        "roe_rank": r.roe_rank,
                    }
                    for r in results
                ],
                "total_screened": len(tickers),
                "total_qualified": len(results),
            },
        })
    except Exception as exc:
        logger.exception("Greenblatt screen failed")
        return jsonify({"status": "error", "message": str(exc)}), 500
