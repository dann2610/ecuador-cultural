from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

STATUS_CLASSES = {"draft": "secondary", "pending": "warning", "published": "success", "rejected": "danger",
                  "hidden": "danger", "pledged": "secondary", "under_review": "warning", "confirmed": "success",
                  "cancelled": "dark", "approved": "success"}


@register.simple_tag
def stars(value, size=""):
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        v = 0
    full = int(v)
    half = 1 if v - full >= 0.5 else 0
    html = "".join('<i class="bi bi-star-fill"></i>' for _ in range(full))
    html += '<i class="bi bi-star-half"></i>' * half
    html += "".join('<i class="bi bi-star"></i>' for _ in range(5 - full - half))
    return format_html('<span class="stars {}" aria-label="{} de 5 estrellas">{}</span>', size,
                       f"{v:.1f}", mark_safe(html))


@register.simple_tag
def status_badge(obj):
    status = getattr(obj, "status", "")
    label = obj.get_status_display() if hasattr(obj, "get_status_display") else status
    return format_html('<span class="badge text-bg-{}">{}</span>', STATUS_CLASSES.get(status, "secondary"), label)


@register.simple_tag
def demo_badge(obj):
    if getattr(obj, "is_demo", False):
        return format_html('<span class="badge badge-demo" title="{}"><i class="bi bi-info-circle"></i> '
                           'Demostración</span>', "Dato de demostración pendiente de verificación")
    return ""


@register.filter
def get_item(d, key):
    return d.get(key) if hasattr(d, "get") else None


@register.filter
def field_type(field):
    return field.field.widget.__class__.__name__
