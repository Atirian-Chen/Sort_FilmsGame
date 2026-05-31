from __future__ import annotations

from typing import Dict, List, Optional


HERO_TITLE = "慢慢排出你的电影审美名单"
HERO_SUBTITLE = "不用一口气想清楚全部排名，只在每一组里选更喜欢的那一部。"
HERO_TAGLINE = "最后得到一张温柔、准确、能分享的私人片单。"

FILM_CHALLENGE_TEMPLATES: List[Dict[str, object]] = [
    {
        "id": "douban-top50",
        "name": "豆瓣 Top 50",
        "theme": "我的豆瓣 Top 50 电影审美榜",
        "tagline": "从国民高分片里排出你的审美底色。",
        "top_k": 10,
        "seed_text": "douban-top50-v1",
        "source": "builtin",
        "badge": "适合第一次",
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
        "name": "诺兰电影偏爱榜",
        "theme": "我的诺兰电影偏爱榜",
        "tagline": "从时间、梦境和黑夜里，找到你最偏爱的那一部。",
        "top_k": 8,
        "seed_text": "nolan-v1",
        "source": "builtin",
        "badge": "导演专题",
        "items": [
            "追随", "记忆碎片", "失眠症", "蝙蝠侠：侠影之谜", "致命魔术", "蝙蝠侠：黑暗骑士",
            "盗梦空间", "蝙蝠侠：黑暗骑士崛起", "星际穿越", "敦刻尔克", "信条", "奥本海默",
        ],
    },
    {
        "id": "miyazaki",
        "name": "宫崎骏动画榜",
        "theme": "我的宫崎骏动画偏爱榜",
        "tagline": "在风、飞行和温柔里，慢慢看见自己的答案。",
        "top_k": 8,
        "seed_text": "miyazaki-v1",
        "source": "builtin",
        "badge": "温柔向",
        "items": [
            "风之谷", "天空之城", "龙猫", "魔女宅急便", "红猪", "幽灵公主",
            "千与千寻", "哈尔的移动城堡", "悬崖上的金鱼姬", "起风了", "你想活出怎样的人生",
        ],
    },
    {
        "id": "chinese-highscore",
        "name": "华语高分电影榜",
        "theme": "我的华语高分电影偏爱榜",
        "tagline": "把心里那些重要的华语电影，排成一张名单。",
        "top_k": 10,
        "seed_text": "chinese-highscore-v1",
        "source": "builtin",
        "badge": "华语片",
        "items": [
            "霸王别姬", "活着", "无间道", "大话西游之大圣娶亲", "让子弹飞", "鬼子来了",
            "饮食男女", "牯岭街少年杀人事件", "阳光灿烂的日子", "花样年华", "一一",
            "悲情城市", "喜宴", "甜蜜蜜", "卧虎藏龙", "重庆森林", "春光乍泄", "芙蓉镇",
            "我不是药神", "哪吒之魔童降世",
        ],
    },
    {
        "id": "couple-debate",
        "name": "双人观影分歧榜",
        "theme": "我们的观影分歧片单",
        "tagline": "不是测默契，只是看看两个人的喜欢如何不同。",
        "top_k": 8,
        "seed_text": "couple-debate-v1",
        "source": "builtin",
        "badge": "双人片单",
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
        f"别再问我最喜欢哪部电影了，我用「{app_title}」排出来了。",
        f"片单：{theme}",
        "",
        "我的电影审美名片：",
    ]
    lines.extend(f"{idx}. {item}" for idx, item in enumerate(top_items, 1))
    if len(ranked) > len(top_items):
        lines.append(f"...还有 {len(ranked) - len(top_items)} 个排名")
    lines.append("")
    lines.append(f"这份榜单经过 {comparisons} 次二选一生成。")
    if seed_text:
        lines.append(f"对局口令：{seed_text}")
    if challenge_url:
        lines.append(f"也排同一份片单：{challenge_url}")
    else:
        lines.append("也排同一份片单，看看我们的喜欢如何相同又不同。")
    return "\n".join(lines)


def challenge_share_caption(theme: str, challenge_url: str) -> str:
    return "\n".join(
        [
            f"我整理了一份电影审美片单：{theme}",
            "规则很简单：每次只在两部电影里选更喜欢的那一部。",
            f"入口：{challenge_url}",
        ]
    )


RESUME_BULLETS = [
    "独立开发并上线影视偏好排序 Web App，设计同题片单入口与匿名事件漏斗，支持用户完成 1v1 电影榜单排序与社交分享。",
    "接入 Supabase REST API 采集匿名 page_view/start/complete/share 事件，用数据追踪完成率、分享率和热门片单。",
    "围绕影视爱好者场景优化首屏、移动端对决体验和分享海报，形成从片单入口到结果传播的完整增长闭环。",
]


LAUNCH_CHECKLIST = [
    "部署 Streamlit Community Cloud，配置 PUBLIC_APP_URL、SUPABASE_URL、SUPABASE_ANON_KEY、ADMIN_DASHBOARD_TOKEN。",
    "先发 5 个内置片单入口，让朋友用同一份片单生成第一批结果。",
    "第 1 周每天截图一次后台漏斗，记录访问、开局、完成、复制分享四个指标。",
    "挑选 3 条用户反馈和 2 张结果海报，放进 README 和简历项目说明。",
]
