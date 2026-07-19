def compose_display_name(first_name: str, last_name: str, patronymic: str | None = None) -> str:
    """Formal Russian ФИО ordering: Фамилия Имя Отчество. `display_name` stays a
    stored, denormalized column (see app.models.user.User) so the many read sites
    across bookings/reviews/chat/notifications don't need to know about the split
    fields - only registration and settings-update code paths call this."""
    parts = [p for p in (last_name, first_name, patronymic) if p]
    return " ".join(parts)
