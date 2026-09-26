"""车辆档案业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "fleet"
REQUIRED_FIELDS = ["车辆编号", "车牌号码", "车型类别"]
STATUS_ORDER = ["空闲", "出车中", "维修中", "已报废"]
ACTION_RULES = {"调度出车": "出车中", "维修登记": "维修中", "申请报废": "已报废"}
NEGATIVE_ACTIONS: list[str] = []
SORTABLE_FIELDS = ["车辆编号", "温区数量", "购置日期"]
DEFAULT_SORT = "车辆编号"


def _serialize(row: dict[str, Any], plate_counts: dict[str, int] | None = None) -> dict[str, Any]:
    """对外输出的车辆档案：车辆状态以状态机字段为准，保证列表与详情口径一致。"""
    data = dict(row)
    data["车辆状态"] = str(row.get("status") or "")
    if plate_counts is not None:
        data["同牌记录数"] = plate_counts.get(str(row.get("车牌号码") or ""), 0)
    return data


class FleetService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        plate: str | None = None,
        fleet: str | None = None,
        category: str | None = None,
        status: str | None = None,
        sort: str = DEFAULT_SORT,
        order: str = "asc",
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("车辆编号", ""))]
        if plate:
            rows = [row for row in rows if plate in str(row.get("车牌号码", ""))]
        if fleet:
            rows = [row for row in rows if fleet in str(row.get("所属车队", ""))]
        if category:
            rows = [row for row in rows if str(row.get("车型类别", "")) == category]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        reverse = order == "desc"
        rows = sorted(rows, key=lambda row: (row.get(sort) is None, row.get(sort)), reverse=reverse)
        total = len(rows)
        plate_counts = self._plate_counts()
        start = max(page - 1, 0) * size
        return [_serialize(row, plate_counts) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return _serialize(row) if row is not None else None

    def history_by_plate(self, plate: str) -> list[dict[str, Any]]:
        """同一车牌号码下的全部档案：换车、过户留下的历史记录按车辆编号排好。"""
        rows = [row for row in store.rows(MODULE) if str(row.get("车牌号码") or "") == plate]
        rows = sorted(rows, key=lambda row: str(row.get("车辆编号") or ""))
        return [_serialize(row) for row in rows]

    def meta(self) -> dict[str, Any]:
        """筛选下拉与统计卡片需要的字典数据：车队、车型类别、状态分布。"""
        rows = store.rows(MODULE)
        categories = sorted({str(row.get("车型类别") or "") for row in rows} - {""})
        fleets = sorted({str(row.get("所属车队") or "") for row in rows} - {""})
        status_counts = {status: 0 for status in STATUS_ORDER}
        for row in rows:
            name = str(row.get("status") or "")
            if name in status_counts:
                status_counts[name] += 1
        return {
            "categories": categories,
            "fleets": fleets,
            "statuses": STATUS_ORDER,
            "sortable_fields": SORTABLE_FIELDS,
            "status_counts": status_counts,
        }

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
        return _serialize(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"冷链车 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于车辆档案可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return _serialize(entry), f"冷链车已{action}"

    def _plate_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in store.rows(MODULE):
            key = str(row.get("车牌号码") or "")
            counts[key] = counts.get(key, 0) + 1
        return counts
