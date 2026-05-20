from django.contrib import admin
from .models import Profile, Plan, Deposit, Investment, Withdrawal

# Custom configuration for your Withdrawal Model
class WithdrawalAdmin(admin.ModelAdmin):
    # Removed 'fee' from this list to fix the admin.E108 error
    list_display = ('user', 'amount', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__username', 'wallet_address')
    actions = ['approve_selected_withdrawals']

    def approve_selected_withdrawals(self, request, queryset):
        # Automatically updates the status column from 'pending' to 'approved'
        rows_updated = queryset.filter(status='pending').update(status='approved')
        self.message_user(request, f"Successfully marked {rows_updated} pending requests as Approved & Completed.")
    
    approve_selected_withdrawals.short_description = "Approve and execute selected pending withdrawals"


# Register your models
admin.site.register(Profile)
admin.site.register(Plan) 
admin.site.register(Deposit)
admin.site.register(Investment)

# Register Withdrawal with its updated configuration class
admin.site.register(Withdrawal, WithdrawalAdmin)