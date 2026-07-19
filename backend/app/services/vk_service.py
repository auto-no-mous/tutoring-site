import httpx
from fastapi import HTTPException, status

from app.core.config import settings

VK_TOKEN_URL = "https://oauth.vk.com/access_token"


class VKAuthResult:
    def __init__(self, vk_id: str, email: str | None):
        self.vk_id = vk_id
        self.email = email


async def exchange_code(code: str, redirect_uri: str | None) -> VKAuthResult:
    """Exchanges a VK OAuth authorization code for the user's VK ID (and email, when
    VK grants it - not guaranteed, see project_description.md section 10)."""
    if not settings.vk_client_id or not settings.vk_client_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Вход через VK не настроен на сервере"
        )

    params = {
        "client_id": settings.vk_client_id,
        "client_secret": settings.vk_client_secret,
        "redirect_uri": redirect_uri or settings.vk_redirect_uri,
        "code": code,
    }
    async with httpx.AsyncClient(timeout=10) as http_client:
        response = await http_client.get(VK_TOKEN_URL, params=params)

    if response.status_code != 200:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Не удалось авторизоваться через VK")

    data = response.json()
    if "error" in data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Ошибка VK: {data.get('error_description', data['error'])}")

    vk_user_id = data.get("user_id")
    if vk_user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "VK не вернул идентификатор пользователя")

    return VKAuthResult(vk_id=str(vk_user_id), email=data.get("email"))
