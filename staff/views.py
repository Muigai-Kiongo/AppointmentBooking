from django.shortcuts import render, redirect, get_object_or_404
from booking.models import Appointment, AppointmentType, Doctor
from booking.forms import AppointmentTypeForm,DoctorForm, ReportForm
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.template.loader import render_to_string
from weasyprint import HTML
from django.http import HttpResponse

@staff_member_required 
def staff_view(request):
    current_date = timezone.now().date()
    current_time = timezone.now().time()

    # Get all appointments
    bookings = Appointment.objects.all()

    # Calculate past and future dates
    past_date = current_date - timedelta(days=1)
    tomorrow_date = current_date + timedelta(days=1)

    # Filter bookings for today, tomorrow, and other dates
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
    # Fetch the appointment using the primary key (id)
    appointment = get_object_or_404(Appointment, id=id)
    
    # Prepare the context to pass to the template
    context = {
        'appointment': appointment,
    }
    
    # Render the appointment detail template
    return render(request, 'appointments/appointment_detail.html', context)


def doctor_list(request):
    doctors = Doctor.objects.all()
    return render(request, 'doctors/doctors.html', {'doctors': doctors})


def doctor_create(request):
    if request.method == 'POST':
        form = DoctorForm(request.POST)
        if form.is_valid():
            # Create the Doctor instance
            doctor = form.save()  # Save the doctor instance with the selected user
            return redirect('doctor_list')  # Redirect to a success page
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
            appointments = get_appointments(report_type)  # Helper function to get bookings
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