from __future__ import annotations

from typing import Dict, List, Optional


HERO_TITLE = "慢慢排出你的电影审美名单"
HERO_SUBTITLE = "不必一次想清全部顺序，只在两部电影之间作一次取舍。"
HERO_TAGLINE = "几分钟后，留下一份更接近自己的观影片单。"

FILM_CHALLENGE_TEMPLATES: List[Dict[str, object]] = [
    {
        "id": "douban-top50",
        "name": "豆瓣高分片单",
        "theme": "我的豆瓣高分电影名单",
        "tagline": "从大众高分片里，看见自己的审美底色。",
        "top_k": 10,
        "seed_text": "douban-top50-v1",
        "source": "builtin",
        "badge": "初次整理",
        "recommendation": "适合第一次玩，或想从经典高分片里排出一份个人总榜的用户。",
        "card_poster_title": "肖申克的救赎",
        "card_poster_asset": "assets/builtin_list_thumbnails/douban-top50.webp",
        "items": [
            "肖申克的救赎", "霸王别姬", "阿甘正传", "泰坦尼克号", "这个杀手不太冷",
            "美丽人生", "千与千寻", "辛德勒的名单", "盗梦空间", "忠犬八公的故事",
            "星际穿越", "楚门的世界", "海上钢琴师", "三傻大闹宝莱坞", "机器人总动员",
            "放牛班的春天", "大话西游之大圣娶亲", "疯狂动物城", "无间道", "熔炉",
            "教父", "当幸福来敲门", "龙猫", "怦然心动", "触不可及",
            "控方证人", "蝙蝠侠：黑暗骑士", "活着", "末代皇帝", "乱世佳人",
            "寻梦环游记", "指环王3：王者无敌", "何以为家", "飞屋环游记", "十二怒汉",
            "素媛", "摔跤吧！爸爸", "哈尔的移动城堡", "少年派的奇幻漂流", "鬼子来了",
            "让子弹飞", "天堂电影院", "猫鼠游戏", "钢琴家", "闻香识女人",
            "天空之城", "罗马假日", "大闹天宫", "死亡诗社", "绿皮书",
        ],
    },
    {
        "id": "nolan",
        "name": "诺兰作品序列",
        "theme": "我的诺兰电影名单",
        "tagline": "在时间、梦境与黑夜之间，排出自己的顺序。",
        "top_k": 8,
        "seed_text": "nolan-v1",
        "source": "builtin",
        "badge": "导演",
        "recommendation": "适合诺兰粉丝，想认真比较《盗梦空间》《星际穿越》和《奥本海默》的用户。",
        "card_poster_title": "星际穿越",
        "card_poster_asset": "assets/builtin_list_thumbnails/nolan.webp",
        "items": [
            "追随", "记忆碎片", "失眠症", "蝙蝠侠：侠影之谜", "致命魔术", "蝙蝠侠：黑暗骑士",
            "盗梦空间", "蝙蝠侠：黑暗骑士崛起", "星际穿越", "敦刻尔克", "信条", "奥本海默",
        ],
    },
    {
        "id": "miyazaki",
        "name": "宫崎骏动画手记",
        "theme": "我的宫崎骏动画名单",
        "tagline": "在风、飞行与温柔里，慢慢看见答案。",
        "top_k": 8,
        "seed_text": "miyazaki-v1",
        "source": "builtin",
        "badge": "动画",
        "recommendation": "适合宫崎骏粉丝，想把童年、飞行、温柔和冒险排出自己顺序的用户。",
        "card_poster_title": "千与千寻",
        "card_poster_asset": "assets/builtin_list_thumbnails/miyazaki.webp",
        "items": [
            "风之谷", "天空之城", "龙猫", "魔女宅急便", "红猪", "幽灵公主",
            "千与千寻", "哈尔的移动城堡", "悬崖上的金鱼姬", "起风了", "你想活出怎样的人生",
        ],
    },
    {
        "id": "shinkai",
        "name": "新海诚动画电影榜",
        "theme": "我的新海诚动画电影榜",
        "tagline": "在天空、距离和重逢之间，排出自己的新海诚顺序。",
        "top_k": 8,
        "seed_text": "shinkai-v1",
        "source": "builtin",
        "badge": "动画",
        "recommendation": "适合新海诚粉丝，把从早期短长片到《铃芽之旅》的喜欢程度一次排清楚。",
        "card_poster_title": "你的名字。",
        "card_poster_asset": "assets/builtin_list_thumbnails/shinkai.webp",
        "items": [
            "星之声", "云之彼端，约定的地方", "秒速5厘米", "追逐繁星的孩子",
            "言叶之庭", "你的名字。", "天气之子", "铃芽之旅",
        ],
    },
    {
        "id": "chinese-highscore",
        "name": "华语高分片单",
        "theme": "我的华语电影名单",
        "tagline": "把那些重要的华语电影，排成一份私人次序。",
        "top_k": 10,
        "seed_text": "chinese-highscore-v1",
        "source": "builtin",
        "badge": "华语",
        "recommendation": "适合华语电影爱好者，想排出自己的华语高分总榜或年度补片清单。",
        "card_poster_title": "霸王别姬",
        "card_poster_asset": "assets/builtin_list_thumbnails/chinese-highscore.webp",
        "items": [
            "霸王别姬", "活着", "无间道", "大话西游之大圣娶亲", "让子弹飞", "鬼子来了",
            "饮食男女", "牯岭街少年杀人事件", "阳光灿烂的日子", "花样年华", "一一",
            "悲情城市", "喜宴", "甜蜜蜜", "卧虎藏龙", "重庆森林", "春光乍泄", "芙蓉镇",
            "我不是药神", "哪吒之魔童降世",
        ],
    },
    {
        "id": "wong-kar-wai",
        "name": "王家卫电影榜",
        "theme": "我的王家卫电影榜",
        "tagline": "在霓虹、时间和错过里，排出自己的王家卫顺序。",
        "top_k": 10,
        "seed_text": "wong-kar-wai-v1",
        "source": "builtin",
        "badge": "导演",
        "recommendation": "适合王家卫影迷，把《重庆森林》《花样年华》和《春光乍泄》等作品排成个人序列。",
        "card_poster_title": "花样年华",
        "card_poster_asset": "assets/builtin_list_thumbnails/wong-kar-wai.webp",
        "items": [
            "旺角卡门", "阿飞正传", "重庆森林", "东邪西毒", "堕落天使",
            "春光乍泄", "花样年华", "2046", "蓝莓之夜", "一代宗师",
        ],
    },
    {
        "id": "disney-animation",
        "name": "迪士尼动画长片榜",
        "theme": "我的迪士尼动画长片榜",
        "tagline": "从公主、冒险到动物城，排出自己的迪士尼动画 Top 10。",
        "top_k": 10,
        "seed_text": "disney-animation-v1",
        "source": "builtin",
        "badge": "迪士尼",
        "recommendation": "适合迪士尼动画粉丝，只整理华特迪士尼动画工作室长片，不混入皮克斯和真人版。",
        "card_poster_title": "疯狂动物城",
        "card_poster_asset": "assets/builtin_list_thumbnails/disney-animation.webp",
        "items": [
            "白雪公主和七个小矮人", "灰姑娘", "睡美人", "小美人鱼", "美女与野兽",
            "阿拉丁", "狮子王", "花木兰", "星际宝贝", "公主与青蛙",
            "魔发奇缘", "无敌破坏王", "冰雪奇缘", "超能陆战队", "疯狂动物城",
            "海洋奇缘", "寻龙传说", "魔法满屋", "海洋奇缘2", "疯狂动物城2",
        ],
    },
    {
        "id": "couple-debate",
        "name": "两个人的观影名单",
        "theme": "我们的观影名单",
        "tagline": "不是测默契，只是看看两个人如何喜欢同一批电影。",
        "top_k": 8,
        "seed_text": "couple-debate-v1",
        "source": "builtin",
        "badge": "双人",
        "recommendation": "适合和朋友、伴侣一起玩，看同一批电影在两个人心里的差异。",
        "card_poster_title": "泰坦尼克号",
        "card_poster_asset": "assets/builtin_list_thumbnails/couple-debate.webp",
        "items": [
            "爱在黎明破晓前", "爱在日落黄昏时", "怦然心动", "花束般的恋爱", "消失的爱人",
            "婚姻故事", "泰坦尼克号", "时空恋旅人", "恋恋笔记本", "重庆森林", "春光乍泄",
            "甜蜜蜜", "一天", "她", "蓝色情人节",
        ],
    },
]


