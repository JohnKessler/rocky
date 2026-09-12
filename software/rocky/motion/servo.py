"""Servo backends.

One interface, two implementations: a PCA9685 over I2C, and a simulator that
records what it was told. The simulator is not a stub - it is what the tests
assert against, and what lets the whole robot run on a laptop.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from rocky.motion.kinematics import pulse_us_to_duty

log = logging.getLogger(__name__)


class ServoBackend(ABC):
    """A bank of PWM channels."""

    @abstractmethod
    def set_pulse(self, channel: int, pulse_us: float) -> None:
        """Drive one channel to a pulse width."""

    @abstractmethod
    def release(self, channel: int) -> None:
        """Cut drive to a channel.

        This matters more than it looks. A digital servo holding position
        against its own gear lash hums continuously; releasing it when the head
        has been still for a moment is the difference between a robot you leave
        on your desk and one you unplug.
        """

    def close(self) -> None:
        """Release everything and drop the bus."""

    @property
    def kind(self) -> str:
        return type(self).__name__


class SimServoBackend(ServoBackend):
    """Records channel state. Used on a laptop and by the tests."""

    def __init__(self, frequency_hz: int = 50) -> None:
        self.frequency_hz = frequency_hz
        self.pulses: dict[int, float] = {}
        self.energised: dict[int, bool] = {}
        self.writes = 0

    def set_pulse(self, channel: int, pulse_us: float) -> None:
        self.pulses[channel] = pulse_us
        self.energised[channel] = True
        self.writes += 1

    def release(self, channel: int) -> None:
        self.energised[channel] = False

    def close(self) -> None:
        for channel in list(self.energised):
            self.release(channel)


class PCA9685Backend(ServoBackend):
    """Adafruit PCA9685 on the Pi's I2C bus."""

    def __init__(self, address: int = 0x40, frequency_hz: int = 50) -> None:
        import adafruit_pca9685  # noqa: PLC0415  - optional hardware dependency
        import board  # noqa: PLC0415
        import busio  # noqa: PLC0415

        self.frequency_hz = frequency_hz
        self._i2c = busio.I2C(board.SCL, board.SDA)
        self._pca = adafruit_pca9685.PCA9685(self._i2c, address=address)
        self._pca.frequency = frequency_hz
        log.info("PCA9685 ready at 0x%02x, %d Hz", address, frequency_hz)

    def set_pulse(self, channel: int, pulse_us: float) -> None:
        self._pca.channels[channel].duty_cycle = pulse_us_to_duty(pulse_us, self.frequency_hz)

    def release(self, channel: int) -> None:
        self._pca.channels[channel].duty_cycle = 0

    def close(self) -> None:
        try:
            for channel in range(16):
                self.release(channel)
            self._pca.deinit()
        except Exception:  # pragma: no cover - teardown on real hardware
            log.debug("PCA9685 teardown was not clean", exc_info=True)


def make_servo_backend(preference: str, address: int, frequency_hz: int) -> ServoBackend:
    """Pick a backend. ``auto`` tries the real one and falls back quietly."""
    if preference == "sim":
        return SimServoBackend(frequency_hz)
    try:
        return PCA9685Backend(address, frequency_hz)
    except Exception as exc:
        if preference == "pca9685":
            raise
        log.info("No PCA9685 (%s); running servos in simulation", exc)
        return SimServoBackend(frequency_hz)
