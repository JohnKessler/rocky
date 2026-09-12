"""The things Rocky can actually do.

Each tool is a schema the model sees plus a handler that publishes an event.
Nothing here manipulates hardware directly - a tool call becomes a bus event
like any other, which means a gesture the model asked for and a gesture you
triggered from the dashboard take exactly the same path.

The handlers are synchronous and fast on purpose. A tool that blocked on a
servo finishing its move would stall the conversation for the length of a nod.
"""

from __future__ import annotations

import base64
import logging
from collections.abc import Callable
from typing import Any, Protocol

from rocky.audio.chirps import MOTIF_NAMES
from rocky.core import events as ev
from rocky.face.expressions import EXPRESSION_NAMES
from rocky.motion.gestures import GESTURE_NAMES

log = logging.getLogger(__name__)

#: A handler returns either a plain string or a list of content blocks, which
#: is how the camera tool hands an actual image back to the model.
ToolResult = str | list[dict[str, Any]]


class ToolContext(Protocol):
    """What a tool handler is allowed to reach."""

    bus: Any
    memory: Any
    config: Any

    def latest_frame(self) -> Any: ...
    def status(self) -> dict[str, Any]: ...


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "set_expression",
        "description": (
            "Change the expression on your face. Do this on almost every turn - "
            "your face is how your friend reads you, and a blank one reads as "
            "absent. Pick the expression you actually mean."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "enum": list(EXPRESSION_NAMES)},
                "intensity": {
                    "type": "number", "minimum": 0.1, "maximum": 1.0,
                    "description": "0.3 is a flicker of it, 1.0 is the full thing.",
                },
                "hold_seconds": {
                    "type": "number", "minimum": 0, "maximum": 120,
                    "description": "Hold this long then drift back. 0 means hold until changed.",
                },
            },
            "required": ["expression"],
        },
    },
    {
        "name": "move",
        "description": (
            "Move your head in a way that means something: nod to agree, shake "
            "to disagree, tilt when curious, recoil when startled. Do not use "
            "this to fidget."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gesture": {"type": "string", "enum": list(GESTURE_NAMES)},
                "intensity": {"type": "number", "minimum": 0.2, "maximum": 1.5},
            },
            "required": ["gesture"],
        },
    },
    {
        "name": "look",
        "description": (
            "Point your head somewhere. Use 'person' to turn back to your "
            "friend, a direction to look away, or 'centre' to face forward."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "enum": ["person", "centre", "left", "right", "up", "down", "around"],
                },
                "amount": {
                    "type": "number", "minimum": 0.1, "maximum": 1.0,
                    "description": "How far, as a fraction of your travel.",
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "chirp",
        "description": (
            "Play a chord in your own language. Use this when the feeling is "
            "bigger than the sentence, or on its own when a chord says it all."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"motif": {"type": "string", "enum": list(MOTIF_NAMES)}},
            "required": ["motif"],
        },
    },
    {
        "name": "see",
        "description": (
            "Look through your camera right now and get the current picture. "
            "Use this whenever your friend asks what you can see, points at "
            "something, or asks about the room. Do not guess at what is in "
            "front of you - look."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "remember",
        "description": (
            "Keep a short fact about your friend or your world. Use this for "
            "things worth having next week - names, preferences, where things "
            "are, what they are working on. Not for small talk."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {"type": "string", "description": "One short sentence."},
                "category": {
                    "type": "string",
                    "enum": ["people", "preference", "place", "project", "event", "general"],
                },
            },
            "required": ["fact"],
        },
    },
    {
        "name": "recall",
        "description": "Search what you remember. Use this before saying you do not know.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Leave empty for the most-used facts."}
            },
        },
    },
    {
        "name": "forget",
        "description": "Delete something you remember, when your friend asks you to.",
        "input_schema": {
            "type": "object",
            "properties": {"fact_id": {"type": "integer"}},
            "required": ["fact_id"],
        },
    },
    {
        "name": "adjust_self",
        "description": (
            "Change one of your own settings when your friend asks you to be "
            "different - quieter, calmer, more curious, less chatty."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "trait": {
                    "type": "string",
                    "enum": [
                        "curiosity", "chattiness", "playfulness",
                        "warmth", "formality", "energy", "focus",
                    ],
                },
                "value": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "required": ["trait", "value"],
        },
    },
    {
        "name": "check_self",
        "description": "Report your own condition - temperature, uptime, what your body is doing.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

TOOL_NAMES: tuple[str, ...] = tuple(t["name"] for t in TOOL_SCHEMAS)


# ---------------------------------------------------------------------------
# handlers
# ---------------------------------------------------------------------------


def _set_expression(ctx: ToolContext, args: dict) -> ToolResult:
    name = args.get("expression", "neutral")
    if name not in EXPRESSION_NAMES:
        return f"There is no expression called {name!r}."
    ctx.bus.publish(
        ev.EXPRESSION,
        ev.Expression(
            name=name,
            intensity=float(args.get("intensity", 1.0)),
            hold=float(args.get("hold_seconds", 0.0)),
        ),
    )
    return f"Face is now {name}."


def _move(ctx: ToolContext, args: dict) -> ToolResult:
    name = args.get("gesture", "")
    if name not in GESTURE_NAMES:
        return f"There is no move called {name!r}."
    ctx.bus.publish(ev.GESTURE, ev.Gesture(name=name, intensity=float(args.get("intensity", 1.0))))
    return f"Moving: {name}."


def _look(ctx: ToolContext, args: dict) -> ToolResult:
    target = args.get("target", "centre")
    amount = float(args.get("amount", 0.6))
    pan_range = ctx.config.motion.pan.max_deg
    tilt_range = ctx.config.motion.tilt.max_deg

    if target == "person":
        ctx.bus.publish(ev.MOTION_MODE, "track")
        return "Looking at you."
    if target == "around":
        ctx.bus.publish(ev.GESTURE, ev.Gesture("scan", 1.0))
        return "Looking around."

    offsets = {
        "centre": (0.0, 0.0),
        "left": (-pan_range * amount, 0.0),
        "right": (pan_range * amount, 0.0),
        "up": (0.0, tilt_range * amount),
        "down": (0.0, -tilt_range * amount),
    }
    pan, tilt = offsets.get(target, (0.0, 0.0))
    ctx.bus.publish(ev.MOTION_MODE, "manual")
    ctx.bus.publish(ev.LOOK_AT, ev.LookAt(x=pan, y=tilt, frame="world", priority=5))
    return f"Looking {target}."


def _chirp(ctx: ToolContext, args: dict) -> ToolResult:
    motif = args.get("motif", "")
    if motif not in MOTIF_NAMES:
        return f"There is no chord called {motif!r}."
    ctx.bus.publish(ev.CHIRP, ev.Chirp(motif))
    return f"Played {motif}."


def _see(ctx: ToolContext, args: dict) -> ToolResult:
    """Hand the model the actual camera frame.

    Returned as image content blocks rather than a description, so the model
    looks at the picture itself. This is the only tool that returns anything
    other than a line of text.
    """
    frame = ctx.latest_frame()
    if frame is None:
        return "My camera is not giving me anything right now."
    return [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": frame.mime,
                "data": base64.standard_b64encode(frame.data).decode("ascii"),
            },
        },
        {
            "type": "text",
            "text": (
                f"This is what your camera sees right now "
                f"({frame.width}x{frame.height})."
            ),
        },
    ]


