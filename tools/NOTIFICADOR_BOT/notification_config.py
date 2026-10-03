"""Resolución segura de credenciales opcionales para notificaciones."""

from pathlib import Path


def resolve_telegram_chat_id(root_dir: str, token: str, configured_chat_id: str = "") -> str:
    """Devuelve el chat configurado sin advertir si Telegram no está habilitado."""
    configured = (configured_chat_id or "").strip()
    if configured or not (token or "").strip():
        return configured

    root = Path(root_dir)
    for candidate in (root / "chat_id.txt", root / "data" / "chat_id.txt"):
        try:
            if candidate.is_file():
                value = candidate.read_text(encoding="utf-8").strip()
                if value:
                    return value
        except OSError:
            continue
    return ""
