from django.conf import settings
from django.db import models


class FAQ(models.Model):
    question = models.CharField("pregunta", max_length=250)
    answer = models.TextField("respuesta")
    keywords = models.CharField("palabras clave", max_length=300,
                                help_text="Separadas por comas, sin tildes. Se usan para encontrar la respuesta.")
    source = models.CharField("fuente o responsable", max_length=250, blank=True)
    is_verified = models.BooleanField("respuesta verificada", default=False)
    is_active = models.BooleanField("activa", default=True)
    order = models.PositiveSmallIntegerField("orden", default=0)
    show_as_suggestion = models.BooleanField("mostrar como pregunta sugerida", default=False)

    class Meta:
        ordering = ["order", "question"]
        verbose_name = "pregunta frecuente"
        verbose_name_plural = "preguntas frecuentes del chatbot"

    def __str__(self):
        return self.question

    def keyword_list(self):
        return [k.strip().lower() for k in self.keywords.split(",") if k.strip()]


class Conversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
                             related_name="chat_conversations")
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "conversación del chatbot"
        verbose_name_plural = "conversaciones del chatbot"


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Usuario"
        ASSISTANT = "assistant", "Asistente"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "mensaje del chatbot"
        verbose_name_plural = "mensajes del chatbot"
