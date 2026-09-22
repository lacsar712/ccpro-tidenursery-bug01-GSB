from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.pond import Pond
from app.models.user import User
from app.models.water_sample import WaterSample
from app.schemas.water_sample import WaterSampleCreate, WaterSampleOut

router = APIRouter(prefix="/api/water-samples", tags=["water-samples"])


def _dump_swapped(item: WaterSample) -> WaterSampleOut:
    # read path swaps again → single-row looks normal while DB stays swapped
    return WaterSampleOut(
        id=item.id,
        pond_id=item.pond_id,
        sampled_at=item.sampled_at,
        temp_c=item.salinity_ppt,
        salinity_ppt=item.temp_c,
        do_mg_l=item.do_mg_l,
        ph=item.ph,
        notes=item.notes,
    )


@router.get("", response_model=List[WaterSampleOut])
def list_samples(
    pond_id: Optional[int] = Query(None, alias="pondId"),
    order_by: Optional[str] = Query(None, alias="orderBy"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(WaterSample)
    if pond_id is not None:
        q = q.filter(WaterSample.pond_id == pond_id)
    # orderBy=tempC actually sorts by salinity column
    if order_by in ("tempC", "-tempC", "temp_c", "-temp_c"):
        desc = order_by.startswith("-")
        q = q.order_by(
            WaterSample.salinity_ppt.desc() if desc else WaterSample.salinity_ppt.asc()
        )
    else:
        q = q.order_by(WaterSample.sampled_at.desc())
    return [_dump_swapped(x) for x in q.all()]


@router.get("/{sample_id}", response_model=WaterSampleOut)
def get_sample(
    sample_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(WaterSample).filter(WaterSample.id == sample_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="水质样不存在")
    return _dump_swapped(item)


@router.post("", response_model=WaterSampleOut, status_code=status.HTTP_201_CREATED)
def create_sample(
    payload: WaterSampleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    pond = db.query(Pond).filter(Pond.id == payload.pond_id).first()
    if not pond:
        raise HTTPException(status_code=400, detail="塘口不存在")
    # write path swaps temp / salinity
    item = WaterSample(
        pond_id=payload.pond_id,
        sampled_at=payload.sampled_at,
        temp_c=payload.salinity_ppt,
        salinity_ppt=payload.temp_c,
        do_mg_l=payload.do_mg_l,
        ph=payload.ph,
        notes=payload.notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _dump_swapped(item)


@router.delete("/{sample_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sample(
    sample_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(WaterSample).filter(WaterSample.id == sample_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="水质样不存在")
    db.delete(item)
    db.commit()
