"""Headless tests for the line rasteriser and game rules (no window or GPU needed).

Run from the repository root:
    python -m unittest discover tests
"""
import contextlib
import io
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import catch_the_diamonds as game  # noqa: E402


def plotted_points(draw, *args):
    """Run a drawing function with OpenGL stubbed out and return the plotted pixels."""
    points = []
    saved = game.glVertex2f, game.glBegin, game.glEnd
    game.glVertex2f = lambda x, y: points.append((x, y))
    game.glBegin = game.glEnd = lambda *_: None
    try:
        draw(*args)
    finally:
        game.glVertex2f, game.glBegin, game.glEnd = saved
    return points


class MidpointLineTests(unittest.TestCase):
    def test_zone_conversion_round_trips(self):
        for zone in range(8):
            for x, y in [(3, 7), (-4, 9), (0, -5), (12, 0)]:
                x0, y0 = game.convert_to_zone0(zone, x, y)
                self.assertEqual(game.convert_from_zone0(zone, x0, y0), (x, y))

    def test_random_lines_in_every_zone(self):
        rng = random.Random(42)
        zones = set()
        for _ in range(3000):
            x1, y1, x2, y2 = (rng.randint(-40, 40) for _ in range(4))
            zones.add(game.find_zone(x1, y1, x2, y2))
            points = plotted_points(game.draw_line, x1, y1, x2, y2)
            dx, dy = x2 - x1, y2 - y1

            # One pixel per step along the major axis, no duplicates, both endpoints hit.
            self.assertEqual(len(points), max(abs(dx), abs(dy)) + 1)
            self.assertEqual(len(set(points)), len(points))
            self.assertIn((x1, y1), points)
            self.assertIn((x2, y2), points)

            for (ax, ay), (bx, by) in zip(points, points[1:]):
                self.assertEqual(max(abs(ax - bx), abs(ay - by)), 1)  # 8-connected

            for px, py in points:  # never more than half a pixel off the ideal line
                if abs(dx) >= abs(dy) and dx:
                    self.assertLessEqual(abs(py - (y1 + (px - x1) * dy / dx)), 0.5)
                elif dy:
                    self.assertLessEqual(abs(px - (x1 + (py - y1) * dx / dy)), 0.5)
        self.assertEqual(zones, set(range(8)))

    def test_float_endpoints_are_rounded(self):
        points = plotted_points(game.draw_line, 10.4, 5.6, 30.2, 20.7)
        self.assertIn((10, 6), points)
        self.assertIn((30, 21), points)

    def test_seven_segment_eight_contains_every_digit(self):
        eight = set(plotted_points(game.draw_digit, "8", 0, 0))
        for digit in "0123456789":
            self.assertLessEqual(set(plotted_points(game.draw_digit, digit, 0, 0)), eight)


class GameRuleTests(unittest.TestCase):
    def setUp(self):
        random.seed(0)
        game.reset_game()
        game.cheat_mode = False
        game.held_keys.clear()
        self._quiet = contextlib.redirect_stdout(io.StringIO())
        self._quiet.__enter__()

    def tearDown(self):
        self._quiet.__exit__(None, None, None)

    def test_catch_scores_and_speeds_up(self):
        game.catcher_x = game.diamond_x = 200
        game.diamond_y = 60
        game.update(0.05)
        self.assertEqual(game.score, 1)
        self.assertEqual(game.diamond_speed, game.DIAMOND_START_SPEED + game.DIAMOND_SPEED_STEP)
        self.assertEqual(game.diamond_y, game.DIAMOND_SPAWN_Y)

    def test_miss_ends_game(self):
        game.catcher_x, game.diamond_x, game.diamond_y = 40, 360, 10
        game.update(0.05)
        self.assertTrue(game.game_over)

    def test_fast_diamond_does_not_tunnel_through_catcher(self):
        game.catcher_x = game.diamond_x = 200
        game.diamond_y = 150
        game.diamond_speed = 5000  # moves 500 px in one 0.1 s step
        game.update(0.1)
        self.assertEqual(game.score, 1)
        self.assertFalse(game.game_over)

    def test_pause_freezes_the_game(self):
        game.toggle_pause()
        y = game.diamond_y
        game.update(0.1)
        self.assertEqual(game.diamond_y, y)

    def test_held_key_moves_catcher_and_clamps(self):
        game.catcher_x = 200
        game.held_keys.add(game.GLUT_KEY_LEFT)
        game.update(0.1)
        self.assertAlmostEqual(game.catcher_x, 200 - game.CATCHER_SPEED * 0.1)
        for _ in range(10):
            game.diamond_y = game.DIAMOND_SPAWN_Y
            game.update(0.1)
        self.assertEqual(game.catcher_x, game.CATCHER_MIN_X)

    def test_cheat_mode_catches_from_the_far_side(self):
        game.cheat_mode = True
        game.catcher_x, game.diamond_x = game.CATCHER_MIN_X, game.WINDOW_WIDTH - 30
        while game.score == 0 and not game.game_over:
            game.update(1 / 60)
        self.assertEqual(game.score, 1)


if __name__ == "__main__":
    unittest.main()
