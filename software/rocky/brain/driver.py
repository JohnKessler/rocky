"""The brain service.

Everything that costs an API call happens here and nowhere else, so there is
one place to look when you want to know what Rocky is spending.
"""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any, Callable

from rocky.audio.chirps import motif_for_expression
from rocky.brain.agent import Agent
from rocky.brain.memory import Memory
from rocky.brain.persona import greeting_line
from rocky.core import events as ev
from rocky.core.service import Service


class BrainService(Service):
    """Listens, thinks, answers - and decides when to look."""

    name = "brain"

    def __init__(self, bus, config, *, frame_source: Callable[[], Any] | None = None,
                 status_source: Callable[[], dict] | None = None) -> None:
        super().__init__(bus, config)
        self.memory: Memory | None = None
        self.agent: Agent | None = None
        self._frame_source = frame_source or (lambda: None)
        self._status_source = status_source or dict
        self._busy = asyncio.Lock()
        self._last_interaction = time.time()
        self._last_scene_at = 0.0
        self._scene_pending = False
        self._scene: str = ""
        self._people_present = False
        self._turns = 0
        self._greeted = False

    # -- ToolContext --------------------------------------------------------
    # The brain is its own tool context: tools need the bus, the memory and
    # the camera, and the brain already holds all three.

    def latest_frame(self) -> Any:
        return self._frame_source()

    def status(self) -> dict[str, Any]:
        return self._status_source()

    # -- lifecycle ----------------------------------------------------------

    async def setup(self) -> None:
        if self.config.memory.enabled:
            self.memory = Memory(self.config.memory.path, self.config.memory.max_facts)
            self.log.info("memory: %s", self.memory.stats())
        self.agent = Agent(self.config, self)
        if not self.agent.available:
            self.log.warning("no Claude client; Rocky will move and chirp but not converse")

        self.bus.subscribe(ev.SPEECH, self._on_speech)
        self.bus.subscribe(ev.SCENE, self._on_scene)
        self.bus.subscribe(ev.MOTION_DETECTED, self._on_motion)

    async def teardown(self) -> None:
        if self.memory:
            self.memory.close()
            self.memory = None

    # -- conversation -------------------------------------------------------

    async def _on_speech(self, _topic: str, e: ev.Speech) -> None:
        if not e.final or not e.text.strip():
            return
        await self.handle_input(e.text)

    async def handle_input(self, text: str) -> str:
        """Take a line of input all the way to a spoken reply."""
        if self.agent is None:
            return ""
        if self._busy.locked():
            self.log.info("still answering the last thing; ignoring: %s", text[:40])
            return ""

        async with self._busy:
            self._last_interaction = time.time()
            self._turns += 1
            self.bus.publish(ev.BRAIN_STATE, ev.BrainState("thinking", text[:80]))
            # A thinking face immediately is the difference between a robot
            # that is considering your question and one that has frozen.
            self.bus.publish(ev.EXPRESSION, ev.Expression("thinking", 0.8, hold=12))

            if self.memory:
                self.memory.log_turn("user", text)

            reply = await self.agent.respond(text, context_note=self._context_note())

            for name, args in reply.tool_calls:
                self.bus.publish(ev.TOOL_CALL, ev.ToolCall(name=name, arguments=args))

            if reply.error:
                self.bus.publish(ev.BRAIN_STATE, ev.BrainState("error", reply.error))
                self.bus.publish(ev.EXPRESSION, ev.Expression("confused", 0.9, hold=6))
                self.bus.publish(ev.CHIRP, ev.Chirp("concern"))
                self.log.error("could not answer: %s", reply.error)
                return ""

            spoken = self._trim_reply(reply.text)
            if spoken:
                if self.memory:
                    self.memory.log_turn("rocky", spoken)
                self.bus.publish(
                    ev.UTTERANCE, ev.Utterance(text=spoken, expression=reply.expression)
                )
            elif reply.tool_calls:
                # A chord and a face can be the whole answer. That is normal
                # for Rocky, not a failure to produce text.
                self.log.debug("answered without words")

            self.bus.publish(ev.BRAIN_STATE, ev.BrainState("idle"))
            return spoken

    def _trim_reply(self, text: str) -> str:
        """Cut an over-long reply at a sentence boundary.

        The prompt asks for brevity; this is the backstop, and cutting at a
        full stop matters because the result is spoken aloud.
        """
        text = " ".join(text.split())
        limit = self.config.brain.reply_char_limit
        if len(text) <= limit:
            return text
        cut = text[:limit]
        for mark in (". ", "! ", "? "):
            idx = cut.rfind(mark)
            if idx > limit * 0.5:
                return cut[: idx + 1].strip()
        return cut.rstrip() + "..."

    def _context_note(self) -> str:
        """A short situational line prepended to the user's turn."""
        bits = []
        if self.config.brain.scene_in_context and self._scene:
            bits.append(f"you can see: {self._scene}")
        if self.memory:
            facts = self.memory.recall("", min(4, self.config.memory.recall_limit))
            if facts:
                bits.append("you remember: " + "; ".join(f.text for f in facts))
        return " | ".join(bits)

    # -- looking around -----------------------------------------------------

    async def _on_scene(self, _topic: str, e: ev.Scene) -> None:
        if "presence" in e.tags:
            arrived = "came into view" in e.summary
            if arrived and not self._people_present:
                self._people_present = True
                await self._on_arrival()
            elif not arrived:
                self._people_present = False

    async def _on_motion(self, _topic: str, payload: dict) -> None:
        if not self.config.vision.scene_on_change_only:
            return
        if time.time() - self._last_scene_at >= self.config.vision.scene_interval_s:
            self._scene_pending = True

    async def _on_arrival(self) -> None:
        """Rocky notices you arrive. How much it makes of that is the
        chattiness dial's job."""
        traits = self.config.identity.traits
        self.bus.publish(ev.EXPRESSION, ev.Expression("delighted", 0.8, hold=4))
        self.bus.publish(ev.GESTURE, ev.Gesture("perk", 0.9))
        self.bus.publish(ev.CHIRP, ev.Chirp("greeting"))
        if not self._greeted:
            self._greeted = True
            if traits.chattiness > 0.3:
                self.bus.publish(ev.UTTERANCE, ev.Utterance(greeting_line(self.config), "delighted"))

    async def describe_scene(self) -> str:
        """Ask the model what the camera can see.

        A separate, tool-free, minimal request rather than part of a
        conversation turn: it runs on a timer, and letting it share the
        conversation would put a picture of your room into every later turn's
        cached prefix.
        """
        if self.agent is None or not self.agent.available:
            return ""
        frame = self.latest_frame()
        if frame is None:
            return ""

        self._last_scene_at = time.time()
        try:
            response = await self.agent._client.messages.create(
                model=self.config.brain.model,
                max_tokens=150,
                output_config={"effort": "low"},
                system=(
                    "Describe what is in this camera frame in one short sentence, "
                    "plainly and factually. Name people, objects and what is "
                    "happening. If the frame is dark or empty, say so."
                ),
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": frame.mime,
                                "data": base64.standard_b64encode(frame.data).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": "What do you see?"},
                    ],
                }],
            )
        except Exception as exc:
            self.log.debug("scene description failed: %s", exc)
            return ""

        self.agent.usage.add(response.usage)
        summary = " ".join(b.text for b in response.content if b.type == "text").strip()
        if summary:
            self._scene = summary
            self.bus.publish(ev.SCENE, ev.Scene(summary=summary, tags=("described",)))
        return summary

    # -- background ---------------------------------------------------------

    async def run(self) -> None:
        while True:
            try:
                await self._background_tick()
            except Exception:
                self.log.exception("background tick failed")
            if not await self.sleep(2.0):
                return

    async def _background_tick(self) -> None:
        now = time.time()
        cfg = self.config

        due = now - self._last_scene_at >= cfg.vision.scene_interval_s
        if cfg.vision.enabled and cfg.brain.scene_in_context and due:
            if self._scene_pending or not cfg.vision.scene_on_change_only:
                self._scene_pending = False
                await self.describe_scene()

        idle_after = cfg.brain.idle_prompt_seconds
        if (
            idle_after > 0
            and self._people_present
            and not self._busy.locked()
            and now - self._last_interaction > idle_after
        ):
            self._last_interaction = now
            await self.handle_input(
                "[Nobody has said anything for a while. Say something unprompted "
                "if you have something worth saying, or stay quiet.]"
            )

    # -- introspection ------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "turns": self._turns,
            "busy": self._busy.locked(),
            "scene": self._scene,
            "present": self._people_present,
        }
        if self.agent:
            data.update(self.agent.snapshot())
        if self.memory:
            data["memory"] = self.memory.stats()
        return data
