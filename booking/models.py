from django.contrib.auth.models import User
from django.db import models
from datetime import datetime, timedelta

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    insurance_provider = models.CharField(max_length=100, blank=True)
    insurance_policy_number = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    specialty = models.CharField(max_length=100)
    qualifications = models.TextField()
    experience_years = models.PositiveIntegerField()
    languages_spoken = models.CharField(max_length=100, blank=True)
    rating = models.FloatField(default=0.0)
    available_days = models.CharField(max_length=100)
    available_time_start = models.TimeField()
    available_time_end = models.TimeField()
    appointment_types = models.ManyToManyField('AppointmentType', related_name='doctors')

    def __str__(self):
        return f"{self.user.username} - {self.specialty}"

class AppointmentType(models.Model):
    name = models.CharField(max_length=100)
    duration = models.PositiveIntegerField()

    def __str__(self):
        return self.name

class Appointment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    appointment_type = models.ForeignKey(AppointmentType, on_delete=models.CASCADE)
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    status = models.CharField(max_length=20, choices=[('scheduled', 'Scheduled'), ('completed', 'Completed'), ('canceled', 'Canceled')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['appointment_date']),
        ]

    def __str__(self):
        return f"Appointment with {self.doctor.user.username} on {self.appointment_date} at {self.appointment_time}"

    def get_end_time(self):
        """Calculate the end time of the appointment based on its type duration."""
        start_datetime = datetime.combine(self.appointment_date, self.appointment_time)
        end_datetime = start_datetime + timedelta(minutes=self.appointment_type.duration)
        return end_datetime.time()

class HealthRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    record_date = models.DateField()
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class Notification(models.Model):
    ACTION_CHOICES = [
        ('appointment', 'Appointment Related'),
        ('message', 'Doctor Message'),
        ('system', 'System Notification'),
    ]

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications', null=True, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    notification_type = models.CharField(max_length=20, choices=ACTION_CHOICES, default='system')
    related_appointment = models.ForeignKey(
        Appointment, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"Notification for {self.user.username} - {self.message[:30]}..."

class Payment(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed')])
    transaction_id = models.CharField(max_length=100, blank=True)
