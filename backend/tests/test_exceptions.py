"""Tests for custom exception hierarchy."""

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.utils.exceptions import (
    AlphaLabException,
    DataFetchError,
    InvalidTickerError,
    InsufficientDataError,
    DataValidationError,
    InvalidStrategyError,
    BacktestError,
    PortfolioError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_base(self):
        for exc_cls in (
            DataFetchError,
            InvalidTickerError,
            InsufficientDataError,
            DataValidationError,
            InvalidStrategyError,
            BacktestError,
            PortfolioError,
        ):
            assert issubclass(exc_cls, AlphaLabException)
            assert issubclass(exc_cls, Exception)

    def test_ticker_and_insufficient_data_are_data_fetch_errors(self):
        # These two are more specific subtypes of DataFetchError, so callers
        # can catch DataFetchError to handle both.
        assert issubclass(InvalidTickerError, DataFetchError)
        assert issubclass(InsufficientDataError, DataFetchError)

    def test_can_raise_and_catch_base_exception(self):
        with pytest.raises(AlphaLabException):
            raise InvalidTickerError("XYZ not found")

    def test_can_raise_and_catch_data_fetch_error(self):
        with pytest.raises(DataFetchError):
            raise InsufficientDataError("only 2 rows")

    def test_message_is_preserved(self):
        try:
            raise BacktestError("engine crashed on bar 42")
        except AlphaLabException as e:
            assert str(e) == "engine crashed on bar 42"

    def test_unrelated_exceptions_not_caught(self):
        # PortfolioError should not be catchable as a DataFetchError
        with pytest.raises(PortfolioError):
            try:
                raise PortfolioError("insufficient funds")
            except DataFetchError:
                pytest.fail("PortfolioError should not be a DataFetchError")
            except AlphaLabException:
                raise

    def test_data_validation_error_not_a_data_fetch_error(self):
        assert not issubclass(DataValidationError, DataFetchError)

    def test_invalid_strategy_error_distinct_branch(self):
        assert not issubclass(InvalidStrategyError, DataFetchError)
        assert issubclass(InvalidStrategyError, AlphaLabException)
