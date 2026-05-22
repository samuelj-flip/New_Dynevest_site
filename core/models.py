from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# 1. User Profile
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00) # Deposited/Locked Capital
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00) # All-time historical profit
    
    # NEW CLIENT FEATURE: This tracks available withdrawable mining returns.
    mining_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00) 
    
    # Staff can edit this to increase/decrease mining speed (e.g., 0.0500 = 5% daily growth)
    mining_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0.0100) 

    # NEW CLIENT REQUIREMENT FIELDS
    require_external_deposit = models.BooleanField(default=False, help_text="Toggle if this user must deposit before withdrawing")
    required_deposit_percentage = models.IntegerField(default=10, help_text="Percentage (10-30%) required based on withdrawal amount")

    @property
    def total_assets(self):
        """
        Calculates the sum of balance and available mining balance on the fly.
        """
        return (self.balance or 0) + (self.mining_balance or 0)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"

# Signals to create Profile automatically
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)

# 2. Investment Plans
class Plan(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    duration_days = models.IntegerField(default=7)
    roi_percentage = models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self):
        return self.name
    
# 3. Deposits
class Deposit(models.Model):
    STATUS_CHOICES = [('Pending', 'Pending'), ('Approved', 'Approved'), ('Declined', 'Declined')]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    proof = models.ImageField(upload_to='deposit_proofs/')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            old_status = Deposit.objects.get(pk=self.pk).status
            if old_status != 'Approved' and self.status == 'Approved':
                profile = self.user.profile
                profile.balance += self.amount
                profile.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - ${self.amount} ({self.status})"

# 4. Withdrawals (This maps cleanly to your admin custom tracking)
class Withdrawal(models.Model):
    STATUS_CHOICES = [('Pending', 'Pending'), ('Completed', 'Completed'), ('Declined', 'Declined')]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    wallet_address = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - ${self.amount}"

# 5. Investments
class Investment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"
    

# 6. Unified Ledger Transactions (For logging and tracking history metrics)
class Transaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved & Completed'),
        ('failed', 'Rejected/Failed'),
    ]
    
    TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    wallet_address = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='withdrawal')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - {self.amount} ({self.status})"


class IntegrationSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='integrations')
    connected_service_name = models.CharField(max_length=50, default="Coinbase API")
    public_identifier = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="The public API key or username used for read-only data synchronization."
    )
    is_verified = models.BooleanField(default=False)
    last_synced = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.connected_service_name} Settings"
    

class AccountCompliance(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='compliance')
    is_premium_verified = models.BooleanField(default=False)
    verification_progress_percentage = models.IntegerField(default=0)  # Real progress tracking
    required_deposit_received = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.username} - Compliance Profile"