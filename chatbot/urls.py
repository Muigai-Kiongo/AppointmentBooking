from django.urls import path

from . import views

app_name = "chatbot"

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path("", views.chat, name="chat"),        # POST API endpoint
    path("page/", views.chat_page, name="page"),  # GET page for full chat UI
]