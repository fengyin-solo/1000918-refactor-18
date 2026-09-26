"""委托合同业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "contract"
REQUIRED_FIELDS = ["合同编号", "委托单位", "检测项目"]
STATUS_ORDER = ["待签订", "执行中", "已完成", "已终止"]
# 进入这些状态即视为合同已有结论（正常完成或提前终止），不再产生待办。
CONCLUDED_STATUSES = ["已完成", "已终止"]
# 动作流转表：动作、前置状态、目标状态只维护这一份；
# 列表按钮、详情页与动作接口都通过 available_actions 读同一份判断，调规则只改这里。
ACTION_TRANSITIONS = {
    "签订合同": {"from": ["待签订"], "to": "执行中"},
    "开始执行": {"from": ["执行中"], "to": "已完成"},
    "终止合同": {"from": ["待签订", "执行中"], "to": "已终止"},
}
NEGATIVE_ACTIONS: list[str] = []


def available_actions(entry: dict[str, Any]) -> list[str]:
    """按合同当前状态给出可执行动作；约定周期未开始（待签订）的合同不能直接标成已完成。"""
    status = str(entry.get("status") or "")
    return [name for name, rule in ACTION_TRANSITIONS.items() if status in rule["from"]]


def is_concluded(entry: dict[str, Any]) -> bool:
    """合同是否已有结论：已完成或已终止都算结论已定。"""
    return str(entry.get("status") or "") in CONCLUDED_STATUSES


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

    def describe_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        """给合同记录附上共用规则的结论：当前可执行动作与是否已有结论；不改动存储里的原始数据。"""
        return {**entry, "actions": available_actions(entry), "concluded": is_concluded(entry)}

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
        if action not in ACTION_TRANSITIONS:
            return None, f"动作「{action}」不属于委托合同可执行范围"
        if action not in available_actions(entry):
            return None, f"委托合同当前状态为「{entry.get('status')}」，不能执行「{action}」"
        target = str(ACTION_TRANSITIONS[action]["to"])
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = not is_concluded(entry)
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"委托合同已{action}"
