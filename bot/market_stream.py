import asyncio
import logging
from typing import Callable, Dict, List, Optional

from bot.config import load_settings

try:
    # PocketOptionAPI cloned repo path is added in config
    from pocketoptionapi_async import AsyncPocketOptionClient
    from pocketoptionapi_async.models import TimeFrame, Candle
except Exception as e:
    raise RuntimeError("PocketOptionAPI import failed. Ensure repo is present and importable.") from e

logger = logging.getLogger(__name__)

class MarketStream:
    """Event-driven market stream built on AsyncPocketOptionClient.

    - Maintains a persistent websocket connection
    - Requests candle streams via changeSymbol messages
    - Emits updates through async callbacks
    - Auto-reconnects and region fallback handled by the API
    """

    def __init__(self, asset: str, timeframe_seconds: int):
        self.settings = load_settings()
        self.asset = asset
        self.timeframe = timeframe_seconds
        self.client: Optional[AsyncPocketOptionClient] = None
        self._connected = asyncio.Event()
        self._stop = asyncio.Event()

        # Callbacks
        self._on_candles: List[Callable[[List[Candle]], None]] = []
        self._on_stream: List[Callable[[Dict], None]] = []

        # Internal refresh cadence to keep stream fresh
        self._refresh_interval = max(2, min(10, self.timeframe // 2))

    def add_candle_callback(self, cb: Callable[[List[Candle]], None]) -> None:
        self._on_candles.append(cb)

    def add_stream_callback(self, cb: Callable[[Dict], None]) -> None:
        self._on_stream.append(cb)

    async def connect(self) -> bool:
        if not self.settings.pocket_option_ssid:
            logger.error("Missing POCKET_OPTION_SSID. Configure .env or ssid.txt.")
            return False
        self.client = AsyncPocketOptionClient(
            ssid=self.settings.pocket_option_ssid,
            is_demo=self.settings.is_demo,
            enable_logging=False,
            persistent_connection=True,
        )
        # Register high-level callbacks
        self.client.add_event_callback("candles_received", self._handle_candles_received)
        self.client.add_event_callback("stream_update", self._handle_stream_update)
        self.client.add_event_callback("disconnected", self._handle_disconnected)

        success = await self.client.connect()
        if success:
            self._connected.set()
            logger.info(f"Connected to PocketOption for {self.asset} @ {self.timeframe}s")
            return True
        logger.error("Failed to connect PocketOption client")
        return False

    async def disconnect(self) -> None:
        self._stop.set()
        if self.client:
            await self.client.disconnect()
        self._connected.clear()

    async def _handle_candles_received(self, data: Dict) -> None:
        # The client resolves candle requests via futures; we still parse downstream by calling get_candles
        pass

    async def _handle_stream_update(self, data: Dict) -> None:
        for cb in self._on_stream:
            try:
                res = cb(data)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                logger.exception("Stream callback error")

    async def subscribe(self) -> None:
        """Starts periodic changeSymbol candle requests to maintain a live stream.
        The API will respond via websocket with loadHistoryPeriod/updateStream.
        """
        await self._connected.wait()
        assert self.client is not None

        while not self._stop.is_set():
            try:
                candles = await self.client.get_candles(
                    asset=self.asset,
                    timeframe=self.timeframe,
                    count=200,
                )
                if candles:
                    for cb in self._on_candles:
                        try:
                            res = cb(candles)
                            if asyncio.iscoroutine(res):
                                await res
                        except Exception:
                            logger.exception("Candle callback error")
            except Exception:
                logger.exception("get_candles failed; will retry")
            await asyncio.sleep(self._refresh_interval)

    async def run(self) -> None:
        """Run connection and subscription loop."""
        try:
            ok = await self.connect()
            if not ok:
                return
            await self.subscribe()
        finally:
            await self.disconnect()