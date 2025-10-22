import json
import base64
import io
import logging
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.db.models import Q, Count

from .models import Doctor, Appointment, AppointmentType, Notification
from .forms import AppointmentForm, ReportForm

from weasyprint import HTML

logger = logging.getLogger(__name__)

# optional server-side chart rendering
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False

current_date = datetime.now().date()

def index(request):
    return render(request, 'startup.html', {'title': 'Home'})

@login_required
def dashboard(request):
    upcoming_bookings = Appointment.objects.filter(user=request.user, appointment_date=current_date)
    return render(request, 'index.html', {
        'title': 'Dashboard',
        'upcoming_bookings': upcoming_bookings,
    })

@login_required
def appointmentBooking(request):
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.user = request.user
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
        'appointment_types': AppointmentType.objects.all()
    }
    return render(request, 'appointment/appointment.html', context)

def payment(request):
    return render(request, 'appointment/payment.html')

def appointmentListView(request):
    current_datetime = timezone.now()
    bookings = Appointment.objects.filter(user=request.user).order_by('appointment_date', 'appointment_time')

    past_bookings = []
    upcoming_bookings = []

    for booking in bookings:
        if booking.appointment_date < current_datetime.date() or (booking.appointment_date == current_datetime.date() and booking.appointment_time < current_datetime.time()):
            past_bookings.append(booking)
        else:
            upcoming_bookings.append(booking)

    return render(request, "appointment/appointment_list.html", {
        "title": "Appointment List",
        'upcoming_bookings': upcoming_bookings,
        'past_bookings': past_bookings,
        "current_date": current_datetime.date(),
    })

def appointmentDetailView(request, pk):
    booking = get_object_or_404(Appointment, pk=pk)
    return render(request, "appointment/appointment_detail.html", {
        "title": "Booking Details",
        "booking": booking
    })

def appointmentUpdateView(request, pk):
    booking = get_object_or_404(Appointment, pk=pk)
    if request.method == "POST":
        form = AppointmentForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            return redirect("booking_list")
    else:
        form = AppointmentForm(instance=booking)
    return render(request, "appointment/appointment_update.html", {
        "title": "Update Appointment",
        "form": form
    })

def appointmentDeleteView(request, pk):
    booking = get_object_or_404(Appointment, pk=pk)
    if request.method == "POST":
        try:
            booking.delete()
            return redirect("booking_list")
        except Exception as e:
            return render(request, "appointment/appointment_delete.html", {
                "title": "Delete Appointment",
                "booking": booking,
                "error": str(e)
            })
    return render(request, "appointment/appointment_delete.html", {
        "title": "Delete Appointment",
        "booking": booking
    })

def list_doctors(request):
    doctors = Doctor.objects.all()
    return render(request, 'doctors/doctors_list.html', {'doctors': doctors})

@login_required
def view_notifications(request):
    notifications = Notification.objects.filter(sender=request.user).select_related(
        'sender', 'sender__doctor', 'related_appointment', 'related_appointment__doctor'
    ).order_by('-created_at')

    page = request.GET.get('page', 1)
    paginator = Paginator(notifications, 10)
    try:
        notifications_page = paginator.page(page)
    except PageNotAnInteger:
        notifications_page = paginator.page(1)
    except EmptyPage:
        notifications_page = paginator.page(paginator.num_pages)

    unread_count = Notification.objects.filter(sender=request.user, is_read=False).count()
    total_count = Notification.objects.filter(sender=request.user).count()

    return render(request, 'notifications/notifications.html', {
        'notifications': notifications_page,
        'unread_count': unread_count,
        'total_count': total_count,
    })

