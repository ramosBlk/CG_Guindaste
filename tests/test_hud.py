import unittest
from unittest.mock import patch

from train_scene.hud import ControlsHud


class ControlsHudTests(unittest.TestCase):
    def test_reopening_hud_resets_auto_collapse_timer(self):
        hud = object.__new__(ControlsHud)
        hud.expanded = False
        hud._auto_collapse_left = 0.0
        hud._last_ticks = 1000
        hud._panel_alpha = 0.0

        with patch("train_scene.hud.pygame.time.get_ticks", return_value=5000):
            hud.toggle()

        self.assertTrue(hud.expanded)
        self.assertEqual(hud._auto_collapse_left, hud.AUTO_COLLAPSE_SECONDS)

        with patch("train_scene.hud.pygame.time.get_ticks", return_value=5100):
            hud._advance()

        self.assertTrue(hud.expanded)
        self.assertAlmostEqual(
            hud._auto_collapse_left, hud.AUTO_COLLAPSE_SECONDS - 0.1
        )

    def test_hiding_hud_cancels_auto_collapse_timer(self):
        hud = object.__new__(ControlsHud)
        hud.expanded = True
        hud._auto_collapse_left = 2.0
        hud._last_ticks = 1000
        hud._panel_alpha = 1.0

        with patch("train_scene.hud.pygame.time.get_ticks", return_value=1000):
            hud.toggle()

        self.assertFalse(hud.expanded)
        self.assertEqual(hud._auto_collapse_left, 0.0)


if __name__ == "__main__":
    unittest.main()
