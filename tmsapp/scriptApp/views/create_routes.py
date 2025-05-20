from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import os
from django.conf import settings
import uuid
from tmsapp.tasks import create_routes_task


@login_required
def create_routes(request):
    if request.method == "POST":
        sp_router = request.POST.get("sp_router")
        file = request.FILES.get("upload_file")

        if not file:
            messages.error(request, "Nenhum arquivo enviado.")
            return redirect('tmsapp:create_scripting')
 
        ext = os.path.splitext(file.name)[1].lower()
        ALLOWED_EXTENSIONS = ['.xlsx', '.xls', '.csv']
        if ext not in ALLOWED_EXTENSIONS:
            messages.error(request, "Formato de arquivo não suportado. Envie um arquivo .xlsx, .xls ou .csv.")
            return redirect('tmsapp:create_scripting')

        try:
            temp_dir = os.path.join(settings.BASE_DIR, 'temp')
            os.makedirs(temp_dir, exist_ok=True)  # Garante que a pasta exista

            ext = os.path.splitext(file.name)[1].lower()
            temp_filename = f"{uuid.uuid4()}{ext}"
            temp_file_path = os.path.join(temp_dir, temp_filename)

            with open(temp_file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)

            task = create_routes_task.delay(request.user.id, sp_router, temp_file_path)
            return redirect('tmsapp:route_loading', task.id)

        except Exception as e:
            messages.error(request, f"Erro ao iniciar o processo: {str(e)}")
            return redirect('tmsapp:create_scripting')

    return redirect('tmsapp:create_scripting')

