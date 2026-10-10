import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .engine import DEFAULT_SUGGESTIONS, ask
from .models import FAQ, ChatMessage, Conversation

logger = logging.getLogger("ecuador.chatbot")


def _rate_limited(request):
    ident = request.user.pk if request.user.is_authenticated else request.META.get("REMOTE_ADDR", "anon")
    key = f"chatbot-rl-{ident}"
    count = cache.get(key, 0)
    if count >= settings.CHATBOT_RATE_LIMIT_PER_MINUTE:
        return True
    cache.set(key, count + 1, 60)
    return False


@require_POST
def chat_api(request):
    try:
        body = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"error": "Solicitud no válida."}, status=400)
    message = str(body.get("message", "")).strip()
    if not message:
        return JsonResponse({"error": "Escribe una pregunta."}, status=400)
    if len(message) > 500:
        return JsonResponse({"error": "La pregunta es demasiado larga (máx. 500 caracteres)."}, status=400)
    if _rate_limited(request):
        return JsonResponse({"error": "Has enviado muchas preguntas seguidas. Espera un minuto."}, status=429)
    try:
        result = ask(message)
    except Exception:  # nunca exponer trazas al visitante
        logger.exception("Error en el chatbot")
        return JsonResponse({"error": "El asistente no está disponible en este momento."}, status=500)

    if request.user.is_authenticated and body.get("save_history"):
        conv, _ = Conversation.objects.get_or_create(user=request.user)
        ChatMessage.objects.bulk_create([
            ChatMessage(conversation=conv, role=ChatMessage.Role.USER, text=message),
            ChatMessage(conversation=conv, role=ChatMessage.Role.ASSISTANT, text=result["reply"]),
        ])
        conv.save(update_fields=["updated_at"])
    return JsonResponse(result)


def suggestions(request):
    faq = list(FAQ.objects.filter(is_active=True, show_as_suggestion=True).values_list("question", flat=True)[:3])
    history = []
    if request.user.is_authenticated:
        conv = Conversation.objects.filter(user=request.user).first()
        if conv:
            history = [{"role": m.role, "text": m.text} for m in conv.messages.order_by("-created_at")[:20]][::-1]
    return JsonResponse({"suggestions": (DEFAULT_SUGGESTIONS + faq)[:6], "history": history,
                         "can_save": request.user.is_authenticated})


@login_required
@require_POST
def delete_history(request):
    Conversation.objects.filter(user=request.user).delete()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    messages.success(request, "Historial del asistente eliminado.")
    return redirect("accounts:profile")
