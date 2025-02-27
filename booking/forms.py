from django import forms
from .models import UserProfile, Doctor, AppointmentType,Appointment, HealthRecord, Notification, Payment

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone_number', 'address', 'date_of_birth', 'insurance_provider', 'insurance_policy_number']


class DoctorForm(forms.ModelForm):
    class Meta:
        model = Doctor
        fields = ['specialty', 'qualifications', 'experience_years', 'languages_spoken', 'available_days', 'available_time_start', 'available_time_end']




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
                'class': 'form-control',
                'placeholder': 'Select Doctor',
            }),
            'appointment_type': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'Select Appointment Type',
            }),
            'appointment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'Select Appointment Date',
            }),
            'appointment_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
                'placeholder': 'Select Appointment Time',
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
        appointment_date = cleaned_data.get("appointment_date")
        appointment_time = cleaned_data.get("appointment_time")

        # Example validation: Check if the appointment is in the past
        if appointment_date and appointment_time:
            from datetime import datetime
            appointment_datetime = datetime.combine(appointment_date, appointment_time)
            if appointment_datetime < datetime.now():
                self.add_error('appointment_date', 'The appointment date and time cannot be in the past.')

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
