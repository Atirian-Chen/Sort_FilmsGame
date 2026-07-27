from __future__ import annotations

from typing import Any, Dict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


LANG_ZH = "zh"
LANG_EN = "en"

ENGLISH_HOME_TEMPLATE_IDS = (
    "nolan",
    "miyazaki",
    "shinkai",
    "disney-animation",
    "couple-debate",
    "douban-top50",
)

ENGLISH_TEMPLATE_COPY: Dict[str, Dict[str, str]] = {
    "douban-top50": {
        "name": "Douban Top-Rated Movies",
        "theme": "My Top-Rated Movie List",
        "tagline": "Start with modern classics and discover your own order.",
        "badge": "Classics",
        "recommendation": "A broad starter list for building a personal all-time ranking.",
    },
    "nolan": {
        "name": "Christopher Nolan Ranked",
        "theme": "My Christopher Nolan Ranking",
        "tagline": "Time, dreams and spectacle—put Nolan's films in your order.",
        "badge": "Director",
        "recommendation": "For comparing Inception, Interstellar, Oppenheimer and the rest.",
    },
    "miyazaki": {
        "name": "Hayao Miyazaki Ranked",
        "theme": "My Hayao Miyazaki Ranking",
        "tagline": "Wind, flight and wonder—find the films that stay with you.",
        "badge": "Animation",
        "recommendation": "For Studio Ghibli fans ready to make the difficult choices.",
    },
    "shinkai": {
        "name": "Makoto Shinkai Ranked",
        "theme": "My Makoto Shinkai Ranking",
        "tagline": "Distance, skies and reunion—rank Shinkai's animated films.",
        "badge": "Animation",
        "recommendation": "From Voices of a Distant Star to Suzume in one personal order.",
    },
    "disney-animation": {
        "name": "Disney Animation Ranked",
        "theme": "My Disney Animation Ranking",
        "tagline": "From fairy tales to Zootopia, build your Disney Animation Top 10.",
        "badge": "Animation",
        "recommendation": "Walt Disney Animation Studios features only—no Pixar or remakes.",
    },
    "couple-debate": {
        "name": "Movies for Two",
        "theme": "Our Movies for Two Ranking",
        "tagline": "Not a compatibility test—just two tastes meeting the same films.",
        "badge": "Together",
        "recommendation": "Great with a partner or friend: rank the same list and compare.",
    },
}


