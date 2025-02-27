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

    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()  # Save the updated user information
            return redirect('profile')  # Redirect to the profile page after saving
    else:
        form = UserEditForm(instance=user)  # Pre-fill the form with the user's current information

    context = {
        'form': form,
    }
    return render(request, 'profile/profile.html', context)

def signUp (request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']
            redirect('login')
            messages.success(request, ('Registration successful!'))
            return redirect('login')
    else:

        form = UserCreationForm()

        context= {
            'form':form,
            'title': 'Register'
        }

    return render(request, 'registration/register.html', context)



# def user_profile(request):
#     return render(request, 'profile/profile.html', {'user_profile': request.user.userprofile})

def profile(request):
    user = request.user  # Get the currently logged-in user

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()  # Save the updated user information
            return redirect('profile')  # Redirect to the profile page after saving
    else:
        form = UserProfileForm(instance=user)  # Pre-fill the form with the user's current information

    context = {
        'form': form,
    }
    return render(request, 'profile/profile.html', context)