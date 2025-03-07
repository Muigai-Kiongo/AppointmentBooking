from django.urls import path
from . import views


urlpatterns = [
    path('',views.index, name= 'home'),
    path('book_appointment/',views.appointmentBooking, name='appointmentBooking'),
    path('appointments/',views.appointmentListView, name='appointment_list'),
    path('appointment/<pk>/', views.appointmentDetailView, name='appointments-detail'),
    path('appointment/<pk>/update/', views.appointmentUpdateView, name='appointment_update'),
    path('appointment/<pk>/delete/', views.appointmentDeleteView, name='appointment_delete'),
    path('reports/', views.reports_view, name = 'reports-view'),
    path('reports/download/<str:report_type>/', views.download_report, name='download_report'),
    path('doctors/', views.list_doctors, name='list_doctors'),
    path('notifications/', views.view_notifications, name='view_notifications'),
]
