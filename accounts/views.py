from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms
from booking.models import UserProfile
from booking.forms import UserProfileForm

# Form for editing user information
class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']  # Specify the fields you want to edit

@login_required
def profile(request):
    user = request.user  # Get the currently logged-in user

    # Get or create the user profile
    user_profile, created = UserProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=user)  # Edit user information
        profile_form = UserProfileForm(request.POST, instance=user_profile)  # Edit user profile information

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()  # Save the updated user information
            profile_form.save()  # Save the updated user profile information
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')  # Redirect to the profile page after saving
    else:
        user_form = UserEditForm(instance=user)  # Pre-fill the form with the user's current information
        profile_form = UserProfileForm(instance=user_profile)  # Pre-fill the profile form

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'user': user,  # Pass the user object if needed
        'user_profile': user_profile,  # Pass the user profile object for display
    }
    return render(request, 'profile/profile.html', context)

def signUp(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']
            messages.success(request, 'Registration successful!')
            return redirect('login')  # Ensure this redirect is returned
    else:
        form = UserCreationForm()

    context = {
        'form': form,
        'title': 'Register'
    }

    return render(request, 'registration/register.html', context)