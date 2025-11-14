from django.db import models


class ChatLog(models.Model):
    """
    Stores minimal chat logs. DO NOT store PHI here.
    patient_hash: SHA-256 of any patient identifier (if provided) so we can correlate without storing raw PHI.
    message: the user's message (shortened) -- avoid storing full PHI
    reply: bot's reply
    created_at: timestamp
    """

    patient_hash = models.CharField(max_length=64, blank=True, db_index=True)
    message = models.TextField()
    reply = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"ChatLog {self.id} ({self.created_at.isoformat()})"