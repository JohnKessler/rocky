"""Rocky's conversation loop.

A manual tool-use loop rather than the SDK's tool runner, because each tool
call has to become a bus event the instant it happens - Rocky's face should
change while it is still deciding what to say, not after the whole turn
resolves. The runner does not expose that seam.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from rocky.brain import tools as tool_mod
from rocky.brain.persona import build_system_prompt
from rocky.config import Config

log = logging.getLogger(__name__)

#: Opt-in to server-side refusal fallbacks. If the account does not have the
#: beta, the first call fails cleanly and we drop it for the rest of the run.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_write: int = 0
    requests: int = 0

    def add(self, usage: Any) -> None:
        self.requests += 1
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_read += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.cache_write += getattr(usage, "cache_creation_input_tokens", 0) or 0

    def as_dict(self) -> dict[str, int]:
        return {
            "requests": self.requests,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read": self.cache_read,
            "cache_write": self.cache_write,
        }


@dataclass
class Reply:
    text: str
    tool_calls: list[tuple[str, dict]] = field(default_factory=list)
    expression: str | None = None
    refused: bool = False
    error: str | None = None
    latency_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None and not self.refused


class Agent:
    """Holds the client, the history, and the loop."""

    def __init__(self, config: Config, context: tool_mod.ToolContext) -> None:
        self.config = config
        self.context = context
        self.usage = Usage()
        self.history: list[dict[str, Any]] = []
        self._client: Any | None = None
        self._use_fallbacks = config.brain.refusal_fallbacks
        self._available = False
        self._last_error: str | None = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            import anthropic  # noqa: PLC0415

            self._client = anthropic.AsyncAnthropic()
            self._anthropic = anthropic
            self._available = True
        except Exception as exc:
            self._last_error = str(exc)
            log.warning("Claude client unavailable: %s", exc)

    @property
    def available(self) -> bool:
        return self._available

    # -- the loop -----------------------------------------------------------

    async def respond(self, user_text: str, *, context_note: str = "") -> Reply:
        """One conversational turn, including any tool calls it needs."""
        if not self._available or self._client is None:
            return Reply(text="", error=self._last_error or "no Claude client")

        started = time.perf_counter()
        content: list[dict[str, Any]] = []
        if context_note:
            # Situational context goes in the user turn rather than the system
            # prompt so the cached prefix survives.
            content.append({"type": "text", "text": f"[{context_note}]"})
        content.append({"type": "text", "text": user_text})
        self.history.append({"role": "user", "content": content})
        self._trim()

        reply = Reply(text="")
        try:
            reply = await self._run_loop(reply)
        except Exception as exc:
            reply.error = self._describe(exc)
            log.error("conversation turn failed: %s", reply.error)
        reply.latency_s = time.perf_counter() - started
        return reply

    async def _run_loop(self, reply: Reply) -> Reply:
        for _ in range(self.config.brain.max_tool_iterations):
            response = await self._create()
            self.usage.add(response.usage)

            if getattr(response, "stop_reason", None) == "refusal":
                reply.refused = True
                details = getattr(response, "stop_details", None)
                reply.text = "I cannot help with that one."
                log.warning("model declined: %s", getattr(details, "category", "unspecified"))
                # Drop the turn from history so the refusal does not poison
                # everything that follows.
                self._drop_last_user_turn()
                return reply

            self.history.append({"role": "assistant", "content": response.content})

            text_parts = [b.text for b in response.content if b.type == "text"]
            if text_parts:
                reply.text = " ".join(p.strip() for p in text_parts).strip()

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                return reply

            results = []
            for block in tool_uses:
                args = dict(block.input or {})
                result, is_error = tool_mod.execute(self.context, block.name, args)
                reply.tool_calls.append((block.name, args))
                if block.name == "set_expression":
                    reply.expression = args.get("expression")
                entry: dict[str, Any] = {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                }
                if is_error:
                    entry["is_error"] = True
                results.append(entry)

            # All results go back in one user message. Splitting them teaches
            # the model to stop making parallel calls.
            self.history.append({"role": "user", "content": results})
            self._trim()

        log.warning("hit the tool-call ceiling; answering with what we have")
        if not reply.text:
            reply.text = "I got tangled up in that. Ask me again."
        return reply

    async def _create(self) -> Any:
        cfg = self.config.brain
        kwargs: dict[str, Any] = {
            "model": cfg.model,
            "max_tokens": cfg.max_tokens,
            "system": build_system_prompt(self.config),
            "messages": self.history,
            "tools": tool_mod.TOOL_SCHEMAS,
            "output_config": {"effort": cfg.effort},
            # The system prompt and tool list are identical every turn, so
            # caching that prefix is close to free and removes most of the
            # per-turn input cost.
            "cache_control": {"type": "ephemeral"},
        }
        if cfg.thinking:
            kwargs["thinking"] = {"type": "adaptive"}

        if self._use_fallbacks:
            try:
                return await self._client.beta.messages.create(
                    betas=[FALLBACK_BETA], fallbacks="default", **kwargs
                )
            except self._anthropic.BadRequestError as exc:
                message = str(exc).lower()
                if "beta" in message or "fallback" in message:
                    log.info("refusal fallbacks not enabled for this account; continuing without")
                    self._use_fallbacks = False
                else:
                    raise
        return await self._client.messages.create(**kwargs)

    # -- history ------------------------------------------------------------

    def _trim(self) -> None:
        """Keep the tail of the conversation.

        Trimming from the front can leave a tool_result whose tool_use has been
        cut away, which the API rejects, so the window is advanced to the next
        clean user turn.
        """
        limit = self.config.brain.history_turns * 2
        if len(self.history) <= limit:
            return
        start = len(self.history) - limit
        while start < len(self.history) and not self._is_clean_start(self.history[start]):
            start += 1
        if start >= len(self.history):
            start = max(0, len(self.history) - 2)
        self.history = self.history[start:]

    @staticmethod
    def _is_clean_start(message: dict[str, Any]) -> bool:
        if message.get("role") != "user":
            return False
        content = message.get("content")
        if isinstance(content, str):
            return True
        return not any(
            getattr(b, "type", None) == "tool_result" or
            (isinstance(b, dict) and b.get("type") == "tool_result")
            for b in (content or [])
        )

    def _drop_last_user_turn(self) -> None:
        while self.history and self.history[-1].get("role") != "user":
            self.history.pop()
        if self.history:
            self.history.pop()

    def reset(self) -> None:
        self.history.clear()

    def _describe(self, exc: Exception) -> str:
        a = getattr(self, "_anthropic", None)
        if a is None:
            return str(exc)
        if isinstance(exc, a.AuthenticationError):
            return "ANTHROPIC_API_KEY is missing or wrong"
        if isinstance(exc, a.RateLimitError):
            return "rate limited"
        if isinstance(exc, a.NotFoundError):
            return f"model {self.config.brain.model!r} is not available to this key"
        if isinstance(exc, a.APIConnectionError):
            return "cannot reach the API"
        if isinstance(exc, a.APIStatusError):
            return f"API error {exc.status_code}"
        return f"{type(exc).__name__}: {exc}"

    def snapshot(self) -> dict[str, Any]:
        return {
            "model": self.config.brain.model,
            "effort": self.config.brain.effort,
            "available": self._available,
            "history_messages": len(self.history),
            "fallbacks": self._use_fallbacks,
            "usage": self.usage.as_dict(),
            "last_error": self._last_error,
        }
