import random
from django.shortcuts import render, redirect, get_object_or_404
from .models import Girl
from django.http import Http404
from .forms import GirlCreateForm, registerForm, loginForm
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required


def indexView(request):
    allgirls = Girl.objects.count()
    if request.user.is_authenticated:
        mygirls = Girl.objects.filter(user=request.user)
        mygirlsCount = Girl.objects.filter(user=request.user).count()
    else:
        mygirls = None
        mygirlsCount = 0
    girls = list(Girl.objects.all())
    random.shuffle(girls)
    context = {
        'girls': girls,
        'mygirls': mygirls,
        'mycount': mygirlsCount,
        'all': allgirls
    }
    return render(request, 'index.html', context)


@login_required(login_url='login')
def addGirl(request):
    if request.method == 'POST':
        form = GirlCreateForm(request.POST, request.FILES)
        if form.is_valid():
            username = form.cleaned_data['username']
            if Girl.objects.filter(username=username).exists():
                form.errors['username'] = [
                    'Username is allready taken by someone, try another']
            else:
                detail = form.save(commit=False)
                detail.user = request.user
                form.save()
                return redirect('index')

    else:
        form = GirlCreateForm()

    return render(request, 'add.html', {'form': form})


@login_required(login_url='login')
def viewView(request, pk):
    thing = get_object_or_404(Girl, pk=pk)
    context = {
        'girl': thing,
    }
    return render(request, 'view.html', context)


@login_required(login_url='login')
def editView(request, pk):
    girl = get_object_or_404(Girl, pk=pk)
    if girl.user == request.user:
        if request.method == 'POST':
            form = GirlCreateForm(request.POST, request.FILES, instance=girl)
            if form.is_valid():
                form.save()
                return redirect('view', pk=pk)
        else:
            form = GirlCreateForm(instance=girl)
    else:
        raise Http404

    context = {
        'form': form,
    }
    return render(request, 'edit.html', context)


@login_required(login_url='login')
def delete_girl(request, girl_id):
    girl = get_object_or_404(Girl, id=girl_id)
    if request.user == girl.user:
        if request.method == 'POST':
            girl.delete()
            return redirect('index')
    else:
        raise Http404

    return render(request, 'delete.html', {'girl': girl})


def RegisterView(request):
    if request.method == 'POST':
        form = registerForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            password2 = form.cleaned_data['password2']

            if User.objects.filter(username=username).exists():
                form.errors['username'] = [
                    'Username is allready taken by someone, try another']
            elif User.objects.filter(email=email).exists():
                form.errors['username'] = [f'{email} is allready signed-up']
            elif password != password2:
                form.errors['username'] = ['passwords does not match']
            else:
                user = form.save(commit=False)
                user.set_password(password)
                form.save()
                login(request, user)
                return redirect('index')
    else:
        form = registerForm()
    return render(request, 'register.html', {'form': form})


def loginView(request):
    if request.method == 'POST':
        form = loginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            try:
                user = User.objects.get(email=email)
                username = user.username
                userAuth = authenticate(
                    request, username=username, password=password)
                if userAuth is not None:
                    login(request, user)
                    return redirect('index')
            except:
                form.errors['username'] = ['Invalid username or password']
    else:
        form = loginForm()
    return render(request, 'login.html', {'form': form})


def logoutView(request):
    logout(request)
    return redirect('login')
