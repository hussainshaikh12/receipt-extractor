import base64
import mimetypes
import os
from io import BytesIO
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.files.temp import NamedTemporaryFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from twilio.base.exceptions import TwilioException, TwilioRestException
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from .forms import (OTPVerificationForm, PhoneVerificationForm, ReceiptForm,
                    UserRegistrationForm)
from .models import CustomUser, Receipt
from .utils import process_receipt, process_receipt_query
from core.settings import (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
                           TWILIO_NUMBER, TWILIO_VERIFY_SERVICE_SID)

import threading
from django.db import connection

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
auth_string = f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}"
auth_header = {
    'Authorization': f'Basic {base64.b64encode(auth_string.encode()).decode()}'
}

def create_resp(to_number, body_text):

    resp = MessagingResponse()
    resp.message(
        from_=f"whatsapp:{TWILIO_NUMBER}",
        body=body_text,
        to=f"whatsapp:{to_number}"
        )
    return resp

def login_view(request):
    if request.method == 'POST':
        form = PhoneVerificationForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']

            try:
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

                
                phone_number_info = client.lookups.v2.phone_numbers(phone_number).fetch()

                if not phone_number_info.valid:
                    messages.error(request, 'Invalid phone number')
                else:
                    verification = client.verify.services(
                        TWILIO_VERIFY_SERVICE_SID
                    ).verifications.create(to=phone_number, channel='sms')

                    request.session['phone_number_to_verify'] = phone_number
                    return redirect('verify_otp')  
            except TwilioRestException as e:
                messages.error(request, f'Error processing phone number: {e.msg}')
            except TwilioException as e:
                messages.error(request, f'Error requesting OTP: {e.msg}')  
    else:
        form = PhoneVerificationForm()
    return render(request, 'extractor/login.html', {'form': form})

def verify_otp(request):
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            phone_number = request.session.get('phone_number_to_verify')
            otp = form.cleaned_data['otp']

            if phone_number:
                try:
                    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                    verification_check = client.verify.services(
                        TWILIO_VERIFY_SERVICE_SID
                    ).verification_checks.create(to=phone_number, code=otp)

                    if verification_check.status == 'approved':
                        user, created = CustomUser.objects.get_or_create(phone_number=phone_number)
                        login(request, user)  
                        del request.session['phone_number_to_verify']
                        return redirect('index')  
                    else:
                        messages.error(request, 'Invalid OTP')
                except TwilioRestException as e:
                    messages.error(request, f'Error verifying OTP: {e.msg}')
            else:
                messages.error(request, 'Phone number not found. Please request a new OTP.')
    else:
        form = OTPVerificationForm()
    return render(request, 'extractor/verify_otp.html', {'form': form})

