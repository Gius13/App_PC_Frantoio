"""Test automatici del tema chiaro/scuro e della preferenza utente."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets

from app_frantoio.ui.calendar import configure_calendar
from app_frantoio.ui.theme import (
    apply_theme, calendar_stylesheet, current_theme,
    normalize_theme, theme_stylesheet,
)
from app_frantoio.util import config


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    @classmethod
    def tearDownClass(cls):
        apply_theme("light")

    def test_both_themes_use_red_not_blue(self):
        for name in ("light", "dark"):
            css = theme_stylesheet(name).lower()
            cal = calendar_stylesheet(name).lower()
            self.assertIn("#b91c2b" if name == "light" else "#db3042", css)
            self.assertNotIn("#2563eb", css + cal)
            self.assertNotIn("#2463eb", css + cal)
            self.assertIn("qlineargradient", css)

    def test_dropdown_arrows_are_packaged_and_visible_in_css(self):
        from pathlib import Path
        from app_frantoio.resources import resource_path
        svg = Path(resource_path("dropdown_arrow.svg"))
        self.assertTrue(svg.exists())
        self.assertIn("stroke", svg.read_text(encoding="utf-8"))
        css = theme_stylesheet("dark")
        self.assertIn("QComboBox::down-arrow", css)
        self.assertIn("QDateEdit::down-arrow", css)
        self.assertIn("dropdown_arrow.svg", css)
        self.assertNotIn("$arrow", css)

    def test_calendar_updates_in_place_on_theme_change(self):
        apply_theme("light")
        editor = QtWidgets.QDateEdit()
        configure_calendar(editor)
        calendar = editor.calendarWidget()
        self.assertEqual(calendar.property("frantoioCalendar"), True)
        light_css = calendar.styleSheet()
        self.assertIn("#ffffff", light_css)

        apply_theme("dark")
        self.assertEqual(current_theme(), "dark")
        self.assertIs(editor.calendarWidget(), calendar)
        dark_css = calendar.styleSheet()
        self.assertNotEqual(dark_css, light_css)
        self.assertIn("#db3042", dark_css)
        self.assertIn("#1d1d20", dark_css)
        editor.setDate(QtCore.QDate(2026, 11, 6))
        self.assertEqual(editor.date(), QtCore.QDate(2026, 11, 6))
        editor.close()

    def test_invalid_theme_falls_back_to_light(self):
        self.assertEqual(normalize_theme("unknown"), "light")
        self.assertEqual(apply_theme("unknown"), "light")

    def test_saved_choice_is_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(config, "appdata_dir", return_value=Path(tmp)):
                settings = config.load_config()
                self.assertEqual(settings["theme"], "light")
                settings["theme"] = "dark"
                config.save_config(settings)
                self.assertEqual(config.load_config()["theme"], "dark")


if __name__ == "__main__":
    unittest.main()