def reports_view(request):
    """
    Renders reports with charts and categorized appointment-type counts.
    ReportForm must provide a 'report_type' field with values 'weekly', 'monthly', 'yearly'.
    """
    report_html = None
    report_type = None

    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            report_type = form.cleaned_data['report_type']
            appointments = get_appointments(report_type)

            # Aggregate counts by appointment type and status
            type_qs = appointments.values('appointment_type__name').annotate(count=Count('id')).order_by('-count')
            type_counts = [{'type': item['appointment_type__name'] or 'Unknown', 'count': item['count']} for item in type_qs]

            status_qs = appointments.values('status').annotate(count=Count('id')).order_by('-count')
            status_counts = [{'status': item['status'], 'count': item['count']} for item in status_qs]

            # Build timeline data
            timeline_labels = []
            timeline_data = []
            now = timezone.now()

            if report_type == 'weekly':
                days = [(now.date() - timedelta(days=i)) for i in range(6, -1, -1)]
                for d in days:
                    timeline_labels.append(d.strftime('%a %d'))
                    timeline_data.append(appointments.filter(appointment_date=d).count())
            elif report_type == 'monthly':
                month_start = now.replace(day=1).date()
                today = now.date()
                day = month_start
                while day <= today:
                    timeline_labels.append(day.strftime('%d %b'))
                    timeline_data.append(appointments.filter(appointment_date=day).count())
                    day += timedelta(days=1)
            elif report_type == 'yearly':
                for m in range(1, 13):
                    label = datetime(now.year, m, 1).strftime('%b')
                    timeline_labels.append(label)
                    timeline_data.append(appointments.filter(appointment_date__month=m, appointment_date__year=now.year).count())

            chart_payload = {
                'type_counts': type_counts,
                'status_counts': status_counts,
                'timeline': {
                    'labels': timeline_labels,
                    'data': timeline_data
                }
            }

            report_html = render_to_string(f'reports/{report_type}_report.html', {
                'appointments': appointments,
                'type_counts': type_counts,
                'status_counts': status_counts,
                'timeline_labels': timeline_labels,
                'timeline_data': timeline_data,
                'chart_payload_json': json.dumps(chart_payload),
                'report_type': report_type,
            })
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
        week_start = (now - timedelta(days=6)).date()
        return Appointment.objects.filter(appointment_date__gte=week_start).select_related('appointment_type', 'doctor', 'user')
    elif report_type == 'monthly':
        month_start = now.replace(day=1).date()
        return Appointment.objects.filter(appointment_date__gte=month_start).select_related('appointment_type', 'doctor', 'user')
    elif report_type == 'yearly':
        year_start = now.replace(month=1, day=1).date()
        return Appointment.objects.filter(appointment_date__gte=year_start).select_related('appointment_type', 'doctor', 'user')
    return Appointment.objects.none()

def generate_pdf_response(html_string, filename):
    html = HTML(string=html_string, base_url=None)
    pdf = html.write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@login_required
@csrf_exempt
def download_report(request, report_type):
    """
    Enhanced download_report:
      - GET: returns a PDF using server-side charts (matplotlib) if available.
      - POST: accepts JSON with chart_images (data without the data:image/... prefix or full data URLs)
              and embeds the provided images in the PDF. If images are missing and matplotlib is available,
              server-side images will be generated.
    """
    if report_type not in ('weekly', 'monthly', 'yearly'):
        return HttpResponse('Invalid report type', status=400)

    appointments = get_appointments(report_type)

    chart_images = {}
    if request.method == 'POST':
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
            chart_images = payload.get('chart_images', {}) or {}
        except Exception as e:
            logger.exception("Failed to parse JSON body for download_report: %s", e)
            chart_images = {}

    def normalize_img(val):
        if not val:
            return ''
        if isinstance(val, str) and val.startswith('data:image'):
            return val
        # If contains base64 marker, use content after base64,
        # otherwise assume raw base64 and wrap as png
        if isinstance(val, str) and 'base64,' in val:
            return 'data:image/png;base64,' + val.split('base64,', 1)[1]
        return 'data:image/png;base64,' + val

    img_timeline = normalize_img(chart_images.get('timeline'))
    img_type = normalize_img(chart_images.get('type'))
    img_status = normalize_img(chart_images.get('status'))

    # If any chart missing, attempt server-side generation (matplotlib)
    if (not img_timeline or not img_type or not img_status) and MATPLOTLIB_AVAILABLE:
        try:
            # Build aggregates
            type_counts = {}
            status_counts = {}
            now = timezone.now()

            for appt in appointments:
                tname = appt.appointment_type.name if appt.appointment_type else 'Unknown'
                type_counts[tname] = type_counts.get(tname, 0) + 1
                status_counts[appt.status] = status_counts.get(appt.status, 0) + 1

            timeline_labels = []
            timeline_data = []
            if report_type == 'weekly':
                days = [(now.date() - timedelta(days=i)) for i in range(6, -1, -1)]
                for d in days:
                    timeline_labels.append(d.strftime('%a %d'))
                    timeline_data.append(appointments.filter(appointment_date=d).count())
            elif report_type == 'monthly':
                month_start = now.replace(day=1).date()
                day = month_start
                today = now.date()
                while day <= today:
                    timeline_labels.append(day.strftime('%d %b'))
                    timeline_data.append(appointments.filter(appointment_date=day).count())
                    day += timedelta(days=1)
            else:
                for m in range(1, 13):
                    timeline_labels.append(datetime(now.year, m, 1).strftime('%b'))
                    timeline_data.append(appointments.filter(appointment_date__month=m, appointment_date__year=now.year).count())

            def fig_to_dataurl(fig, fmt='png', dpi=120):
                buf = io.BytesIO()
                fig.savefig(buf, format=fmt, bbox_inches='tight', dpi=dpi)
                plt.close(fig)
                buf.seek(0)
                return 'data:image/png;base64,' + base64.b64encode(buf.read()).decode('utf-8')

            if not img_timeline:
                fig, ax = plt.subplots(figsize=(7, 2.6))
                ax.plot(timeline_labels, timeline_data, marker='o', color='#367fd8')
                ax.grid(True, linestyle=':', linewidth=0.5)
                fig.autofmt_xdate(rotation=25)
                img_timeline = fig_to_dataurl(fig)

            if not img_type:
                fig, ax = plt.subplots(figsize=(5, 3))
                types = list(type_counts.keys()) or ['No data']
                counts = [type_counts.get(k, 0) for k in types]
                ax.bar(types, counts, color='#8e5ea2')
                ax.set_ylabel('Count')
                fig.autofmt_xdate(rotation=25)
                img_type = fig_to_dataurl(fig)

            if not img_status:
                fig, ax = plt.subplots(figsize=(4, 3))
                statuses = list(status_counts.keys()) or ['none']
                scounts = [status_counts.get(k, 0) for k in statuses]
                colors = ['#4CAF50', '#2196F3', '#F44336'][:len(statuses)]
                ax.pie(scounts, labels=statuses, autopct='%1.0f%%', colors=colors)
                img_status = fig_to_dataurl(fig)
        except Exception:
            logger.exception("Server-side chart generation failed")
            img_timeline = img_timeline or ''
            img_type = img_type or ''
            img_status = img_status or ''

    # Render PDF-specific template; template should embed the three chart_* variables if present
    html_string = render_to_string(f'reports/{report_type}_report_pdf.html', {
        'appointments': appointments,
        'chart_timeline': img_timeline,
        'chart_type': img_type,
        'chart_status': img_status,
        'request': request,
    })

    return generate_pdf_response(html_string, f'{report_type}_report.pdf')

