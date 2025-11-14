from django.contrib import admin
from .models import ChatLog


@admin.register(ChatLog)
class ChatLogAdmin(admin.ModelAdmin):
    list_display = ("id", "patient_hash", "created_at")
    readonly_fields = ("created_at",)
    search_fields = ("patient_hash", "message")