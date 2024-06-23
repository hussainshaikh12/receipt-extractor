from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_user, name='register'),
    path('verify_otp/', views.verify_otp, name='verify_otp'),
    path('process_whatsapp_receipt/', views.process_whatsapp_receipt, name='process_whatsapp_receipt'),
]