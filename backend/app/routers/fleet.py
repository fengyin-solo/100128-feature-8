"""车辆档案接口：维护冷链车，覆盖调度出车、维修登记、申请报废等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.fleet import DEFAULT_SORT, SORTABLE_FIELDS, STATUS_ORDER, FleetService

router = APIRouter(prefix="/api/fleet", tags=["车辆档案"])

service = FleetService()

LIST_FIELDS = ["车辆编号", "车牌号码", "车型类别", "制冷机组", "温区数量", "购置日期", "所属车队", "车辆状态"]
STATUSES = STATUS_ORDER


def _parse_list_query(
    keyword: str | None,
    plate: str | None,
    fleet: str | None,
    category: str | None,
    status: str | None,
    sort: str,
    order: str,
) -> dict[str, Any]:
    """把组合筛选条件校验一遍：不合法的值给出可读原因，而不是静默忽略。"""
    if sort not in SORTABLE_FIELDS:
        raise HTTPException(status_code=400, detail=f"排序字段「{sort}」不支持，可选：{'、'.join(SORTABLE_FIELDS)}")
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail=f"排序方向「{order}」不支持，只能是 asc 或 desc")
    if status and status not in STATUSES:
        raise HTTPException(status_code=400, detail=f"车辆状态「{status}」不在允许范围：{'、'.join(STATUSES)}")
    return {
        "keyword": keyword,
        "plate": plate,
        "fleet": fleet,
        "category": category,
        "status": status,
        "sort": sort,
        "order": order,
    }


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按车辆编号模糊检索"),
    plate: str | None = Query(default=None, description="按车牌号码模糊检索"),
    fleet: str | None = Query(default=None, description="按所属车队模糊检索"),
    category: str | None = Query(default=None, description="只保留某一类车型类别"),
    status: str | None = Query(default=None, description="空闲、出车中、维修中、已报废"),
    sort: str = Query(default=DEFAULT_SORT, description="排序字段：车辆编号、温区数量、购置日期"),
    order: str = Query(default="asc", description="asc 升序、desc 降序"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按组合条件筛选车辆档案；排序只落在筛选结果内，没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    filters = _parse_list_query(keyword, plate, fleet, category, status, sort, order)
    items, total = service.list_entries(**filters, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/meta")
def list_meta() -> dict[str, Any]:
    """筛选下拉与统计卡片用的字典数据：车队、车型类别、状态分布与可排序字段。"""
    return service.meta()


@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None),
    plate: str | None = Query(default=None),
    fleet: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
    sort: str = Query(default=DEFAULT_SORT),
    order: str = Query(default="asc"),
) -> dict[str, Any]:
    """导出车辆档案清单：返回当前过滤条件下的全量数据。"""
    filters = _parse_list_query(keyword, plate, fleet, category, status, sort, order)
    items, total = service.list_entries(**filters, page=1, size=10000)
    return {"module": "fleet", "total": total, "items": items}


@router.get("/by-plate/{plate}")
def list_by_plate(plate: str) -> dict[str, Any]:
    """同一车牌号码下的全部档案记录：换车、过户留下的历史都能在这里展开。"""
    items = service.history_by_plate(plate)
    return {"plate": plate, "total": len(items), "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条冷链车明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"冷链车 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条冷链车，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="冷链车已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条冷链车执行调度出车、维修登记、申请报废；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