def register_user(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']
            name = form.cleaned_data.get('name', '')  
            email = form.cleaned_data.get('email', '')  
            print(phone_number, name, email)
            try:
                
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                phone_number_info = client.lookups.v2.phone_numbers(phone_number).fetch()

                if not phone_number_info.valid:
                    print('Invalid phone number')
                    messages.error(request, 'Invalid phone number')

                else:
                    
                    print(phone_number_info.valid)
                    verification = client.verify.services(
                        TWILIO_VERIFY_SERVICE_SID
                    ).verifications.create(to=phone_number, channel='sms')  

                    
                    request.session['phone_number_to_register'] = phone_number
                    request.session['name_to_register'] = name
                    request.session['email_to_register'] = email

                    return redirect('verify_otp_registration') 
            except TwilioRestException as e:
                messages.error(request, f'Error processing phone number: {e.msg}')
            except TwilioException as e:
                messages.error(request, f'Error requesting OTP: {e.msg}')
    else:
        form = UserRegistrationForm()

    return render(request, 'extractor/register.html', {'form': form})


def verify_otp_registration(request):
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            phone_number = request.session.get('phone_number_to_register')
            name = request.session.get('name_to_register')
            email = request.session.get('email_to_register')
            otp = form.cleaned_data['otp']

            try:
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                verification_check = client.verify \
                                     .services(TWILIO_VERIFY_SERVICE_SID) \
                                     .verification_checks \
                                     .create(to=phone_number, code=otp)

                if verification_check.status == 'approved':
                    
                    user = CustomUser.objects.create_user(
                        phone_number=phone_number, name=name, email=email
                    )
                    login(request, user)  

                    
                    del request.session['phone_number_to_register']
                    del request.session['name_to_register']
                    del request.session['email_to_register']

                    return redirect('index') 
                else:
                    messages.error(request, 'Invalid OTP')
            except TwilioRestException as e:
                messages.error(request, f'Error verifying OTP: {e.msg}')
    else:
        form = OTPVerificationForm()

    return render(request, 'verify_otp.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect("index")

@login_required(login_url="login")
def index(request):
    user = request.user

    recent_receipts = Receipt.objects.filter(user=user).order_by('date')
    print(recent_receipts)
    total_receipts = Receipt.objects.filter(user=user).count()
    total_expense = Receipt.objects.filter(user=user).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_expense = round(float(total_expense), 2)
    chart_data = (Receipt.objects.filter(user=user)
                  .values('date')
                  .annotate(total=Sum('total_amount'))
                  .order_by('date'))
    
    
    # for data in chart_data:
    #     print(f"Date: {data['date']}, Total: {data['total']}")

    dates = [data['date'].isoformat() for data in chart_data]
    totals = [round(float(data['total']), 2) if data['total'] is not None else 0.0 for data in chart_data]

    return render(request, 'extractor/index.html', {
        'recent_receipts': recent_receipts,
        'total_receipts': total_receipts,
        'total_expense': total_expense,
        'chart_data': chart_data,
        'dates': dates,
        'totals': totals
    })




@csrf_exempt
def process_whatsapp_receipt(request):
    if request.method == 'POST':
        message = request.POST.get('Body')
        media_url = request.POST.get('MediaUrl0')
        mime_type = request.POST.get('MediaContentType0')
        user_phone = request.POST.get("From").split(":")[1]

        user, _ = CustomUser.objects.get_or_create(phone_number=user_phone)

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        if media_url:
            threading.Thread(target=process_receipt_thread, args=(media_url, mime_type, user, client, user_phone)).start()
            return HttpResponse(create_resp(user_phone,'Let me extract the data for you!! Processing receipt...'))
        else:
            threading.Thread(target=process_query_thread, args=(user, message, client, user_phone)).start()
            return HttpResponse(create_resp(user_phone,'Let me process the query for you!! Processing query...'))

    return HttpResponse('Invalid method. Use POST')

import os
import tempfile

def process_receipt_thread(media_url, mime_type, user, client, user_phone):
    temp_file_path = None
    try:
        connection.close()

        media_sid = os.path.basename(urlparse(media_url).path)
        file_extension = mimetypes.guess_extension(mime_type)
        filename = f'{media_sid}{file_extension}'

        response = requests.get(media_url, headers=auth_header, stream=True)

        # Create a temporary file
        fd, temp_file_path = tempfile.mkstemp(suffix=file_extension)
        with os.fdopen(fd, 'wb') as temp_file:
            temp_file.write(response.content)


        extracted_data = process_receipt(temp_file_path, mime_type)
        print(extracted_data)

        if extracted_data is None:
            client.messages.create(
                from_=f"whatsapp:{TWILIO_NUMBER}",
                body="Error processing receipt data. Please try again with a clear image or PDF.",
                to=f"whatsapp:{user_phone}"
            )
            return

        form_data = {
            'date': extracted_data.get("date"),
            'vendor': extracted_data.get("vendor"),
            'total_amount': extracted_data.get("total_amount")
        }

        file_temp_in_memory = InMemoryUploadedFile(
            file=BytesIO(response.content),
            field_name='file',
            name=filename,
            content_type=mime_type,
            size=len(response.content),
            charset=None
        )

        form = ReceiptForm(form_data, files={'file': file_temp_in_memory})
        if form.is_valid():
            receipt = form.save(commit=False)
            receipt.user = user
            receipt.save()
            formatted_data = f"Your receipt was processed !! \n" \
                             f"Receipt Details:\n" \
                             f"Date: {form_data['date']}\n" \
                             f"Vendor: {form_data['vendor']}\n" \
                             f"Total Amount: ${form_data['total_amount']:.2f}\n"

            client.messages.create(
                from_=f"whatsapp:{TWILIO_NUMBER}",
                body=formatted_data,
                to=f"whatsapp:{user_phone}"
            )
        else:
            print(form.errors.as_json())
            client.messages.create(
                from_=f"whatsapp:{TWILIO_NUMBER}",
                body="Error processing receipt data. Please try again with a clear image or PDF.",
                to=f"whatsapp:{user_phone}"
            )

    except Exception as e:
        print(f"Error in process_receipt_thread: {str(e)}")
        client.messages.create(
            from_=f"whatsapp:{TWILIO_NUMBER}",
            body="An error occurred while processing your receipt. Please try again.",
            to=f"whatsapp:{user_phone}"
        )
    finally:
        # Clean up the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def process_query_thread(user, message, client, user_phone):
    try:
        connection.close()

        result = process_receipt_query(user=user, query=message)
        print(result)

        if not result:
            result = 'Sorry I was not able to solve your query, can you try again'

        client.messages.create(
            from_=f"whatsapp:{TWILIO_NUMBER}",
            body=result,
            to=f"whatsapp:{user_phone}"
        )

    except Exception as e:
        print(f"Error in process_query_thread: {str(e)}")
        client.messages.create(
            from_=f"whatsapp:{TWILIO_NUMBER}",
            body="An error occurred while processing your query. Please try again.",
            to=f"whatsapp:{user_phone}"
        )