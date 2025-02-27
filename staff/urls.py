from django.urls import path
from . import views

urlpatterns = [
    path('', views.staff_view, name = 'staff_home'),
    path('appointment-types/', views.appointment_type_list, name='appointment_type_list'),
    path('appointment-types/create/', views.appointment_type_create, name='appointment_type_create'),
    path('appointment-types/edit/<int:pk>/', views.appointment_type_edit, name='appointment_type_edit'),
    path('appointment/<int:id>/', views.appointment_detail, name='appointment_detail'),
    path('doctors/',views.doctor_list, name='doctor_list'),
    path('doctors/create/', views.doctor_create, name='doctor_create'),
    path('doctors/edit/<int:pk>/', views.doctor_edit, name='doctor_edit'),
]

