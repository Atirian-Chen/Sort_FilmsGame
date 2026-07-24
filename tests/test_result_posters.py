from __future__ import annotations

import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from merged_douban_ranker_v3 import (
    generate_top10_poster_bytes,
    generate_top100_poster_bytes,
    result_poster_items,
    result_poster_scope,
    top100_column_layout,
)


def sample_poster_bytes(color: tuple[int, int, int]) -> bytes:
    output = BytesIO()
    Image.new("RGB", (300, 450), color).save(output, format="JPEG", quality=88)
    return output.getvalue()


class ResultPosterTests(unittest.TestCase):
    def test_top10_poster_is_fixed_portrait_and_limits_items(self) -> None:
        ranked = [f"电影 {index:03d}" for index in range(1, 13)]
        poster_map = {
            title: sample_poster_bytes((40 + index * 8, 80, 130))
            for index, title in enumerate(ranked[:10])
        }
        poster_bytes = generate_top10_poster_bytes(
            "我的电影审美名单",
            ranked,
            "测试用户",
            "留白卡片",
            share_url="https://example.com/list",
            include_qr=True,
            poster_bytes_map=poster_map,
        )
        with Image.open(BytesIO(poster_bytes)) as image:
            self.assertEqual("PNG", image.format)
            self.assertEqual((1080, 1920), image.size)
            self.assertEqual("RGB", image.mode)
        self.assertEqual(ranked[:10], result_poster_items(ranked, 10))
        self.assertEqual(10, len(set(result_poster_items(ranked, 10))))

    def test_top10_poster_allows_missing_posters_and_long_titles(self) -> None:
        ranked = [f"这是一部拥有很长很长中文标题的电影第{index}部" for index in range(1, 9)]
        poster_bytes = generate_top10_poster_bytes(
            "一个同样很长但必须稳定换行的电影审美名单标题",
            ranked,
            "",
            "夜场蓝",
            include_qr=False,
            poster_bytes_map={},
        )
        with Image.open(BytesIO(poster_bytes)) as image:
            self.assertEqual((1080, 1920), image.size)

    def test_top100_column_layout_boundaries_and_cutoff(self) -> None:
        for count, expected_columns, expected_items in [
            (1, 1, 1),
            (26, 2, 26),
            (51, 3, 51),
            (76, 4, 76),
            (100, 4, 100),
            (120, 4, 100),
        ]:
            ranked = [f"电影 {index:03d}" for index in range(1, count + 1)]
            columns = top100_column_layout(ranked)
            flattened = [item for column in columns for item in column]
            self.assertEqual(expected_columns, len(columns), count)
            self.assertEqual(expected_items, len(flattened), count)
            self.assertTrue(all(len(column) <= 25 for column in columns), count)
            self.assertEqual(ranked[:100], flattened, count)
            self.assertEqual(len(flattened), len(set(flattened)), count)

    def test_top100_poster_is_fixed_size_and_never_fetches_movie_posters(self) -> None:
        ranked = [f"第{index:03d}名 一部标题很长但不能越过当前栏位的电影" for index in range(1, 121)]
        with patch("merged_douban_ranker_v3.get_result_poster_bytes") as poster_fetch:
            poster_bytes = generate_top100_poster_bytes(
                "我的一百部电影审美坐标",
                ranked,
                "测试用户",
                "银幕红",
                share_url="https://example.com/list",
                include_qr=True,
            )
        poster_fetch.assert_not_called()
        with Image.open(BytesIO(poster_bytes)) as image:
            self.assertEqual("PNG", image.format)
            self.assertEqual((1800, 2400), image.size)
            self.assertEqual("RGB", image.mode)

    def test_actual_top_n_scope_is_not_inflated(self) -> None:
        self.assertEqual("Top 8", result_poster_scope(8, 8, 100))
        self.assertEqual("Top 100 · 完整结果共 120 名", result_poster_scope(100, 120, 100))
        self.assertEqual("暂无排名", result_poster_scope(0, 0, 100))


if __name__ == "__main__":
    unittest.main()
