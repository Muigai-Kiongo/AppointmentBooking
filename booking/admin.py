from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Doctor

# Unregister the default User admin to customize it
admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_profile_type')
    list_filter = ('is_staff', 'is_superuser', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    def get_profile_type(self, obj):
        if hasattr(obj, 'doctor'):
            return 'Doctor'
        elif hasattr(obj, 'userprofile'):
            return 'Patient'
        return 'None'
    get_profile_type.short_description = 'Profile Type'

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name')

    fieldsets = (
        (None, {
            'fields': ('user',)
        }),
    )

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('user',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name')

    fieldsets = (
        (None, {
            'fields': ('user',)
        }),
    )

# Customizing the admin site titles
admin.site.site_header = "Health Plus Management"
admin.site.site_title = "Health Plus Management Admin"
admin.site.index_title = "Welcome to Health Plus Management Admin"