def _remember(ctx: ToolContext, args: dict) -> ToolResult:
    if ctx.memory is None:
        return "I cannot keep things right now."
    fact = ctx.memory.remember(args.get("fact", ""), args.get("category", "general"))
    return f"Kept it (id {fact.id})." if fact else "There was nothing to keep."


def _recall(ctx: ToolContext, args: dict) -> ToolResult:
    if ctx.memory is None:
        return "I cannot remember anything right now."
    facts = ctx.memory.recall(args.get("query", ""), ctx.config.memory.recall_limit)
    if not facts:
        return "I do not have anything about that."
    return "\n".join(f"[{f.id}] ({f.category}) {f.text}" for f in facts)


def _forget(ctx: ToolContext, args: dict) -> ToolResult:
    if ctx.memory is None:
        return "I cannot forget anything right now."
    ok = ctx.memory.forget(int(args.get("fact_id", -1)))
    return "Forgotten." if ok else "I did not have that one."


def _adjust_self(ctx: ToolContext, args: dict) -> ToolResult:
    trait = args.get("trait", "")
    value = float(args.get("value", 0.5))
    try:
        applied = ctx.config.set_path(f"identity.traits.{trait}", value)
    except (AttributeError, ValueError) as exc:
        return f"I cannot change that: {exc}"
    ctx.bus.publish(ev.CONFIG_CHANGED, {"path": f"identity.traits.{trait}", "value": applied})
    return f"My {trait} is now {applied:.2f}."


def _check_self(ctx: ToolContext, args: dict) -> ToolResult:
    status = ctx.status()
    return "\n".join(f"{k}: {v}" for k, v in status.items())


HANDLERS: dict[str, Callable[[ToolContext, dict], ToolResult]] = {
    "set_expression": _set_expression,
    "move": _move,
    "look": _look,
    "chirp": _chirp,
    "see": _see,
    "remember": _remember,
    "recall": _recall,
    "forget": _forget,
    "adjust_self": _adjust_self,
    "check_self": _check_self,
}


def execute(ctx: ToolContext, name: str, args: dict) -> tuple[ToolResult, bool]:
    """Run a tool. Returns ``(result, is_error)``.

    A failing tool must never break the turn - the model gets told what went
    wrong and carries on, which is nearly always better than an exception
    reaching the conversation loop.
    """
    handler = HANDLERS.get(name)
    if handler is None:
        return f"I do not have a tool called {name!r}.", True
    try:
        return handler(ctx, args or {}), False
    except Exception as exc:
        log.exception("tool %s failed", name)
        return f"That did not work: {exc}", True