# AJAX: get doctors by appointment_type
def get_available_doctors(request, appointment_type_id):
    doctors = Doctor.objects.filter(appointment_types__id=appointment_type_id)
    doctor_list = [{'id': doctor.id, 'name': str(doctor)} for doctor in doctors]
    return JsonResponse({'doctors': doctor_list})

# AJAX: get available times for doctor on selected date for an appointment type
def get_available_times(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)
    selected_date_str = request.GET.get('appointment_date')
    appointment_type_id = request.GET.get('appointment_type_id')

    if not selected_date_str:
        return JsonResponse({'times': [], 'error': 'Appointment date is required.'}, status=400)
    if not appointment_type_id:
        return JsonResponse({'times': [], 'error': 'Appointment type is required.'}, status=400)

    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        appointment_type = AppointmentType.objects.get(id=appointment_type_id)
    except (ValueError, AppointmentType.DoesNotExist):
        return JsonResponse({'times': [], 'error': 'Invalid date or appointment type.'}, status=400)

    if selected_date < timezone.now().date():
        return JsonResponse({'times': [], 'error': 'Cannot book appointments for past dates.'}, status=400)

    start_time_doctor = doctor.available_time_start
    end_time_doctor = doctor.available_time_end

    booked_appointments = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=selected_date
    ).order_by('appointment_time')

    available_times = []
    current_slot_datetime = datetime.combine(selected_date, start_time_doctor)
    end_slot_datetime = datetime.combine(selected_date, end_time_doctor)
    appointment_duration = timedelta(minutes=appointment_type.duration)
    time_slot_interval = timedelta(minutes=15)

    while current_slot_datetime + appointment_duration <= end_slot_datetime:
        slot_start_time = current_slot_datetime.time()
        slot_end_time = (current_slot_datetime + appointment_duration).time()

        is_available = True
        if selected_date == timezone.now().date() and slot_start_time < timezone.now().time():
            is_available = False

        if is_available:
            for booked_appt in booked_appointments:
                booked_start_datetime = datetime.combine(booked_appt.appointment_date, booked_appt.appointment_time)
                booked_end_datetime = booked_start_datetime + timedelta(minutes=booked_appt.appointment_type.duration)
                proposed_slot_start_datetime = datetime.combine(selected_date, slot_start_time)
                proposed_slot_end_datetime = datetime.combine(selected_date, slot_end_time)
                if (proposed_slot_start_datetime < booked_end_datetime and proposed_slot_end_datetime > booked_start_datetime):
                    is_available = False
                    break

        if is_available:
            available_times.append(slot_start_time.strftime('%H:%M'))

        current_slot_datetime += time_slot_interval

    return JsonResponse({'times': available_times})