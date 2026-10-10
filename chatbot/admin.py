from django.contrib import admin

from .models import FAQ, ChatMessage, Conversation


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "is_verified", "is_active", "show_as_suggestion", "order")
    list_editable = ("is_active", "show_as_suggestion", "order")


class MessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ("role", "text", "created_at")


admin.site.register(Conversation, list_display=("user", "created_at", "updated_at"), inlines=[MessageInline])
