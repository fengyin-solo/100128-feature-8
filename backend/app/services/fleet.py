"""车辆档案业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "fleet"
REQUIRED_FIELDS = ["车辆编号", "车牌号码", "车型类别"]
STATUS_ORDER = ["空闲", "出车中", "维修中", "已报废"]
ACTION_RULES = {"调度出车": "出车中", "维修登记": "维修中", "申请报废": "已报废"}
NEGATIVE_ACTIONS = []
SORTABLE_FIELDS = {"车辆编号", "车牌号码", "温区数量", "购置日期"}
NUMERIC_FIELDS = {"温区数量"}
DEFAULT_SORT = "车辆编号"


class FleetService:
    def list_entries(
        self,
        *,
        vehicle_no: str | None = None,
        plate_no: str | None = None,
        fleet_name: str | None = None,
        category: str | None = None,
        status: str | None = None,
        sort_by: str = DEFAULT_SORT,
        sort_dir: str = "asc",
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, int]:
        """组合筛选后排序分页；页码越界时收敛到最后一页，返回实际生效的页码。"""
        rows = [self._serialize(row) for row in store.rows(MODULE)]
        if vehicle_no:
            rows = [row for row in rows if vehicle_no in str(row.get("车辆编号", ""))]
        if plate_no:
            rows = [row for row in rows if plate_no in str(row.get("车牌号码", ""))]
        if fleet_name:
            rows = [row for row in rows if fleet_name in str(row.get("所属车队", ""))]
        if category:
            rows = [row for row in rows if str(row.get("车型类别", "")) == category]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        rows = self._sort(rows, sort_by, sort_dir)
        total = len(rows)
        size = max(size, 1)
        max_page = max(1, -(-total // size))
        page = min(max(page, 1), max_page)
        start = (page - 1) * size
        return rows[start:start + size], total, page

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._serialize(row) if row is not None else None

    def history_by_plate(self, plate_no: str) -> list[dict[str, Any]]:
        """同一车牌号码下的全部档案记录，按购置日期倒序，最新的排在前面。"""
        rows = [
            self._serialize(row)
            for row in store.rows(MODULE)
            if str(row.get("车牌号码", "")) == plate_no
        ]
        rows.sort(
            key=lambda row: (str(row.get("购置日期", "")), int(row.get("id", 0))),
            reverse=True,
        )
        return rows

    def filter_options(self) -> dict[str, list[str]]:
        """车型类别与所属车队的可选值，给筛选下拉用。"""
        rows = store.rows(MODULE)
        categories = sorted({str(row["车型类别"]) for row in rows if row.get("车型类别")})
        fleets = sorted({str(row["所属车队"]) for row in rows if row.get("所属车队")})
        return {"categories": categories, "fleets": fleets}

    def status_stats(self) -> dict[str, int]:
        rows = store.rows(MODULE)
        result = {status: 0 for status in STATUS_ORDER}
        for row in rows:
            status = str(row.get("status", ""))
            if status in result:
                result[status] += 1
        result["total"] = len(rows)
        return result

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["车辆状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._serialize(entry), []

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
        return self._serialize(entry), f"冷链车已{action}"

    def _sort(
        self,
        rows: list[dict[str, Any]],
        sort_by: str,
        sort_dir: str,
    ) -> list[dict[str, Any]]:
        if sort_by not in SORTABLE_FIELDS:
            sort_by = DEFAULT_SORT
        reverse = sort_dir == "desc"
        if sort_by in NUMERIC_FIELDS:
            key = lambda row: (self._to_number(row.get(sort_by)), int(row.get("id", 0)))  # noqa: E731
        else:
            key = lambda row: (str(row.get(sort_by) or ""), int(row.get("id", 0)))  # noqa: E731
        return sorted(rows, key=key, reverse=reverse)

    @staticmethod
    def _to_number(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        """对外输出统一以 status 为准回写车辆状态，保证列表与详情看到的一致。"""
        item = dict(row)
        item["车辆状态"] = str(row.get("status") or "")
        return item
