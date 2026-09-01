from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.blog import router as blog_router
from app.api.v1.bookings import router as bookings_router
from app.api.v1.chat import router as chat_router
from app.api.v1.groups import public_router as groups_public_router
from app.api.v1.groups import router as groups_router
from app.api.v1.homework import router as homework_router
from app.api.v1.mail import router as mail_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.reviews import router as reviews_router
from app.api.v1.stats import router as stats_router
from app.api.v1.subjects import router as subjects_router
from app.api.v1.tutors import router as tutors_router
from app.api.v1.whiteboards import router as whiteboards_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(subjects_router)
api_router.include_router(blog_router)
api_router.include_router(tutors_router)
api_router.include_router(bookings_router)
api_router.include_router(groups_router)
api_router.include_router(groups_public_router)
api_router.include_router(homework_router)
api_router.include_router(chat_router)
api_router.include_router(notifications_router)
api_router.include_router(reviews_router)
api_router.include_router(stats_router)
api_router.include_router(whiteboards_router)
api_router.include_router(admin_router)
api_router.include_router(mail_router)
