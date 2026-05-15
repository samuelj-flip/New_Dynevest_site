from django.contrib import admin
from .models import Profile, Plan, Deposit, Investment, Withdrawal

admin.site.register(Profile)
admin.site.register(Plan) 
admin.site.register(Deposit)
admin.site.register(Investment)
admin.site.register(Withdrawal)