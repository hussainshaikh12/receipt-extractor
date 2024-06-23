from django import forms
from .models import CustomUser, Receipt
from datetime import datetime
from django.core.exceptions import ValidationError
 

class ReceiptForm(forms.ModelForm):
    date = forms.CharField(required=False)  
    total_amount = forms.DecimalField(max_digits=10, decimal_places=2, required=True)

    class Meta:
        model = Receipt
        fields = ('file', 'date', 'vendor', 'total_amount')

    def clean_date(self):
        date_str = self.cleaned_data.get('date')
        if date_str:
            try:
                # Parse date string assuming the format "DD-MM-YYYY"
                return datetime.strptime(date_str, '%d-%m-%Y').date()
            except ValueError:
                raise ValidationError("Invalid date format. Please use DD-MM-YYYY.")

    def clean_total_amount(self):
        total_amount = self.cleaned_data.get('total_amount')
        if total_amount is not None and total_amount < 0:  # Check if total_amount is None to avoid errors
            raise ValidationError("Total amount cannot be negative.")
        return total_amount
    
class OTPVerificationForm(forms.Form):
    otp = forms.CharField(
        label='OTP',
        max_length=6,
        widget=forms.TextInput(attrs={'placeholder': 'Enter OTP received'}),
    )

class PhoneVerificationForm(forms.Form):
    phone_number = forms.CharField(
        label='Phone Number',
        max_length=15,
        widget=forms.TextInput(attrs={'placeholder': 'Enter your phone number'}),
    )

class UserRegistrationForm(forms.Form):
    phone_number = forms.CharField(
        label='Phone Number',
        max_length=15,
        widget=forms.TextInput(attrs={'placeholder': 'Enter your phone number'}),
    )
    name = forms.CharField(
        label='Name',
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': 'Enter your name'}),
        required=False,
    )
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'placeholder': 'Enter your email'}),
        required=False,
    )
