from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.subject import SubjectOut
from app.services import subject_service

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("", response_model=list[SubjectOut])
async def list_subjects(db: DbSession) -> list[SubjectOut]:
    """Public controlled vocabulary of subjects+directions - used by the catalog
    filter and by tutors picking what they teach (section 10 redesign)."""
    rows = await subject_service.list_subjects(db)
    return [SubjectOut.model_validate(s, from_attributes=True) for s in rows]
