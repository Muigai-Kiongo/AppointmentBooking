from django.contrib import admin
from .models import UserProfile, Doctor


admin.site.register(UserProfile)
admin.site.register(Doctor)

