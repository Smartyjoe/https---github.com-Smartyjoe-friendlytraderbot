import asyncio
import logging
from typing import Dict, Any, Tuple

from openai import OpenAI
from bot.config import load_settings

logger = logging.getLogger(__name__)

class AIConfirmation:
    """Rate-limited AI confirmation using OpenRouter-compatible OpenAI client."""

    def __init__(self):
        self.settings = load_settings()
        self.client = OpenAI(
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
        )
        # QPS limiter: allow ~1 call per 3 seconds by default
        self._sem = asyncio.Semaphore(1)
        self._min_interval = 1.0 / max(1e-6, self.settings.rate_limit_ai_qps)
        self._last_call = 0.0

    async def confirm(self, snapshot: Dict[str, Any]) -> Tuple[str, float]:
        """Send snapshot to AI; returns (direction, confidence).
        Direction in {"CALL","PUT","NO_TRADE"}
        """
        await self._throttle()
        try:
            prompt = self._format_prompt(snapshot)
            resp = await self._create_chat(prompt)
            text = resp.strip().upper()
            # Parse minimal structured response like: "CALL|82"
            direction, conf = "NO_TRADE", 0.0
            if "CALL" in text or "PUT" in text or "NO_TRADE" in text:
                if "CALL" in text:
                    direction = "CALL"
                elif "PUT" in text:
                    direction = "PUT"
                else:
                    direction = "NO_TRADE"
            # Find confidence number
            import re
            m = re.search(r"(\d{2,3})\s*%", text)
            if m:
                conf = float(m.group(1))
            return direction, conf
        except Exception:
            logger.exception("AI confirmation failed")
            return "NO_TRADE", 0.0

    async def _create_chat(self, prompt: str):
        # OpenAI client has async or sync; create coroutine using asyncio.to_thread for sync call
        def _sync():
            completion = self.client.chat.completions.create(
                model=self.settings.deepseek_model,
                messages=[
                    {"role": "system", "content": "You are a strict trading validator. Output 'CALL|NN' or 'PUT|NN' or 'NO_TRADE|NN' with NN=confidence."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=64,
            )
            return completion.choices[0].message.content
        return await asyncio.to_thread(_sync)

    def _format_prompt(self, s: Dict[str, Any]) -> str:
        return (
            f"Market: {s.get('market_type')}\n"
            f"Asset: {s.get('asset')}\n"
            f"Expiry: {s.get('expiry_seconds')}s\n"
            f"Price: {s.get('current_price')}\n"
            f"Volatility: ATR_rel={s.get('atr_rel'):.6f}\n"
            f"EMA Trend: {s.get('ema_trend')} strength={s.get('ema_strength'):.4f}\n"
            f"RSI: {s.get('rsi'):.2f}\n"
            f"Structure: breakout={s.get('breakout')} reject={s.get('reject')}\n"
            "Task: Validate direction (CALL/PUT/NO_TRADE) for PocketOption binary option."
            " Reject choppy/manipulated conditions. Return confidence percent (0-100)."
        )

    async def _throttle(self):
        # Simple time-based throttle with semaphore
        async with self._sem:
            now = asyncio.get_event_loop().time()
            wait = max(0.0, self._last_call + self._min_interval - now)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = asyncio.get_event_loop().time()