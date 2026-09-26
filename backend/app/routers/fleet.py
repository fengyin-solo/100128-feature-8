"""车辆档案接口：维护冷链车，覆盖调度出车、维修登记、申请报废等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.fleet import SORTABLE_FIELDS, FleetService

router = APIRouter(prefix="/api/fleet", tags=["车辆档案"])

service = FleetService()

LIST_FIELDS = ["车辆编号", "车牌号码", "车型类别", "制冷机组", "温区数量", "购置日期", "所属车队", "车辆状态"]
STATUSES = ["空闲", "出车中", "维修中", "已报废"]
SORT_DIRECTIONS = {"asc", "desc"}


def _check_sort(sort_by: str, sort_dir: str) -> None:
    if sort_by not in SORTABLE_FIELDS:
        options = "、".join(sorted(SORTABLE_FIELDS))
        raise HTTPException(status_code=400, detail=f"暂不支持按「{sort_by}」排序，可选项：{options}")
    if sort_dir not in SORT_DIRECTIONS:
        raise HTTPException(status_code=400, detail="排序方向只支持 asc 或 desc")


@router.get("", response_model=PageResult[dict])
def list_entries(
    vehicle_no: str | None = Query(default=None, description="按车辆编号模糊检索"),
    plate_no: str | None = Query(default=None, description="按车牌号码模糊检索"),
    fleet_name: str | None = Query(default=None, description="按所属车队筛选"),
    category: str | None = Query(default=None, description="只在某类车型类别里检索与排序"),
    status: str | None = Query(default=None, description="空闲、出车中、维修中、已报废"),
    sort_by: str = Query(default="车辆编号", description="排序字段"),
    sort_dir: str = Query(default="asc", description="asc 正序 / desc 倒序"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """组合筛选车辆档案列表；修改条件后页码保持不变，越界时收敛到最后一页。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    _check_sort(sort_by, sort_dir)
    items, total, page = service.list_entries(
        vehicle_no=vehicle_no,
        plate_no=plate_no,
        fleet_name=fleet_name,
        category=category,
        status=status,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


# 固定路径必须放在 /{entry_id} 之前，否则会被路径参数抢占、按 int 校验报 422。
@router.get("/export")
def export_entries(
    vehicle_no: str | None = Query(default=None, description="按车辆编号模糊检索"),
    plate_no: str | None = Query(default=None, description="按车牌号码模糊检索"),
    fleet_name: str | None = Query(default=None, description="按所属车队筛选"),
    category: str | None = Query(default=None, description="只在某类车型类别里检索与排序"),
    status: str | None = Query(default=None, description="空闲、出车中、维修中、已报废"),
    sort_by: str = Query(default="车辆编号", description="排序字段"),
    sort_dir: str = Query(default="asc", description="asc 正序 / desc 倒序"),
) -> dict[str, Any]:
    """导出车辆档案清单：返回当前过滤条件下的全量数据。"""
    _check_sort(sort_by, sort_dir)
    items, total, _ = service.list_entries(
        vehicle_no=vehicle_no,
        plate_no=plate_no,
        fleet_name=fleet_name,
        category=category,
        status=status,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=1,
        size=10000,
    )
    return {"module": "fleet", "fields": LIST_FIELDS, "total": total, "items": items}


@router.get("/options")
def filter_options() -> dict[str, list[str]]:
    """筛选项：车型类别与所属车队的可选值。"""
    return service.filter_options()


@router.get("/stats")
def status_stats() -> dict[str, int]:
    """按车辆状态统计在册车辆数，给页头卡片用。"""
    return service.status_stats()


@router.get("/history")
def history_entries(plate_no: str = Query(..., description="车牌号码")) -> dict[str, Any]:
    """同一车牌号码下的历史档案记录，按购置日期倒序。"""
    items = service.history_by_plate(plate_no)
    return {"plate_no": plate_no, "total": len(items), "items": items}


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