def get_template(template_id: str) -> Optional[Dict[str, object]]:
    for template in FILM_CHALLENGE_TEMPLATES:
        if template["id"] == template_id:
            return template
    return None


def result_share_caption(
    *,
    app_title: str,
    theme: str,
    ranked: List[str],
    comparisons: int,
    challenge_url: str,
    seed_text: str,
) -> str:
    top_items = ranked[: min(8, len(ranked))]
    lines = [
        f"我用「{app_title}」慢慢排出了一份电影名单。",
        f"片单：{theme}",
        "",
        "前几名是：",
    ]
    lines.extend(f"{idx}. {item}" for idx, item in enumerate(top_items, 1))
    if len(ranked) > len(top_items):
        lines.append(f"...还有 {len(ranked) - len(top_items)} 部电影")
    lines.append("")
    lines.append(f"这份名单经过 {comparisons} 次取舍生成。")
    if seed_text:
        lines.append(f"顺序口令：{seed_text}")
    if challenge_url:
        lines.append(f"也排同一份片单：{challenge_url}")
    else:
        lines.append("也排同一份片单，看看我们的喜欢如何相同又不同。")
    return "\n".join(lines)


def challenge_share_caption(theme: str, challenge_url: str) -> str:
    return "\n".join(
        [
            f"我留了一份电影片单：{theme}",
            "每次只在两部电影之间作一次取舍，最后会得到自己的顺序。",
            f"片单链接：{challenge_url}",
        ]
    )


RESUME_BULLETS = [
    "独立开发并上线影视偏好排序 Web App，设计同一片单链接与匿名事件漏斗，支持用户通过连续取舍完成电影名单整理与社交分享。",
    "接入 Supabase REST API 采集匿名 page_view/start/complete/share 事件，用数据追踪完成率、分享率和热门片单。",
    "围绕影视爱好者场景优化首屏、移动端取舍体验和分享海报，形成从片单链接到结果分享的完整增长闭环。",
]


LAUNCH_CHECKLIST = [
    "部署 Streamlit Community Cloud，配置 PUBLIC_APP_URL、SUPABASE_URL、SUPABASE_ANON_KEY、ADMIN_DASHBOARD_TOKEN。",
    "先发 5 个内置片单链接，让朋友用同一份片单生成第一批结果。",
    "第 1 周每天截图一次后台漏斗，记录访问、开始、完成、复制分享四个指标。",
    "挑选 3 条用户反馈和 2 张结果海报，放进 README 和简历项目说明。",
]
