"""Вёрстка транзакционных писем в фирменном стиле сайта.

Письма читают почтовые клиенты с очень разным CSS: внешние стили и <style> в
Gmail/mail.ru режутся, поэтому здесь только инлайновые стили и таблица для
кнопки (Outlook не умеет padding у ссылок). Палитра — та же, что во фронтенде
(frontend/src/style.css): бирюзовый #0EBCBD, фон #E4F7F8/#FBFDFE, текст #090909.
"""

from html import escape

from app.core.config import settings

BRAND = "#0EBCBD"
BRAND_DARK = "#0BA1A2"
INK = "#090909"
ASH = "#50504F"
PAPER = "#FBFDFE"
MIST = "#E4F7F8"


def _site_url() -> str:
    return settings.frontend_base_url.rstrip("/")


def render_email(*, heading: str, intro: str, button_label: str, button_url: str, note: str) -> tuple[str, str]:
    """Собирает текстовую и HTML-версии письма. Возвращает (text, html).

    Текстовая версия — не формальность: часть почтовых клиентов и антиспам-фильтров
    смотрят именно на неё, а письмо без text/plain выглядит подозрительнее.
    """
    site = _site_url()
    text = f"{heading}\n\n{intro}\n\n{button_url}\n\n{note}\n\n{site}"

    html = f"""<!doctype html>
<html lang="ru">
  <body style="margin:0;padding:24px 12px;background:{PAPER};font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:{INK};">
    <div style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #E2EAEC;border-radius:16px;padding:32px 28px;">
      <a href="{escape(site)}" style="text-decoration:none;">
        <img src="{escape(site)}/logo.png" alt="my-tutor.ru" width="120" style="display:block;margin:0 auto 24px;border:0;" />
      </a>
      <h1 style="margin:0 0 12px;font-size:22px;line-height:1.3;color:{INK};">{escape(heading)}</h1>
      <p style="margin:0 0 24px;font-size:16px;line-height:1.6;color:{ASH};">{escape(intro)}</p>
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 auto 24px;">
        <tr>
          <td align="center" bgcolor="{BRAND}" style="border-radius:10px;">
            <a href="{escape(button_url)}"
               style="display:inline-block;padding:14px 28px;font-size:16px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:10px;background:{BRAND};">
              {escape(button_label)}
            </a>
          </td>
        </tr>
      </table>
      <p style="margin:0 0 8px;font-size:14px;line-height:1.6;color:{ASH};">{escape(note)}</p>
      <p style="margin:0;font-size:13px;line-height:1.6;color:#6D7273;">
        Если кнопка не открывается, скопируйте ссылку в браузер:<br />
        <a href="{escape(button_url)}" style="color:{BRAND_DARK};word-break:break-all;">{escape(button_url)}</a>
      </p>
      <div style="margin-top:28px;padding-top:16px;border-top:1px solid {MIST};font-size:12px;line-height:1.6;color:#6D7273;">
        Это письмо отправлено автоматически сервисом
        <a href="{escape(site)}" style="color:{BRAND_DARK};text-decoration:none;">my-tutor.ru</a>.
        Если вы его не запрашивали — просто удалите его.
      </div>
    </div>
  </body>
</html>"""
    return text, html


def render_notice_email(*, heading: str, body_text: str) -> tuple[str, str]:
    """Письмо без кнопки-ссылки: администратор пишет обычный текст.

    Текст пользователя в HTML экранируется целиком (никакой разметки от админа в
    письмо не попадает), переводы строк превращаются в абзацы.
    """
    site = _site_url()
    text = f"{heading}\n\n{body_text}\n\n{site}"

    paragraphs = "".join(
        f'<p style="margin:0 0 14px;font-size:16px;line-height:1.6;color:{INK};">{escape(chunk)}</p>'
        for chunk in body_text.splitlines()
        if chunk.strip()
    )
    html = f"""<!doctype html>
<html lang="ru">
  <body style="margin:0;padding:24px 12px;background:{PAPER};font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:{INK};">
    <div style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #E2EAEC;border-radius:16px;padding:32px 28px;">
      <a href="{escape(site)}" style="text-decoration:none;">
        <img src="{escape(site)}/logo.png" alt="my-tutor.ru" width="120" style="display:block;margin:0 auto 24px;border:0;" />
      </a>
      <h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;color:{INK};">{escape(heading)}</h1>
      {paragraphs}
      <div style="margin-top:28px;padding-top:16px;border-top:1px solid {MIST};font-size:12px;line-height:1.6;color:#6D7273;">
        Письмо отправлено администратором сервиса
        <a href="{escape(site)}" style="color:{BRAND_DARK};text-decoration:none;">my-tutor.ru</a>.
        Вы можете ответить на него - ответ придёт нам на почту.
      </div>
    </div>
  </body>
</html>"""
    return text, html
