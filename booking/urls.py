from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='startup'),
    path('dashboard/', views.dashboard, name='home'),
    path('book_appointment/', views.appointmentBooking, name='appointmentBooking'),
    path('appointments/', views.appointmentListView, name='appointment_list'),
    path('appointment/<pk>/', views.appointmentDetailView, name='appointments-detail'),
    path('appointment/<pk>/update/', views.appointmentUpdateView, name='appointment_update'),
    path('appointment/<pk>/delete/', views.appointmentDeleteView, name='appointment_delete'),
    path('payment/', views.payment, name='payment'),
    path('reports/', views.reports_view, name='reports-view'),
    path('reports/download/<str:report_type>/', views.download_report, name='download_report'),
    path('doctors/', views.list_doctors, name='list_doctors'),
    path('notifications/', views.view_notifications, name='view_notifications'),

    # New AJAX endpoints
    path('get_available_doctors/<int:appointment_type_id>/', views.get_available_doctors, name='get_available_doctors'),
    path('get_available_times/<int:doctor_id>/', views.get_available_times, name='get_available_times'),
]
