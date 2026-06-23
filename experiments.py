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
        "status": "active",
        "traffic_allocation": 1.0,
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
        "status": "active",
        "traffic_allocation": 1.0,
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


def get_active_experiment_assignment(session_id: str, experiment_id: str = "homepage_cta_v1") -> Dict[str, Any]:
    return get_experiment_assignment(session_id, experiment_id)


def get_experiment_config(session_id: str, experiment_id: str, defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = dict(defaults or {})
    assignment = get_experiment_assignment(session_id, experiment_id)
    config.update(dict(assignment.get("config") or {}))
    return config


def get_homepage_experiment_config(session_id: str) -> Dict[str, Any]:
    return get_experiment_config(session_id, "homepage_cta_v1")


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
