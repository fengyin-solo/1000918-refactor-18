"""委托合同业务规则：状态流转、字段校验与筛选口径都收在这里。

「这份合同现在能做什么、做完之后合同结论是什么」只有这一份实现：
列表按钮、详情页与动作接口都通过 executable_actions / action_verdict 取结论，
以后调整规则只改这里，不要在别处再写一遍。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.store import store

MODULE = "contract"
REQUIRED_FIELDS = ["合同编号", "委托单位", "检测项目"]
STATUS_ORDER = ["待签订", "执行中", "已完成", "已终止"]
# 已有结论（终态）的状态：进入这些状态后合同不再有待办，也不能再执行任何动作
CONCLUDED_STATUSES = frozenset({"已完成", "已终止"})
NEGATIVE_ACTIONS: list[str] = []


@dataclass(frozen=True)
class ActionRule:
    """一个合同动作：能从哪些状态发起、执行后的合同结论、被拦下时的专属说明。"""

    target: str
    sources: tuple[str, ...]
    reasons: dict[str, str] = field(default_factory=dict)


ACTION_RULES: dict[str, ActionRule] = {
    "签订合同": ActionRule(target="执行中", sources=("待签订",)),
    "开始执行": ActionRule(
        target="已完成",
        sources=("执行中",),
        reasons={"待签订": "约定周期还没开始，不能标成已完成"},
    ),
    "终止合同": ActionRule(target="已终止", sources=("待签订", "执行中")),
}

for _name, _rule in ACTION_RULES.items():
    if _rule.target not in STATUS_ORDER:
        raise RuntimeError(f"动作「{_name}」的目标状态「{_rule.target}」不在允许的状态序列里")


def executable_actions(entry: dict[str, Any]) -> list[str]:
    """这份合同当前可执行的动作；列表、详情与动作接口都看这一个结果。"""
    status = str(entry.get("status") or "")
    return [name for name, rule in ACTION_RULES.items() if status in rule.sources]


def action_verdict(entry: dict[str, Any], action: str) -> tuple[bool, str]:
    """判断动作能否落在当前合同上：返回 (是否允许, 给操作者看的说明)。"""
    rule = ACTION_RULES.get(action)
    if rule is None:
        return False, f"动作「{action}」不属于委托合同可执行范围"
    status = str(entry.get("status") or "")
    if status in rule.sources:
        return True, f"委托合同已{action}"
    reason = rule.reasons.get(status) or f"当前状态「{status}」下不能执行「{action}」"
    return False, reason


class ContractService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("合同编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def present(self, entry: dict[str, Any]) -> dict[str, Any]:
        """列表/详情/动作结果共用的视图：原始字段不动，附上共享规则算出的可执行动作。"""
        return {**entry, "可执行动作": executable_actions(entry)}

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"委托合同 {entry_id} 不存在或已归档"
        allowed, message = action_verdict(entry, action)
        if not allowed:
            return None, message
        target = ACTION_RULES[action].target
        entry["status"] = target
        entry["pending"] = target not in CONCLUDED_STATUSES
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, message
