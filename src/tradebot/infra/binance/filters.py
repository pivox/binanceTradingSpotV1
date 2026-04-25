from decimal import Decimal, ROUND_DOWN

from tradebot.domain.models.symbol_filters import SymbolFilters


class BinanceFilters:

    @staticmethod
    def round_quantity(qty: Decimal, filters: SymbolFilters) -> Decimal:
        step = filters.step_size
        # Floor strict : (qty // step) * step
        rounded = (qty // step) * step
        # Aligner le nombre de décimales sur step_size
        decimals = abs(step.normalize().as_tuple().exponent)
        return rounded.quantize(Decimal(10) ** -decimals, rounding=ROUND_DOWN)

    @staticmethod
    def round_price(price: Decimal, filters: SymbolFilters) -> Decimal:
        tick = filters.tick_size
        # Arrondi au plus proche sur tick_size
        rounded = (price / tick).quantize(Decimal("1"), rounding=ROUND_DOWN) * tick
        decimals = abs(tick.normalize().as_tuple().exponent)
        return rounded.quantize(Decimal(10) ** -decimals)

    @staticmethod
    def validate_order(
        qty: Decimal,
        price: Decimal | None,
        filters: SymbolFilters,
    ) -> None:
        if qty < filters.min_qty:
            raise ValueError(
                f"quantity {qty} < min_qty {filters.min_qty} for {filters.symbol}"
            )
        if qty > filters.max_qty:
            raise ValueError(
                f"quantity {qty} > max_qty {filters.max_qty} for {filters.symbol}"
            )
        if price is not None:
            notional = qty * price
            if notional < filters.min_notional:
                raise ValueError(
                    f"notional {notional} < min_notional {filters.min_notional} for {filters.symbol}"
                )
            if price < filters.min_price:
                raise ValueError(
                    f"price {price} < min_price {filters.min_price} for {filters.symbol}"
                )
            if filters.max_price > Decimal("0") and price > filters.max_price:
                raise ValueError(
                    f"price {price} > max_price {filters.max_price} for {filters.symbol}"
                )

    @staticmethod
    def apply(
        qty: Decimal,
        price: Decimal | None,
        filters: SymbolFilters,
    ) -> tuple[Decimal, Decimal | None]:
        rounded_qty = BinanceFilters.round_quantity(qty, filters)
        rounded_price = BinanceFilters.round_price(price, filters) if price is not None else None
        BinanceFilters.validate_order(rounded_qty, rounded_price, filters)
        return rounded_qty, rounded_price
