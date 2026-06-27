from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Optional

import streamlit as st


# 新增 A/B 实验时，优先只改这里：
# 1. 复制一个实验配置块
# 2. 改 experiment_id、实验名称、流量比例和 variants
# 3. 在对应页面/功能里用 get_experiment_config(session_id, experiment_id) 读取 config
EXPERIMENTS: List[Dict[str, Any]] = [
    {
        "experiment_id": "post_render_hero_value_v1",
        "experiment_name": "渲染后首屏价值表达实验",
        "status": "active",  # active / paused
        "traffic_allocation": 1.0,
        "started_at": "2026-06-27T03:08:50+08:00",
        "primary_metric": "exposed_action_rate",
        "description": "测试更明确的结果预览是否能提升首页内容渲染后的打开/选择片单率。",
        "variants": [
            {
                "variant_id": "control",
                "variant_name": "原首屏表达",
                "weight": 1,
                "config": {
                    "hero_title": "慢慢排出你的电影审美名单",
                    "hero_subtitle": "不必一次想清全部顺序，只在两部电影之间作一次取舍。",
                    "hero_tagline": "几分钟后，留下一份更接近自己的观影片单。",
                    "hero_outcomes": [
                        "得到一份 Top 榜单",
                        "看见你的冠军电影",
                        "生成结果海报",
                        "复制链接给朋友同题挑战",
                    ],
                },
            },
            {
                "variant_id": "outcome_preview",
                "variant_name": "结果预览表达",
                "weight": 1,
                "config": {
                    "hero_title": "先选几次，得到你的电影 Top 榜",
                    "hero_subtitle": "不用先准备完整片单，从一份现成主题开始也可以。",
                    "hero_tagline": "完成后会生成冠军、Top 排名、海报和可分享链接。",
                    "hero_outcomes": [
                        "先从现成片单开始",
                        "每次只做二选一",
                        "直接看到冠军电影",
                        "带走海报和分享链接",
                    ],
                },
            },
        ],
    },
    {
        "experiment_id": "quick_list_card_framing_v1",
        "experiment_name": "快速片单卡片行动框架实验",
        "status": "active",
        "traffic_allocation": 1.0,
        "started_at": "2026-06-27T03:08:50+08:00",
        "primary_metric": "exposed_action_rate",
        "description": "测试把快速片单卡片从“推荐说明”改成“低成本行动提示”是否提升卡片打开率和渲染后行动率。",
        "variants": [
            {
                "variant_id": "control",
                "variant_name": "推荐理由 + 开始整理",
                "weight": 1,
                "config": {
                    "card_reason_label": "推荐理由",
                    "card_recommendation_prefix": "",
                    "card_meta_template": "{count} 部电影 · 前 {top_k} 名",
                    "card_action_text": "开始整理",
                },
            },
            {
                "variant_id": "low_friction",
                "variant_name": "低成本行动提示",
                "weight": 1,
                "config": {
                    "card_reason_label": "适合现在开始",
                    "card_recommendation_prefix": "如果暂时没有自己的片单，",
                    "card_meta_template": "{count} 部电影 · 只排前 {top_k} 名",
                    "card_action_text": "先排 Top {top_k}",
                },
            },
        ],
    },
    {
        "experiment_id": "douban_collect_entry_cta_v1",
        "experiment_name": "豆瓣已看入口 CTA 降成本实验",
        "status": "active",
        "traffic_allocation": 1.0,
        "started_at": "2026-06-27T03:08:50+08:00",
        "primary_metric": "exposed_action_rate",
        "description": "测试把豆瓣已看入口改成更明确的下一步提示，是否提升用户从首页进入配置页的比例。",
        "variants": [
            {
                "variant_id": "control",
                "variant_name": "总榜叙事",
                "weight": 1,
                "config": {
                    "collect_kicker": "主推功能 · 豆瓣已看总榜",
                    "collect_title": "把你看过的电影排成私人总榜",
                    "collect_copy": "适合想排出自己总榜单、年度榜单或某个阶段观影坐标的用户。输入豆瓣 ID，读取公开的“看过”电影，再用一轮轮二选一整理出总榜或 Top N。",
                    "collect_note_html": "可只排 Top N<br>也可整理完整总榜",
                    "collect_cta_text": "开始整理",
                    "collect_hint": "只读取公开可访问的“看过”页面；可以只排 Top N，也可以整理完整总榜。",
                },
            },
            {
                "variant_id": "next_step",
                "variant_name": "下一步低门槛提示",
                "weight": 1,
                "config": {
                    "collect_kicker": "主推功能 · 只需要豆瓣 ID",
                    "collect_title": "从已看电影里先排出一个 Top N",
                    "collect_copy": "下一步输入公开豆瓣 ID，先预览候选电影，再决定只排 Top N 还是整理完整总榜。",
                    "collect_note_html": "先预览候选<br>再开始整理",
                    "collect_cta_text": "用豆瓣已看开始",
                    "collect_hint": "下一步可以先预览候选电影，确认片单后再开始整理。",
                },
            },
        ],
    },
    {
        "experiment_id": "home_zero_decision_start_v1",
        "experiment_name": "首页零决策开排实验",
        "status": "active",
        "traffic_allocation": 1.0,
        "started_at": "2026-06-27T20:56:19+08:00",
        "primary_metric": "exposed_action_rate",
        "description": "测试在首页提供无需选择片单的一键开排入口，是否提升渲染后打开/开始整理率。",
        "variants": [
            {
                "variant_id": "control",
                "variant_name": "不显示零决策入口",
                "weight": 1,
                "config": {
                    "show_zero_decision_start": False,
                },
            },
            {
                "variant_id": "direct_start_strip",
                "variant_name": "零决策开排横条",
                "weight": 1,
                "config": {
                    "show_zero_decision_start": True,
                    "zero_decision_title": "不知道排哪份？直接开一局",
                    "zero_decision_copy": "系统会从适合快速开始的片单里为你稳定挑一份，同一个会话刷新也不会变。",
                    "zero_decision_cta": "现在开排",
                    "zero_decision_template_ids": [
                        "douban-top50",
                        "miyazaki",
                        "nolan",
                        "chinese-highscore",
                        "couple-debate",
                    ],
                },
            },
        ],
    },
    {
        "experiment_id": "home_duel_teaser_v1",
        "experiment_name": "首页先试一题二选一实验",
        "status": "active",
        "traffic_allocation": 1.0,
        "started_at": "2026-06-27T20:56:19+08:00",
        "primary_metric": "exposed_action_rate",
        "description": "测试在首页先给一组二选一，让用户先完成一个轻量选择再进入片单，是否提升渲染后行动率。",
        "variants": [
            {
                "variant_id": "control",
                "variant_name": "不显示试看题",
                "weight": 1,
                "config": {
                    "show_duel_teaser": False,
                },
            },
            {
                "variant_id": "first_choice",
                "variant_name": "首页先试一题",
                "weight": 1,
                "config": {
                    "show_duel_teaser": True,
                    "duel_teaser_title": "先试一题：你更想把谁排前面？",
                    "duel_teaser_copy": "点任意一边就进入同一份豆瓣高分片单，后面继续用二选一排出你的 Top 榜。",
                    "duel_teaser_template_id": "douban-top50",
                    "duel_teaser_left": "千与千寻",
                    "duel_teaser_right": "星际穿越",
                },
            },
        ],
    },
    {
        "experiment_id": "homepage_cta_v1",
        "experiment_name": "首页首屏标题与 CTA 实验",
        "status": "paused",  # active / paused
        "traffic_allocation": 1.0,
        "description": "测试不同首屏价值表达对开始整理率的影响。",
        "variants": [
            {
                "variant_id": "control",
                "variant_name": "原始表达",
                "weight": 1,
                "config": {
                    "hero_title": "生成你的电影审美榜单",
                    "cta_text": "开始整理",
                },
            },
            {
                "variant_id": "quick_start",
                "variant_name": "快速收益表达",
                "weight": 1,
                "config": {
                    "hero_title": "用 3 分钟生成你的私人电影 Top 榜",
                    "cta_text": "生成我的 Top 榜",
                },
            },
        ],
    },
    {
        "experiment_id": "home_layout_order_v1",
        "experiment_name": "首页片单入口顺序实验",
        "status": "paused",
        "traffic_allocation": 1.0,
        "started_at": "2026-06-12T02:12:39+08:00",
        "ended_at": "2026-06-25T18:22:38+08:00",
        "decision_variant_id": "builtin_first",
        "description": "测试快速开始片单前置是否比豆瓣已看主推前置更能提升开始整理率。",
        "variants": [
            {
                "variant_id": "control",
                "variant_name": "豆瓣已看主推前置",
                "weight": 1,
                "config": {
                    "home_layout_order": "current",
                },
            },
            {
                "variant_id": "builtin_first",
                "variant_name": "快速片单前置",
                "weight": 1,
                "config": {
                    "home_layout_order": "builtin_first",
                },
            },
        ],
    },
    {
        "experiment_id": "builtin_card_poster_v1",
        "experiment_name": "首页内置片单卡片海报实验",
        "status": "paused",
        "traffic_allocation": 1.0,
        "started_at": "2026-06-23T22:34:11+08:00",
        "ended_at": "2026-06-25T18:22:38+08:00",
        "decision_variant_id": "poster",
        "description": "测试预制代表电影海报是否能提升内置轻量片单打开率。",
        "variants": [
            {
                "variant_id": "control",
                "variant_name": "纯文字卡片",
                "weight": 1,
                "config": {
                    "show_builtin_card_posters": False,
                },
            },
            {
                "variant_id": "poster",
                "variant_name": "大众电影海报",
                "weight": 1,
                "config": {
                    "show_builtin_card_posters": True,
                },
            },
        ],
    }
]


