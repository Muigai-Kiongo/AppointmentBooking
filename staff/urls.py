from django.urls import path
from . import views

urlpatterns = [
    path('', views.staff_view, name='staff_home'),
    path('appointment-types/', views.appointment_type_list, name='appointment_type_list'),
    path('appointment-types/create/', views.appointment_type_create, name='appointment_type_create'),
    path('appointment-types/edit/<int:pk>/', views.appointment_type_edit, name='appointment_type_edit'),
    path('appointment/<int:id>/', views.appointment_detail, name='appointment_detail'),
    path('doctors/', views.doctor_list, name='doctor_list'),
    path('doctors/create/', views.doctor_create, name='doctor_create'),
    path('doctors/edit/<int:pk>/', views.doctor_edit, name='doctor_edit'),
    path('staff_reports/', views.reports_view, name='reports-view'),
    path('staff_reports/download/<str:report_type>/', views.download_report, name='download_report'),

    # Notification URLs
    path('notifications/', views.staff_notification_dashboard, name='notification_dashboard'),
    path('notifications/send/', views.send_notification, name='send_notification'),
]
