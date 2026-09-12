"""Rocky - a compact desk companion.

The package is organised as a set of cooperating services that talk to each
other over an in-process event bus rather than by calling into each other:

    audio   hears you and speaks back
    vision  watches the room
    motion  points the head
    face    draws the expression
    brain   decides what Rocky thinks about all of it
    web     exposes the dashboard

Every hardware-facing module ships a real backend and a simulated one, and
picks between them at runtime. That means the entire robot - face animation,
servo motion, conversation - runs on a laptop with no hardware attached,
which is how the tests exercise it.
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