def _stable_ratio(value: str) -> float:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(16**12 - 1)


def list_experiments(*, active_only: bool = False) -> List[Dict[str, Any]]:
    if not active_only:
        return [dict(experiment) for experiment in EXPERIMENTS]
    return [dict(experiment) for experiment in EXPERIMENTS if experiment.get("status") == "active"]


def get_experiment(experiment_id: str) -> Dict[str, Any]:
    for experiment in EXPERIMENTS:
        if experiment.get("experiment_id") == experiment_id:
            return experiment
    return {}


def _variant_bucket(variants: List[Dict[str, Any]], bucket: float) -> Dict[str, Any]:
    weighted: List[Dict[str, Any]] = []
    total_weight = 0.0
    for variant in variants:
        if not variant.get("variant_id"):
            continue
        weight = float(variant.get("weight", 1) or 0)
        if weight <= 0:
            continue
        total_weight += weight
        weighted.append({**variant, "_upper": total_weight})

    if not weighted or total_weight <= 0:
        return {}

    target = bucket * total_weight
    for variant in weighted:
        if target <= float(variant["_upper"]):
            return variant
    return weighted[-1]


def experiment_query_param_name(experiment_id: str) -> str:
    safe_id = "".join(char for char in str(experiment_id) if char.isalnum() or char in {"_", "-"})
    return f"exp_{safe_id}"


