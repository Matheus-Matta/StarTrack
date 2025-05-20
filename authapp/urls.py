from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.urls import reverse_lazy
app_name = 'authapp'

urlpatterns = [
    # page register and login
    path('login/', views.custom_login, name='login'),
    path('register/', views.register, name='register'),

    # url logout
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Reset password
    path('password_reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='authapp/password_reset_form.html',
             email_template_name='authapp/emails/password_reset_email.html',
             subject_template_name='authapp/subject/password_reset_subject.txt',
             success_url=reverse_lazy('authapp:password_reset_done')
         ), 
         name='password_reset'),
    
    path('password_reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='authapp/password_reset_done.html'
         ), 
         name='password_reset_done'),

    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='authapp/password_reset_confirm.html',
             success_url='/auth/reset/done/'
         ), 
         name='password_reset_confirm'),

    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='authapp/password_reset_complete.html'
         ), 
         name='password_reset_complete'),

    # ALTERAR SENHA (usuário logado)
    path('password_change/', 
         auth_views.PasswordChangeView.as_view(
             template_name='authapp/password_change_form.html',
             success_url='/auth/password_change/done/'
         ), 
         name='password_change'),

    path('password_change/done/', 
         auth_views.PasswordChangeDoneView.as_view(
             template_name='authapp/password_change_done.html'
         ), 
         name='password_change_done'),
]