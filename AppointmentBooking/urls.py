from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('django.contrib.auth.urls')),

    # Register booking app with a namespace so templates can use {% url 'booking:<name>' %}
    path('', include(('booking.urls', 'booking'), namespace='booking')),

    # Chatbot routes under /chat/ to avoid root collisions with booking app.
    path('chat/', include(('chatbot.urls', 'chatbot'), namespace='chatbot')),

    # Staff app (namespaced)
    path('staff/', include('staff.urls')),
]