from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from django.conf import settings
from .forms import LoginForm, RegisterForm
from django.views.decorators.csrf import csrf_protect
@csrf_protect
def custom_login(request):
    next_url = request.GET.get('next') or request.POST.get('next') or 'index'
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password']
            )
            if user is not None:
                login(request, user)

                # Expiração da sessão
                if form.cleaned_data.get('remember_me'):
                    request.session.set_expiry(60 * 60 * 24 * 30)  # 30 dias
                else:
                    request.session.set_expiry(0)  # até o navegador fechar

                # Segurança: valida se o next está no mesmo domínio
                if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                    return redirect(next_url)
                return redirect('index')
            else:
                messages.error(request, 'Usuário ou senha inválidos.')
    else:
        form = LoginForm()

    return render(request, 'authapp/login.html', {'form': form, 'next': next_url})

def register(request):
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Login automático após cadastro (opcional)
            login(request, user)
            messages.success(request, 'Cadastro realizado com sucesso!')

            # Valida se o next é seguro
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect('index')  # Página principal após cadastro
        else:
            messages.error(request, 'Erro ao realizar o cadastro. Verifique os campos.')
    else:
        form = RegisterForm()

    return render(request, 'authapp/register.html', {
        'form': form,
        'next': next_url
    })