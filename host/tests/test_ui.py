"""Basic smoke tests for UI layer — styles, i18n.

Full QWidget interaction tests require a running QApplication / display server,
which is difficult in CI.  These tests verify the data/logic layers that
underpin the UI components.
"""

import sys

import pytest


# ---------------------------------------------------------------------------
# ui.styles
# ---------------------------------------------------------------------------

class TestDarkStylesheet:
    def test_stylesheet_is_non_empty_string(self):
        from deepsight_host.ui.styles import DARK_THEME
        assert isinstance(DARK_THEME, str)
        assert len(DARK_THEME) > 0

    def test_stylesheet_contains_key_selectors(self):
        from deepsight_host.ui.styles import DARK_THEME
        # Verify that the stylesheet has content for the main widget types
        assert "QMainWindow" in DARK_THEME
        assert "QPushButton" in DARK_THEME
        assert "QLabel" in DARK_THEME
        assert "QGroupBox" in DARK_THEME
        assert "QSlider" in DARK_THEME
        assert "QTabWidget" in DARK_THEME

    def test_stylesheet_contains_color_definitions(self):
        from deepsight_host.ui.styles import DARK_THEME
        # The dark theme uses specific color tokens
        assert "#1a1a2e" in DARK_THEME       # background
        assert "#2a2a4a" in DARK_THEME       # button background
        assert "#e0e0e0" in DARK_THEME       # text color

    def test_stylesheet_has_danger_button_style(self):
        from deepsight_host.ui.styles import DARK_THEME
        assert "danger" in DARK_THEME
        assert "#ff8888" in DARK_THEME

    def test_stylesheet_has_status_label_styles(self):
        from deepsight_host.ui.styles import DARK_THEME
        assert "status_green" in DARK_THEME
        assert "status_yellow" in DARK_THEME
        assert "status_red" in DARK_THEME


# ---------------------------------------------------------------------------
# ui.i18n
# ---------------------------------------------------------------------------

class TestI18nTranslations:
    def test_tr_english_fallback(self):
        from deepsight_host.ui.i18n import I18n
        i18n = I18n()
        i18n.set_lang("en")
        result = i18n.tr("app.title")
        assert "ROV" in result or "DeepSight" in result

    def test_tr_chinese(self):
        from deepsight_host.ui.i18n import I18n
        i18n = I18n()
        i18n.set_lang("zh")
        result = i18n.tr("app.title")
        assert "自由潜水" in result or "拍摄" in result

    def test_tr_unknown_key_returns_key(self):
        from deepsight_host.ui.i18n import I18n
        i18n = I18n()
        result = i18n.tr("nonexistent.key.xyz")
        assert result == "nonexistent.key.xyz"

    def test_tr_with_format_args(self):
        from deepsight_host.ui.i18n import I18n
        i18n = I18n()
        i18n.set_lang("en")
        # "Running | Tracking: %s | %s"
        result = i18n.tr("app.running", "fast", "NOMINAL")
        assert "fast" in result
        assert "NOMINAL" in result

    def test_tr_chinese_with_format_args(self):
        from deepsight_host.ui.i18n import I18n
        i18n = I18n()
        i18n.set_lang("zh")
        result = i18n.tr("app.running", "快速", "正常")
        assert "快速" in result
        assert "正常" in result

    def test_toggle_switches_language(self):
        from deepsight_host.ui.i18n import I18n
        i18n = I18n()
        i18n.set_lang("en")
        assert i18n.lang == "en"
        i18n.toggle()
        assert i18n.lang == "zh"
        i18n.toggle()
        assert i18n.lang == "en"

    def test_module_level_tr_function(self):
        from deepsight_host.ui.i18n import tr, I18n
        # Set lang to English
        I18n.instance().set_lang("en")
        result = tr("app.title")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_module_level_tr_chinese(self):
        from deepsight_host.ui.i18n import tr, I18n
        I18n.instance().set_lang("zh")
        result = tr("app.title")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_all_safety_translations_exist(self):
        from deepsight_host.ui.i18n import I18n
        i18n = I18n()
        for lang in ("en", "zh"):
            i18n.set_lang(lang)
            for key_suffix in ("nominal", "degraded", "caution", "safe", "emergency"):
                key = f"safety.{key_suffix}"
                result = i18n.tr(key)
                assert len(result) > 0
                assert result != key, f"Missing translation for {key} in {lang}"

    def test_all_node_translations_exist(self):
        from deepsight_host.ui.i18n import I18n
        i18n = I18n()
        for lang in ("en", "zh"):
            i18n.set_lang(lang)
            for node_key in ("host", "pi", "pico", "stm32"):
                key = f"node.{node_key}"
                result = i18n.tr(key)
                assert len(result) > 0
                assert result != key

    def test_all_tracking_translations_exist(self):
        from deepsight_host.ui.i18n import I18n
        i18n = I18n()
        tracking_keys = [
            "tracking.mode", "tracking.fast", "tracking.precise",
            "tracking.reset", "tracking.fps", "tracking.latency",
            "tracking.target_id", "tracking.confidence",
            "tracking.pan_angle", "tracking.tilt_angle",
        ]
        for lang in ("en", "zh"):
            i18n.set_lang(lang)
            for key in tracking_keys:
                result = i18n.tr(key)
                assert len(result) > 0
                assert result != key

    def test_set_lang_ignores_invalid_code(self):
        from deepsight_host.ui.i18n import I18n
        i18n = I18n()
        i18n.set_lang("en")
        i18n.set_lang("fr")  # not supported
        assert i18n.lang == "en"  # unchanged


class TestI18nSingleton:
    def test_instance_is_singleton(self):
        from deepsight_host.ui.i18n import I18n
        a = I18n.instance()
        b = I18n.instance()
        assert a is b

    def test_language_changed_signal_exists(self):
        from deepsight_host.ui.i18n import I18n
        from PySide6.QtCore import Signal
        i18n = I18n.instance()
        assert isinstance(i18n.language_changed, Signal)
