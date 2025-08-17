from django.shortcuts import render, redirect, get_object_or_404
from .models import Doctor, Appointment, AppointmentType, Notification
from .forms import AppointmentForm, ReportForm
from django.urls import reverse_lazy
from datetime import datetime, time, timedelta
from django.utils import timezone
from django.template.loader import render_to_string
from weasyprint import HTML
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q


current_date = datetime.now().date()

def index(request):
    context = {
        'title': 'Home',
    }
    return render(request, 'startup.html', context)

@login_required
def dashboard(request):
    upcoming_bookings = Appointment.objects.filter(user=request.user, appointment_date=current_date)
    context = {
        'title': 'Dashboard',
        'upcoming_bookings': upcoming_bookings,
    }
    return render(request, 'index.html', context)

@login_required
def appointmentBooking(request):
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.user = request.user  # Set the user to the logged-in user
            appointment.save()

            # Prepare the email
            subject = 'Booking Successfully'
            doctor = form.cleaned_data['doctor']
            appointment_type = form.cleaned_data['appointment_type']
            appointment_date = form.cleaned_data['appointment_date']
            appointment_time = form.cleaned_data['appointment_time']

            message = f"""
            Hi {request.user.username}, you have successfully made an appointment.

            Details:
            Doctor: {doctor}
            Appointment Type: {appointment_type}
            Appointment Date: {appointment_date}
            Appointment Time: {appointment_time}
            """
            recipient_list = [request.user.email]

            send_mail(subject, message, settings.EMAIL_HOST_USER, recipient_list)
            messages.success(request, 'Appointment successfully scheduled! Pay Booking Fee (200/-) to secure your Appointment')

            return redirect('payment')
    else:
        form = AppointmentForm()

    context = {
        'form': form,
        'appointment_types': AppointmentType.objects.all()  # Pass appointment types to the template
    }
    return render(request, 'appointment/appointment.html', context)

def payment(request):
    return render(request, 'appointment/payment.html')

def appointmentListView(request):
    current_datetime = timezone.now()  # Get the current date and time
    bookings = Appointment.objects.filter(user=request.user).order_by('appointment_date', 'appointment_time')  # Order by appointment_date and appointment_time

    past_bookings = []
    upcoming_bookings = []

    for booking in bookings:
        if booking.appointment_date < current_datetime.date() or (booking.appointment_date == current_datetime.date() and booking.appointment_time < current_datetime.time()):
            past_bookings.append(booking)
        else:
            upcoming_bookings.append(booking)

    context = {
        "title": "Appointment List",
        'upcoming_bookings': upcoming_bookings,
        'past_bookings': past_bookings,
        "current_date": current_datetime.date(),
    }
    return render(request, "appointment/appointment_list.html", context)

def appointmentDetailView(request, pk):
    booking = get_object_or_404(Appointment, pk=pk)
    context = {
        "title": "Booking Details",
        "booking": booking
    }
    return render(request, "appointment/appointment_detail.html", context)

def appointmentUpdateView(request, pk):
    booking = get_object_or_404(Appointment, pk=pk)
    if request.method == "POST":
        form = AppointmentForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            return redirect("booking_list")
    else:
        form = AppointmentForm(instance=booking)
    context = {
        "title": "Update Appointment",
        "form": form
    }
    return render(request, "appointment/appointment_update.html", context)

def appointmentDeleteView(request, pk):
    booking = get_object_or_404(Appointment, pk=pk)
    if request.method == "POST":
        try:
            booking.delete()
            return redirect("booking_list")
        except Exception as e:
            context = {
                "title": "Delete Appointment",
                "booking": booking,
                "error": str(e)
            }
            return render(request, "appointment/appointment_delete.html", context)
    context = {
        "title": "Delete Appointment",
        "booking": booking
    }
    return render(request, "appointment/appointment_delete.html", context)

def list_doctors(request):
    doctors = Doctor.objects.all()
    return render(request, 'doctors/doctors_list.html', {'doctors': doctors})

@login_required
def view_notifications(request):
    # Get all notifications for the logged-in user, ordered by creation date (latest first)
    notifications = Notification.objects.filter(sender=request.user).select_related(
        'sender', 'sender__doctor', 'related_appointment', 'related_appointment__doctor'
    ).order_by('-created_at')

    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(notifications, 10)  # Show 10 notifications per page

    try:
        notifications_page = paginator.page(page)
    except PageNotAnInteger:
        notifications_page = paginator.page(1)
    except EmptyPage:
        notifications_page = paginator.page(paginator.num_pages)

    # Counts for filter options
    unread_count = Notification.objects.filter(sender=request.user, is_read=False).count()
    total_count = Notification.objects.filter(sender=request.user).count()

    return render(request, 'notifications/notifications.html', {
        'notifications': notifications_page,
        'unread_count': unread_count,
        'total_count': total_count,
    })

