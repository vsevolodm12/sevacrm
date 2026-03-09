import time
from typing import Dict, Tuple

import httpx

from app.config import settings


class CurrencyService:
    def __init__(self):
        self._cache: Dict[str, Tuple[float, float]] = {}  # key -> (rate, timestamp)
        self._cache_ttl = 3600  # 1 hour

    async def get_rate(self, from_currency: str, to_currency: str = "RUB") -> float:
        if from_currency == to_currency:
            return 1.0

        cache_key = f"{from_currency}{to_currency}"
        now = time.time()

        if cache_key in self._cache:
            rate, ts = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return rate

        try:
            ticker = f"{from_currency}{to_currency}=X"
            url = f"{settings.yahoo_finance_api}/{ticker}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    params={"interval": "1d", "range": "1d"},
                )
                response.raise_for_status()
                data = response.json()
                rate = float(
                    data["chart"]["result"][0]["meta"]["regularMarketPrice"]
                )
                self._cache[cache_key] = (rate, now)
                return rate
        except Exception:
            # Try reverse rate
            try:
                reverse_key = f"{to_currency}{from_currency}"
                ticker = f"{to_currency}{from_currency}=X"
                url = f"{settings.yahoo_finance_api}/{ticker}"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        url,
                        headers={"User-Agent": "Mozilla/5.0"},
                        params={"interval": "1d", "range": "1d"},
                    )
                    response.raise_for_status()
                    data = response.json()
                    reverse_rate = float(
                        data["chart"]["result"][0]["meta"]["regularMarketPrice"]
                    )
                    if reverse_rate != 0:
                        rate = 1.0 / reverse_rate
                        self._cache[cache_key] = (rate, now)
                        return rate
            except Exception:
                pass

            # Fallback to cached value if available
            if cache_key in self._cache:
                return self._cache[cache_key][0]

            # Last resort fallback values
            fallbacks = {
                "USDRUB": 90.0,
                "EURRUB": 98.0,
                "EURUSD": 1.09,
            }
            return fallbacks.get(cache_key, 1.0)

    async def convert_to_rub(self, amount: float, currency: str) -> float:
        if currency == "RUB":
            return amount
        rate = await self.get_rate(currency, "RUB")
        return amount * rate


currency_service = CurrencyService()
