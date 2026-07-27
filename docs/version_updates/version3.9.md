# version3.9

## Summary

v3.9 adds a complete English core journey for international visitors while preserving the existing Chinese product. Visitors can switch languages from the page header or open a tracked `?lang=en` URL directly.

The English journey covers the home page, six ready-made movie lists, custom lists, pairwise ranking, completion results, copy controls and shareable same-list links. Douban Top250 and Douban watched-list imports remain Chinese-only because those flows depend on a Chinese-language third-party service.

## Entry and URL Behavior

- `?lang=en` opens the English interface.
- Existing query parameters such as `list`, `utm_source`, `utm_medium` and `utm_campaign` are preserved.
- Ready-made list cards, saved custom-list links and result share links continue carrying `lang=en`.
- URLs without `lang=en` continue opening the Chinese interface.

Example:

```text
https://sortfilmsgamegit.streamlit.app/?list=nolan&lang=en
```

## English Ready-Made Lists

- Christopher Nolan
- Hayao Miyazaki
- Makoto Shinkai
- Disney Animation
- Movies for Two
- Douban Top-Rated Movies

All movie titles used by these six lists have explicit English display mappings. Internal Chinese titles remain unchanged so poster lookup, existing challenge URLs and historical analytics stay compatible.

## Product and Analytics Changes

- Added `i18n.py` for language normalization, template copy, title display mappings and language-aware URL handling.
- Added English home, custom-list, pairwise ranking and result flows.
- Localized the custom battle-picker and copy-button components.
- Added `language` to anonymous event payloads.
- Kept the existing Chinese experiment surfaces and Douban import flows unchanged.

## Version Metadata

- `APP_VERSION = "v3.9"`
- `APP_RELEASE_ID = "v3.9-english-core-flow"`
- `APP_RELEASE_NAME = "中英文切换与英文核心流程"`
- `APP_RELEASED_AT = "2026-07-27T20:56:52+08:00"`

## Compatibility

- No database schema, public API or stored challenge format changed.
- Existing Chinese links remain valid.
- Poster fetching continues using the original internal title.
- English custom-list titles are displayed as entered by the visitor.

## Regression Commands

```bash
python -m py_compile merged_douban_ranker_v3.py i18n.py release_history.py
python -m unittest discover -s tests -v
git diff --check
```
