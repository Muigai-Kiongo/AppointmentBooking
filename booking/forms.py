from django import forms
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from .models import UserProfile, Doctor, AppointmentType,Appointment, HealthRecord, Notification, Payment
from django.contrib.auth.models import User


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone_number', 'address', 'date_of_birth', 'insurance_provider', 'insurance_policy_number']


class DoctorForm(forms.ModelForm):
    # Dropdown for selecting existing users
    user = forms.ModelChoiceField(
        queryset=User .objects.all(),
        required=True,
        label='Select User'
    )

    # Remove the password field
    # password = forms.CharField(widget=forms.PasswordInput, required=True, label='Password')

    # Time choices for available time start and end
    TIME_CHOICES = [(f"{hour:02d}:{minute:02d}", f"{hour:02d}:{minute:02d}") for hour in range(24) for minute in (0, 15, 30, 45)]

    available_time_start = forms.ChoiceField(choices=TIME_CHOICES, required=True, label='Available Time Start')
    available_time_end = forms.ChoiceField(choices=TIME_CHOICES, required=True, label='Available Time End')

    class Meta:
        model = Doctor
        fields = [
            'user',  # Include the user dropdown
            'specialty',
            'qualifications',
            'experience_years',
            'languages_spoken',
            'available_days',
            'available_time_start',
            'available_time_end'
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
            'doctor': forms.Select(attrs={
                'placeholder': 'Select Doctor',
            }),
            'appointment_type': forms.Select(attrs={
                'placeholder': 'Select Appointment Type',
            }),
            'appointment_date': forms.DateInput(attrs={
                'type': 'date',
                'placeholder': 'Select Appointment Date',
            }),
            'appointment_time': forms.TimeInput(attrs={
                'type': 'time',
                'placeholder': 'Select Appointment Time',
                'min': '06:00',  # Set minimum time to 6 AM
                'max': '20:00',  # Set maximum time to 8 PM
            }),
        }

    def __init__(self, *args, **kwargs):
        super(AppointmentForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages = {
                'required': 'This field is required.',
                'invalid': 'Please enter a valid value.',
            }
            field.widget.attrs.update({'class': 'form-control'})  # Add a default class for styling

    def clean(self):
        cleaned_data = super().clean()
        doctor = cleaned_data.get('doctor')
        appointment_date = cleaned_data.get('appointment_date')
        appointment_time = cleaned_data.get('appointment_time')

        if doctor and appointment_date and appointment_time:
            # Combine date and time into a single datetime object
            appointment_datetime = timezone.datetime.combine(appointment_date, appointment_time)


            if appointment_date and appointment_date < timezone.now().date():
                raise ValidationError("You cannot book an appointment for a past date.")


            # Check if the appointment time is within the allowed range
            if appointment_time < timezone.datetime.strptime('06:00', '%H:%M').time() or \
               appointment_time > timezone.datetime.strptime('20:00', '%H:%M').time():
                raise ValidationError("Appointment time must be between 6 AM and 8 PM.")

            # Check for existing appointments for the same doctor at the same time
            existing_appointments = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=appointment_date,
                appointment_time=appointment_time
            )

            if existing_appointments.exists():
                raise ValidationError("This doctor is already booked at this time.")

            # Check for appointments within one hour before or after the requested time
            one_hour_before = appointment_datetime - timedelta(hours=1)
            one_hour_after = appointment_datetime + timedelta(hours=1)

            conflicting_appointments = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=appointment_date,
                appointment_time__range=(one_hour_before.time(), one_hour_after.time())
            )

            if conflicting_appointments.exists():
                raise ValidationError("This doctor is booked within one hour of the requested time.")

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
