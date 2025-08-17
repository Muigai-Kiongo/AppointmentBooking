from django import forms
from django.utils import timezone
from datetime import timedelta, datetime
from django.core.exceptions import ValidationError
from .models import UserProfile, Doctor, AppointmentType, Appointment, HealthRecord, Notification, Payment
from django.contrib.auth.models import User

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone_number', 'address', 'date_of_birth', 'insurance_provider', 'insurance_policy_number']

class DoctorForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User .objects.all(),
        required=True,
        label='Select User'
    )

    TIME_CHOICES = [(f"{hour:02d}:{minute:02d}", f"{hour:02d}:{minute:02d}") for hour in range(24) for minute in (0, 15, 30, 45)]

    available_time_start = forms.ChoiceField(choices=TIME_CHOICES, required=True, label='Available Time Start')
    available_time_end = forms.ChoiceField(choices=TIME_CHOICES, required=True, label='Available Time End')

    class Meta:
        model = Doctor
        fields = [
            'user',
            'specialty',
            'qualifications',
            'experience_years',
            'languages_spoken',
            'available_days',
            'available_time_start',
            'available_time_end',
            'appointment_types'
        ]

class AppointmentTypeForm(forms.ModelForm):
    class Meta:
        model = AppointmentType
        fields = ['name', 'duration']

class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['doctor', 'appointment_type', 'appointment_date', 'appointment_time']
        widgets = {
            'doctor': forms.Select(attrs={'placeholder': 'Select Doctor'}),
            'appointment_type': forms.Select(attrs={'placeholder': 'Select Appointment Type'}),
        }

    def __init__(self, *args, **kwargs):
        super(AppointmentForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages = {
                'required': 'This field is required.',
                'invalid': 'Please enter a valid value.',
            }
            field.widget.attrs.update({'class': 'form-control'})

    def clean(self):
        cleaned_data = super().clean()
        doctor = cleaned_data.get('doctor')
        appointment_date = cleaned_data.get('appointment_date')
        appointment_time = cleaned_data.get('appointment_time')
        appointment_type = cleaned_data.get('appointment_type')

        if doctor and appointment_date and appointment_time and appointment_type:
            appointment_datetime = datetime.combine(appointment_date, appointment_time)

            if appointment_date < timezone.now().date():
                raise ValidationError("You cannot book an appointment for a past date.")

            if not (doctor.available_time_start <= appointment_time <= doctor.available_time_end):
                raise ValidationError(f"Doctor is only available between {doctor.available_time_start.strftime('%I:%M %p')} and {doctor.available_time_end.strftime('%I:%M %p')}.")

            if appointment_type not in doctor.appointment_types.all():
                raise ValidationError(f"This doctor does not offer '{appointment_type.name}' appointments.")

            proposed_start_datetime = datetime.combine(appointment_date, appointment_time)
            proposed_end_datetime = proposed_start_datetime + timedelta(minutes=appointment_type.duration)

            existing_appointments = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=appointment_date
            )

            for existing_appt in existing_appointments:
                existing_start_datetime = datetime.combine(existing_appt.appointment_date, existing_appt.appointment_time)
                existing_end_datetime = existing_start_datetime + timedelta(minutes=existing_appt.appointment_type.duration)

                if (proposed_start_datetime < existing_end_datetime and proposed_end_datetime > existing_start_datetime):
                    raise ValidationError("This doctor is already booked at this time or there is an overlap with another appointment.")

        return cleaned_data

class HealthRecordForm(forms.ModelForm):
    class Meta:
        model = HealthRecord
        fields = ['record_date', 'description']

class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = ['message']


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'transaction_id']

class ReportForm(forms.Form):
    REPORT_CHOICES = [
        ('weekly', 'Weekly Report'),
        ('monthly', 'Monthly Report'),
        ('yearly', 'Yearly Report'),
    ]
    report_type = forms.ChoiceField(choices=REPORT_CHOICES, label="Select Report Type")
