from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from merged_douban_ranker_v3 import generate_top100_poster_bytes


FILMS = [
    "花样年华",
    "一一",
    "2001太空漫游",
    "霸王别姬",
    "东京物语",
    "潜行者",
    "牯岭街少年杀人事件",
    "七武士",
    "教父",
    "千与千寻",
    "大地之歌",
    "天堂电影院",
    "杀人回忆",
    "红辣椒",
    "美丽人生",
    "窃听风暴",
    "燃烧",
    "一次别离",
    "悲情城市",
    "辛德勒的名单",
    "肖申克的救赎",
    "现代启示录",
    "活着",
    "永恒和一日",
    "切腹",
    "站台",
    "城市之光",
    "美国往事",
    "熔炉",
    "这个杀手不太冷",
    "鬼子来了",
    "罗生门",
    "上帝之城",
    "老男孩",
    "何处是我朋友的家",
    "低俗小说",
    "小偷家族",
    "无人知晓",
    "密阳",
    "特写",
    "蓝白红三部曲之红",
    "四百击",
    "八部半",
    "偷自行车的人",
    "日落大道",
    "迷魂记",
    "好家伙",
    "血色将至",
    "飞越疯人院",
    "十二怒汉",
    "星际穿越",
    "黑客帝国",
    "指环王3：王者无敌",
    "蝙蝠侠：黑暗骑士",
    "寄生虫",
    "楚门的世界",
    "搏击俱乐部",
    "钢琴家",
    "末代皇帝",
    "生之欲",
    "晚春",
    "楢山节考",
    "阳光灿烂的日子",
    "恐怖分子",
    "春夏秋冬又一春",
    "共同警备区",
    "樱桃的滋味",
    "天堂的孩子",
    "冬眠",
    "野梨树",
    "焦土之城",
    "狩猎",
    "海边的曼彻斯特",
    "酒精计划",
    "中央车站",
    "荒蛮故事",
    "坠落的审判",
    "驾驶我的车",
    "偶然与想象",
    "完美的日子",
    "奥本海默",
    "疯狂的麦克斯4：狂暴之路",
    "蜘蛛侠：平行宇宙",
    "机器人总动员",
    "萤火虫之墓",
    "幽灵公主",
    "头脑特工队",
    "寻梦环游记",
    "爆裂鼓手",
    "布达佩斯大饭店",
    "指环王1：护戒使者",
    "星球大战5：帝国反击战",
    "入殓师",
    "筋疲力尽",
    "大路",
    "阿尔及尔之战",
    "何以为家",
    "浪潮",
    "蜂鸟",
    "盗梦空间",
]


def main() -> None:
    if len(FILMS) != 100 or len(set(FILMS)) != 100:
        raise ValueError("The promotional list must contain 100 unique films")

    output_path = Path(__file__).with_name("top100_feature_poster.png")
    output_path.write_bytes(
        generate_top100_poster_bytes(
            "林屿的私人电影 Top 100",
            FILMS,
            "林屿",
            "银幕红",
            share_url="https://sortfilmsgamegit.streamlit.app/",
            include_qr=True,
        )
    )
    print(output_path)


if __name__ == "__main__":
    main()
