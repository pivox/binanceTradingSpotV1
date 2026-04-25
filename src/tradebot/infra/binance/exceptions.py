class BinanceApiError(Exception):
    def __init__(self, code: int, msg: str, http_status: int = 0) -> None:
        super().__init__(f"Binance API error {code}: {msg}")
        self.code = code
        self.msg = msg
        self.http_status = http_status


class BinanceRateLimitError(BinanceApiError):
    pass


class BinanceIpBanError(BinanceApiError):
    pass


class BinanceInvalidQtyError(BinanceApiError):
    pass


class BinanceServerError(Exception):
    pass


class BinanceTimeoutError(Exception):
    pass