ENGLISH_MOVIE_TITLES: Dict[str, str] = {
    "肖申克的救赎": "The Shawshank Redemption",
    "霸王别姬": "Farewell My Concubine",
    "阿甘正传": "Forrest Gump",
    "泰坦尼克号": "Titanic",
    "这个杀手不太冷": "Léon: The Professional",
    "美丽人生": "Life Is Beautiful",
    "千与千寻": "Spirited Away",
    "辛德勒的名单": "Schindler's List",
    "盗梦空间": "Inception",
    "忠犬八公的故事": "Hachi: A Dog's Tale",
    "星际穿越": "Interstellar",
    "楚门的世界": "The Truman Show",
    "海上钢琴师": "The Legend of 1900",
    "三傻大闹宝莱坞": "3 Idiots",
    "机器人总动员": "WALL·E",
    "放牛班的春天": "The Chorus",
    "大话西游之大圣娶亲": "A Chinese Odyssey Part Two: Cinderella",
    "疯狂动物城": "Zootopia",
    "无间道": "Infernal Affairs",
    "熔炉": "Silenced",
    "教父": "The Godfather",
    "当幸福来敲门": "The Pursuit of Happyness",
    "龙猫": "My Neighbor Totoro",
    "怦然心动": "Flipped",
    "触不可及": "The Intouchables",
    "控方证人": "Witness for the Prosecution",
    "蝙蝠侠：黑暗骑士": "The Dark Knight",
    "活着": "To Live",
    "末代皇帝": "The Last Emperor",
    "乱世佳人": "Gone with the Wind",
    "寻梦环游记": "Coco",
    "指环王3：王者无敌": "The Lord of the Rings: The Return of the King",
    "何以为家": "Capernaum",
    "飞屋环游记": "Up",
    "十二怒汉": "12 Angry Men",
    "素媛": "Hope",
    "摔跤吧！爸爸": "Dangal",
    "哈尔的移动城堡": "Howl's Moving Castle",
    "少年派的奇幻漂流": "Life of Pi",
    "鬼子来了": "Devils on the Doorstep",
    "让子弹飞": "Let the Bullets Fly",
    "天堂电影院": "Cinema Paradiso",
    "猫鼠游戏": "Catch Me If You Can",
    "钢琴家": "The Pianist",
    "闻香识女人": "Scent of a Woman",
    "天空之城": "Castle in the Sky",
    "罗马假日": "Roman Holiday",
    "大闹天宫": "Havoc in Heaven",
    "死亡诗社": "Dead Poets Society",
    "绿皮书": "Green Book",
    "追随": "Following",
    "记忆碎片": "Memento",
    "失眠症": "Insomnia",
    "蝙蝠侠：侠影之谜": "Batman Begins",
    "致命魔术": "The Prestige",
    "蝙蝠侠：黑暗骑士崛起": "The Dark Knight Rises",
    "敦刻尔克": "Dunkirk",
    "信条": "Tenet",
    "奥本海默": "Oppenheimer",
    "风之谷": "Nausicaä of the Valley of the Wind",
    "魔女宅急便": "Kiki's Delivery Service",
    "红猪": "Porco Rosso",
    "幽灵公主": "Princess Mononoke",
    "悬崖上的金鱼姬": "Ponyo",
    "起风了": "The Wind Rises",
    "你想活出怎样的人生": "The Boy and the Heron",
    "星之声": "Voices of a Distant Star",
    "云之彼端，约定的地方": "The Place Promised in Our Early Days",
    "秒速5厘米": "5 Centimeters per Second",
    "追逐繁星的孩子": "Children Who Chase Lost Voices",
    "言叶之庭": "The Garden of Words",
    "你的名字。": "Your Name.",
    "天气之子": "Weathering with You",
    "铃芽之旅": "Suzume",
    "白雪公主和七个小矮人": "Snow White and the Seven Dwarfs",
    "灰姑娘": "Cinderella",
    "睡美人": "Sleeping Beauty",
    "小美人鱼": "The Little Mermaid",
    "美女与野兽": "Beauty and the Beast",
    "阿拉丁": "Aladdin",
    "狮子王": "The Lion King",
    "花木兰": "Mulan",
    "星际宝贝": "Lilo & Stitch",
    "公主与青蛙": "The Princess and the Frog",
    "魔发奇缘": "Tangled",
    "无敌破坏王": "Wreck-It Ralph",
    "冰雪奇缘": "Frozen",
    "超能陆战队": "Big Hero 6",
    "海洋奇缘": "Moana",
    "寻龙传说": "Raya and the Last Dragon",
    "魔法满屋": "Encanto",
    "海洋奇缘2": "Moana 2",
    "疯狂动物城2": "Zootopia 2",
    "爱在黎明破晓前": "Before Sunrise",
    "爱在日落黄昏时": "Before Sunset",
    "花束般的恋爱": "We Made a Beautiful Bouquet",
    "消失的爱人": "Gone Girl",
    "婚姻故事": "Marriage Story",
    "时空恋旅人": "About Time",
    "恋恋笔记本": "The Notebook",
    "重庆森林": "Chungking Express",
    "春光乍泄": "Happy Together",
    "甜蜜蜜": "Comrades: Almost a Love Story",
    "一天": "One Day",
    "她": "Her",
    "蓝色情人节": "Blue Valentine",
}


def normalize_language(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("_", "-")
    return LANG_EN if normalized == "en" or normalized.startswith("en-") else LANG_ZH


def is_english_language(language: Any) -> bool:
    return normalize_language(language) == LANG_EN


def translate_movie_title(title: Any, language: Any) -> str:
    text = str(title or "")
    if not is_english_language(language):
        return text
    return ENGLISH_MOVIE_TITLES.get(text, text)


def translate_template_field(template: Dict[str, object], field: str, language: Any) -> str:
    value = str(template.get(field) or "")
    if not is_english_language(language):
        return value
    translated = ENGLISH_TEMPLATE_COPY.get(str(template.get("id") or ""), {}).get(field)
    return str(translated or value)


def translate_theme(theme: Any, template_id: Any, language: Any) -> str:
    text = str(theme or "")
    if not is_english_language(language):
        return text
    translated = ENGLISH_TEMPLATE_COPY.get(str(template_id or ""), {}).get("theme")
    return str(translated or text)


def with_language_param(url: str, language: Any) -> str:
    if not is_english_language(language):
        return str(url or "")
    parts = urlsplit(str(url or ""))
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["lang"] = LANG_EN
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
