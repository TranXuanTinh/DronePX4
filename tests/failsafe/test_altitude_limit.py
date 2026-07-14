"""
Altitude limit failsafe tests.

Validates altitude ceiling enforcement per safety regulations.

DO-178C Traceability: REQ-ALT-001 through REQ-ALT-004
"""
import pytest

from src.core.types import SafetyAction
from src.mission.safety import AltitudeRule


@pytest.mark.failsafe
class TestAltitudeLimit:
    """Test altitude ceiling enforcement."""

    def test_normal_altitude_is_safe(self, make_telemetry):
        """REQ-ALT-001: Altitude at 15m (< 120m max) → NONE."""
        rule = AltitudeRule(max_altitude_m=120.0)
        telem = make_telemetry(alt=15.0)
        assert rule.evaluate(telem) == SafetyAction.NONE

    def test_altitude_exceeded_triggers_rtl(self, make_telemetry):
        """REQ-ALT-002: Altitude at 150m (> 120m) → RTL_NOW."""
        rule = AltitudeRule(max_altitude_m=120.0)
        telem = make_telemetry(alt=150.0)
        assert rule.evaluate(telem) == SafetyAction.RTL_NOW

    def test_90_percent_altitude_warns(self, make_telemetry):
        """REQ-ALT-003: Altitude at 90% of max → WARN."""
        rule = AltitudeRule(max_altitude_m=120.0)
        telem = make_telemetry(alt=115.0)
        assert rule.evaluate(telem) == SafetyAction.WARN

    @pytest.mark.parametrize("max_alt", [30.0, 60.0, 120.0, 400.0])
    def test_custom_altitude_limits(self, make_telemetry, max_alt):
        """REQ-ALT-004: Various altitude limits enforce correctly."""
        rule = AltitudeRule(max_altitude_m=max_alt)

        # Within limit
        telem_ok = make_telemetry(alt=max_alt * 0.5)
        assert rule.evaluate(telem_ok) == SafetyAction.NONE

        # Near limit (90%)
        telem_warn = make_telemetry(alt=max_alt * 0.95)
        assert rule.evaluate(telem_warn) == SafetyAction.WARN

        # Beyond limit
        telem_breach = make_telemetry(alt=max_alt * 1.1)
        assert rule.evaluate(telem_breach) == SafetyAction.RTL_NOW

    def test_ground_level_altitude_is_safe(self, make_telemetry):
        """REQ-ALT-001: Altitude at 0m → NONE."""
        rule = AltitudeRule(max_altitude_m=120.0)
        telem = make_telemetry(alt=0.0)
        assert rule.evaluate(telem) == SafetyAction.NONE
