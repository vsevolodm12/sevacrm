from fastapi.templating import Jinja2Templates


def _money(value):
    """Format number with non-breaking spaces as thousands separator: 1 000 000"""
    try:
        n = int(round(float(value or 0)))
        return f"{n:,}".replace(",", "\u00a0")
    except (ValueError, TypeError):
        return "0"


templates = Jinja2Templates(directory="app/templates")
templates.env.filters["money"] = _money
