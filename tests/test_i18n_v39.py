from __future__ import annotations

import unittest

from i18n import (
    ENGLISH_HOME_TEMPLATE_IDS,
    ENGLISH_MOVIE_TITLES,
    LANG_EN,
    LANG_ZH,
    normalize_language,
    translate_movie_title,
    translate_template_field,
    translate_theme,
    with_language_param,
)
from launch_copy import get_template
from release_history import APP_RELEASE_ID, APP_VERSION, get_release_by_version


class EnglishCoreFlowTests(unittest.TestCase):
    def test_language_normalization(self) -> None:
        self.assertEqual(LANG_EN, normalize_language("en"))
        self.assertEqual(LANG_EN, normalize_language("en-US"))
        self.assertEqual(LANG_EN, normalize_language("EN_gb"))
        self.assertEqual(LANG_ZH, normalize_language("zh-CN"))
        self.assertEqual(LANG_ZH, normalize_language(""))

    def test_every_english_home_movie_has_an_english_title(self) -> None:
        for template_id in ENGLISH_HOME_TEMPLATE_IDS:
            template = get_template(template_id)
            self.assertIsNotNone(template, template_id)
            assert template is not None
            for title in template.get("items", []):
                self.assertIn(str(title), ENGLISH_MOVIE_TITLES, f"{template_id}: {title}")
                self.assertNotEqual(str(title), translate_movie_title(title, LANG_EN))

    def test_every_english_home_template_has_localized_copy(self) -> None:
        for template_id in ENGLISH_HOME_TEMPLATE_IDS:
            template = get_template(template_id)
            self.assertIsNotNone(template, template_id)
            assert template is not None
            for field in ("name", "theme", "tagline", "badge", "recommendation"):
                translated = translate_template_field(template, field, LANG_EN)
                self.assertTrue(translated, f"{template_id}: {field}")
                self.assertNotEqual(str(template.get(field) or ""), translated)
            self.assertEqual(
                translate_template_field(template, "theme", LANG_EN),
                translate_theme(template.get("theme"), template_id, LANG_EN),
            )

    def test_english_url_preserves_attribution_and_fragment(self) -> None:
        url = (
            "https://example.com/path?list=nolan&utm_source=letterboxd"
            "&utm_medium=organic_social&utm_campaign=launch_profile#result"
        )
        translated = with_language_param(url, LANG_EN)
        self.assertIn("list=nolan", translated)
        self.assertIn("utm_source=letterboxd", translated)
        self.assertIn("utm_medium=organic_social", translated)
        self.assertIn("utm_campaign=launch_profile", translated)
        self.assertIn("lang=en", translated)
        self.assertTrue(translated.endswith("#result"))
        self.assertEqual(url, with_language_param(url, LANG_ZH))

    def test_v39_release_keeps_v38_history(self) -> None:
        self.assertEqual("v3.9", APP_VERSION)
        self.assertEqual("v3.9-english-core-flow", APP_RELEASE_ID)
        self.assertEqual("v3.8-abtest-funnel-recovery", get_release_by_version("v3.8")["release_id"])


if __name__ == "__main__":
    unittest.main()
