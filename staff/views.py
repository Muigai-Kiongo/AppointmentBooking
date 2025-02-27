from django.shortcuts import render, redirect, get_object_or_404
from booking.models import Appointment, AppointmentType, Doctor
from booking.forms import AppointmentTypeForm,DoctorForm
from datetime import timedelta
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required

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
    # Retrieve the book object or return a 404 error if not found
    appintment = get_object_or_404(Appointment, id=id)
    
    # Create a context dictionary to pass the book details to the template
    context = {
        'Appointment': Appointment,
    }
    
    # Render the template with the context
    return render(request, 'appointment_detail.html', context)


def doctor_list(request):
    doctors = Doctor.objects.all()
    return render(request, 'doctors/doctors.html', {'doctors': doctors})

def doctor_create(request):
    if request.method == 'POST':
        form = DoctorForm(request.POST)
        if form.is_valid():
            form.save()
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