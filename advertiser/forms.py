from django import forms
from .models import Girl
from django.contrib.auth.models import User

class GirlCreateForm(forms.ModelForm):
    class Meta:
        model = Girl
        fields = '__all__'
        exclude = ['user']

class registerForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)
    class Meta:
        model = User
        fields = ['username', 'email','password', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.fields['username'].help_text = ''

class loginForm(forms.Form):
    email = forms.EmailField(max_length=100, label='email')
    password = forms.CharField(widget=forms.PasswordInput, label='password')