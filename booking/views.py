from django.shortcuts import render, redirect, get_object_or_404
from .models import Doctor,Appointment, AppointmentType, Doctor, Notification
from .forms import AppointmentForm, ReportForm
from django.urls import reverse_lazy
from datetime import datetime
from django.utils import timezone
from django.template.loader import render_to_string
from weasyprint import HTML
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from django.contrib import messages

current_date = datetime.now().date()

@login_required
def index(request):
    upcoming_bookings = Appointment.objects.filter(user=request.user ,appointment_date=current_date)
    context= {
    'title':'Home',
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
            messages.success(request, 'Appointment successfully scheduled! Pay Booking  Fee( 200/-) to secure your Apointment')

            return redirect('appointmentBooking')  
    else:
        form = AppointmentForm()

    context = {
        'form': form
    }
    return render(request, 'appointment/appointment.html', context)



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
    return render(request, "appointment/appointment_delete.htm", context)



def list_doctors(request):
    doctors = Doctor.objects.all()
    return render(request, 'doctors/doctors_list.html', {'doctors': doctors})



@login_required
def view_notifications(request):
    notifications = Notification.objects.filter(user=request.user)
    return render(request, 'notifications/notifications.html', {'notifications': notifications})

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