def _query_param_value(name: str) -> str:
    try:
        value = st.query_params.get(name, "")
    except Exception:
        try:
            value = st.experimental_get_query_params().get(name, [""])
        except Exception:
            value = ""
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "").strip()


def _variant_assignment(experiment: Dict[str, Any], variant: Dict[str, Any]) -> Dict[str, Any]:
    experiment_id = str(experiment.get("experiment_id") or "")
    return {
        "experiment_id": experiment_id,
        "experiment_name": str(experiment.get("experiment_name") or experiment_id),
        "variant_id": str(variant.get("variant_id") or ""),
        "variant_name": str(variant.get("variant_name") or variant.get("variant_id") or ""),
        "config": dict(variant.get("config") or {}),
    }


def get_experiment_assignment(session_id: str, experiment_id: str) -> Dict[str, Any]:
    experiment = get_experiment(experiment_id)
    if not experiment or experiment.get("status") != "active":
        return {}

    state_key = f"experiment_assignment_{experiment_id}"
    variants = [variant for variant in experiment.get("variants", []) if variant.get("variant_id")]
    query_variant_id = _query_param_value(experiment_query_param_name(experiment_id))
    if query_variant_id:
        query_variant = next(
            (variant for variant in variants if str(variant.get("variant_id")) == query_variant_id),
            None,
        )
        if query_variant:
            assignment = _variant_assignment(experiment, query_variant)
            st.session_state[state_key] = assignment
            return assignment

    cached = st.session_state.get(state_key)
    if isinstance(cached, dict) and cached.get("experiment_id") == experiment_id:
        return cached

    allocation = float(experiment.get("traffic_allocation", 0.0) or 0.0)
    allocation = max(0.0, min(1.0, allocation))
    traffic_bucket = _stable_ratio(f"{experiment_id}:traffic:{session_id}")
    if traffic_bucket >= allocation:
        return {}

    variant = _variant_bucket(variants, _stable_ratio(f"{experiment_id}:variant:{session_id}"))
    if not variant:
        return {}

    assignment = _variant_assignment(experiment, variant)
    st.session_state[state_key] = assignment
    return assignment


def get_active_experiment_assignment(session_id: str, experiment_id: str = "post_render_hero_value_v1") -> Dict[str, Any]:
    return get_experiment_assignment(session_id, experiment_id)


def get_experiment_config(session_id: str, experiment_id: str, defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = dict(defaults or {})
    assignment = get_experiment_assignment(session_id, experiment_id)
    config.update(dict(assignment.get("config") or {}))
    return config


def get_homepage_experiment_config(session_id: str) -> Dict[str, Any]:
    return get_experiment_config(session_id, "post_render_hero_value_v1")


def get_active_assignments(session_id: str, experiment_ids: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    ids = list(experiment_ids or [str(experiment.get("experiment_id")) for experiment in list_experiments(active_only=True)])
    assignments: List[Dict[str, Any]] = []
    for experiment_id in ids:
        assignment = get_experiment_assignment(session_id, experiment_id)
        if assignment:
            assignments.append(assignment)
    return assignments


def get_experiment_query_params(session_id: str, experiment_ids: Optional[Iterable[str]] = None) -> Dict[str, str]:
    return {
        experiment_query_param_name(str(assignment["experiment_id"])): str(assignment["variant_id"])
        for assignment in get_active_assignments(session_id, experiment_ids)
        if assignment.get("experiment_id") and assignment.get("variant_id")
    }


def get_experiment_event_context(session_id: str, experiment_ids: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    assignments = get_active_assignments(session_id, experiment_ids)
    if not assignments:
        return {}

    experiments = {
        assignment["experiment_id"]: assignment["variant_id"]
        for assignment in assignments
        if assignment.get("experiment_id") and assignment.get("variant_id")
    }
    primary = assignments[0]
    return {
        "experiment_id": primary.get("experiment_id"),
        "variant_id": primary.get("variant_id"),
        "experiments": experiments,
    }
