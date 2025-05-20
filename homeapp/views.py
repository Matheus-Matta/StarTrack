from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import datetime
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date

# Create your views here.
@login_required
def DashboardView(request):
    return render(request, 'index.html')