def reports_view(request):
    report_html = None
    report_type = None

    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            report_type = form.cleaned_data['report_type']
            appointments = get_appointments(report_type)  # Helper function to get bookings
            report_html = render_to_string(f'reports/{report_type}_report.html', {'appointments': appointments})
    else:
        form = ReportForm()

    return render(request, 'reports/reports.html', {
        'form': form,
        'report_html': report_html,
        'report_type': report_type,
    })

def get_appointments(report_type):
    now = timezone.now()
    if report_type == 'weekly':
        week_start = now - timezone.timedelta(days=7)
        return Appointment.objects.filter(appointment_date__gte=week_start.date())  # Use appointment_date
    elif report_type == 'monthly':
        month_start = now.replace(day=1)
        return Appointment.objects.filter(appointment_date__gte=month_start.date())  # Use appointment_date
    elif report_type == 'yearly':
        year_start = now.replace(month=1, day=1)
        return Appointment.objects.filter(appointment_date__gte=year_start.date())  # Use appointment_date
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

# New AJAX view to get available doctors based on appointment type
def get_available_doctors(request, appointment_type_id):
    # Filter doctors who are associated with the given appointment_type_id
    doctors = Doctor.objects.filter(appointment_types__id=appointment_type_id)
    doctor_list = [{'id': doctor.id, 'name': str(doctor)} for doctor in doctors]
    return JsonResponse({'doctors': doctor_list})

# New AJAX view to get available times for a selected doctor and date
def get_available_times(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)
    selected_date_str = request.GET.get('appointment_date') # Get the selected date from the request
    appointment_type_id = request.GET.get('appointment_type_id') # Get the selected appointment type ID

    if not selected_date_str:
        return JsonResponse({'times': [], 'error': 'Appointment date is required.'}, status=400)
    if not appointment_type_id:
        return JsonResponse({'times': [], 'error': 'Appointment type is required.'}, status=400)

    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        appointment_type = AppointmentType.objects.get(id=appointment_type_id)
    except (ValueError, AppointmentType.DoesNotExist):
        return JsonResponse({'times': [], 'error': 'Invalid date or appointment type.'}, status=400)

    available_times = []

    # Check if the selected date is in the past
    if selected_date < timezone.now().date():
        return JsonResponse({'times': [], 'error': 'Cannot book appointments for past dates.'}, status=400)

    # Convert doctor's available start and end times to datetime.time objects
    start_time_doctor = doctor.available_time_start
    end_time_doctor = doctor.available_time_end

    # Get all existing appointments for this doctor on the selected date
    booked_appointments = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=selected_date
    ).order_by('appointment_time')

    # Generate potential time slots within the doctor's availability
    # Start from the doctor's available start time
    current_slot_datetime = datetime.combine(selected_date, start_time_doctor)
    end_slot_datetime = datetime.combine(selected_date, end_time_doctor)

    # Use the duration of the selected appointment type
    appointment_duration = timedelta(minutes=appointment_type.duration)
    time_slot_interval = timedelta(minutes=15) # Define a granular interval for checking slots, e.g., every 15 minutes

    while current_slot_datetime + appointment_duration <= end_slot_datetime:
        slot_start_time = current_slot_datetime.time()
        slot_end_time = (current_slot_datetime + appointment_duration).time()

        is_available = True

        # Check if the slot is in the past relative to now
        if selected_date == timezone.now().date() and slot_start_time < timezone.now().time():
            is_available = False

        if is_available:
            for booked_appt in booked_appointments:
                booked_start_datetime = datetime.combine(booked_appt.appointment_date, booked_appt.appointment_time)
                booked_end_datetime = booked_start_datetime + timedelta(minutes=booked_appt.appointment_type.duration)

                # Check for overlap: (StartA < EndB and EndA > StartB)
                # Convert proposed slot times to datetime objects for comparison
                proposed_slot_start_datetime = datetime.combine(selected_date, slot_start_time)
                proposed_slot_end_datetime = datetime.combine(selected_date, slot_end_time)

                if (proposed_slot_start_datetime < booked_end_datetime and proposed_slot_end_datetime > booked_start_datetime):
                    is_available = False
                    break

        if is_available:
            available_times.append(slot_start_time.strftime('%H:%M'))

        current_slot_datetime += time_slot_interval # Move to the next granular interval

    return JsonResponse({'times': available_times})
