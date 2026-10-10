from django.conf import settings


def site_context(request):
    user = request.user
    unread = 0
    if user.is_authenticated:
        unread = user.notifications.filter(is_read=False).count()
    return {
        "SITE_NAME": "Ecuador Cultural",
        "SITE_SLOGAN": "Descubre nuestras raíces, vive nuestras tradiciones.",
        "SITE_CONTACT_EMAIL": settings.SITE_CONTACT_EMAIL,
        "unread_notifications": unread,
    }
