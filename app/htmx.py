import json


def set_htmx_toast(response, message: str, level: str = "success"):
    response.headers["HX-Trigger"] = json.dumps(
        {"showToast": {"message": message, "type": level}},
        ensure_ascii=True,
    )
    return response
