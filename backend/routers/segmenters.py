from fastapi import APIRouter

from ..models import SegmenterInfo
from ..pipeline.segmentation import list_segmenters

router = APIRouter(prefix="/segmenters", tags=["segmenters"])


@router.get("", response_model=list[SegmenterInfo])
async def get_segmenters() -> list[SegmenterInfo]:
    return [SegmenterInfo(**s) for s in list_segmenters()]
