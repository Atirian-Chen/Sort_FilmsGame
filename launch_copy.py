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
        "items": [
            "风之谷", "天空之城", "龙猫", "魔女宅急便", "红猪", "幽灵公主",
            "千与千寻", "哈尔的移动城堡", "悬崖上的金鱼姬", "起风了", "你想活出怎样的人生",
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
        "items": [
            "霸王别姬", "活着", "无间道", "大话西游之大圣娶亲", "让子弹飞", "鬼子来了",
            "饮食男女", "牯岭街少年杀人事件", "阳光灿烂的日子", "花样年华", "一一",
            "悲情城市", "喜宴", "甜蜜蜜", "卧虎藏龙", "重庆森林", "春光乍泄", "芙蓉镇",
            "我不是药神", "哪吒之魔童降世",
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
