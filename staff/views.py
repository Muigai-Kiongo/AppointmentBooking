from django.shortcuts import render, redirect, get_object_or_404
from booking.models import Appointment, AppointmentType, Doctor, Notification
from booking.forms import AppointmentTypeForm, DoctorForm, ReportForm, NotificationForm
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.template.loader import render_to_string
from weasyprint import HTML
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.http import require_POST
import logging

# Set up logging
logger = logging.getLogger(__name__)

@staff_member_required 
def staff_view(request):
    current_date = timezone.now().date()
    current_time = timezone.now().time()

    bookings = Appointment.objects.all()
    past_date = current_date - timedelta(days=1)
    tomorrow_date = current_date + timedelta(days=1)

    today_bookings = bookings.filter(appointment_date=current_date).order_by('appointment_time')
    tomorrow_bookings = bookings.filter(appointment_date=tomorrow_date).order_by('appointment_time')
    other_bookings = bookings.exclude(appointment_date__in=[past_date, current_date, tomorrow_date]).order_by('appointment_date', 'appointment_time')

    context = {
        'today_bookings': today_bookings,
        'tomorrow_bookings': tomorrow_bookings,
        'other_bookings': other_bookings,
        'user': request.user,
    }

    return render(request, 'staff.html', context)

def appointment_type_list(request):
    appointment_types = AppointmentType.objects.all()
    return render(request, 'appointments/appointments_types.html', {'appointment_types': appointment_types})

def appointment_type_create(request):
    if request.method == 'POST':
        form = AppointmentTypeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('/staff/appointment-types/')
    else:
        form = AppointmentTypeForm()
    return render(request, 'appointments/create_appointment_type.html', {'form': form})

def appointment_type_edit(request, pk):
    appointment_type = get_object_or_404(AppointmentType, pk=pk)
    if request.method == 'POST':
        form = AppointmentTypeForm(request.POST, instance=appointment_type)
        if form.is_valid():
            form.save()
            return redirect('/staff/appointment-types/')
    else:
        form = AppointmentTypeForm(instance=appointment_type)
    return render(request, 'appointments/create_appointment_type.html', {'form': form})

def appointment_detail(request, id):
    appointment = get_object_or_404(Appointment, id=id)
    context = {'appointment': appointment}
    return render(request, 'appointments/appointment_detail.html', context)

def doctor_list(request):
    doctors = Doctor.objects.all()
    return render(request, 'doctors/doctors.html', {'doctors': doctors})

def doctor_create(request):
    if request.method == 'POST':
        form = DoctorForm(request.POST)
        if form.is_valid():
            doctor = form.save()
            return redirect('doctor_list')
    else:
        form = DoctorForm()
    return render(request, 'doctors/doctors_edit.html', {'form': form})

def doctor_edit(request, pk):
    doctor = get_object_or_404(Doctor, pk=pk)
    if request.method == 'POST':
        form = DoctorForm(request.POST, instance=doctor)
        if form.is_valid():
            form.save()
            return redirect('doctor_list')
    else:
        form = DoctorForm(instance=doctor)
    return render(request, 'doctors/doctors_edit.html', {'form': form})

def reports_view(request):
    report_html = None
    report_type = None

    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            report_type = form.cleaned_data['report_type']
            appointments = get_appointments(report_type)
            report_html = render_to_string(f'reports/{report_type}_report.html', {'appointments': appointments})
    else:
        form = ReportForm()

    return render(request, 'reports/staff_reports.html', {
        'form': form,
        'report_html': report_html,
        'report_type': report_type,
    })

def get_appointments(report_type):
    now = timezone.now()
    if report_type == 'weekly':
        week_start = now - timezone.timedelta(days=7)
        return Appointment.objects.filter(appointment_date__gte=week_start.date())
    elif report_type == 'monthly':
        month_start = now.replace(day=1)
        return Appointment.objects.filter(appointment_date__gte=month_start.date())
    elif report_type == 'yearly':
        year_start = now.replace(month=1, day=1)
        return Appointment.objects.filter(appointment_date__gte=year_start.date())
    return Appointment.objects.none()

def generate_pdf_response(html_string, filename):
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def download_report(request, report_type):
    appointments = get_appointments(report_type)
    html_string = render_to_string(f'reports/{report_type}_report.html', {'appointments': appointments})
    return generate_pdf_response(html_string, f'{report_type}_report.pdf')



@login_required
@user_passes_test(lambda u: u.is_staff or hasattr(u, 'doctor'))
def staff_notification_dashboard(request):
    appointment_types = AppointmentType.objects.all()
    appointments = Appointment.objects.all()
    if hasattr(request.user, 'doctor'):
        appointments = appointments.filter(doctor=request.user.doctor)
    
    grouped_appointments = {
        'today': appointments.filter(appointment_date=timezone.now().date()),
        'upcoming': appointments.filter(appointment_date__gt=timezone.now().date()),
        'completed': appointments.filter(status='completed'),
        'canceled': appointments.filter(status='canceled'),
    }

    form = NotificationForm(request.POST or None)
    
    return render(request, 'notifications/notification_dashboard.html', {
        'appointment_types': appointment_types,
        'grouped_appointments': grouped_appointments,
        'common_messages': {
            'reminder': "Friendly reminder about your upcoming appointment",
            'reschedule': "We need to reschedule your appointment",
            'cancellation': "Your appointment has been canceled",
            'followup': "Follow-up instructions after your appointment",
        },
        'form': form
    })



@login_required
@user_passes_test(lambda u: u.is_staff or hasattr(u, 'doctor'))
@require_POST
def send_notification(request):
    form = NotificationForm(request.POST)
    appointment_id = request.POST.get('appointment_id')
    
    if form.is_valid() and appointment_id:
        try:
            appointment = get_object_or_404(Appointment, id=appointment_id)
            notification = form.save(commit=False)
            notification.user = appointment.user
            notification.sender = request.user
            notification.notification_type = 'appointment'
            notification.related_appointment = appointment
            notification.save()
            
            messages.success(request, "Notification sent successfully!")
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            messages.error(request, f"Failed to send notification: {str(e)}")
    
    return redirect('notification_dashboard')
