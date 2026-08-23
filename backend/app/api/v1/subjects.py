from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.subject import SubjectCatalogOut
from app.services import subject_service

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("", response_model=list[SubjectCatalogOut])
async def list_subjects(db: DbSession) -> list[SubjectCatalogOut]:
    """Public controlled vocabulary of subjects+directions - used by the catalog
    filter, by the home page's subject tiles, and by tutors picking what they teach
    (section 10 redesign)."""
    rows = await subject_service.list_subjects(db)
    counts = await subject_service.get_visible_tutor_counts(db)
    return [
        SubjectCatalogOut.model_validate(s, from_attributes=True).model_copy(
            update={"tutors_count": counts.get(s.id, 0)}
        )
        for s in rows
    ]
