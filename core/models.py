from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# 1. User Profile to track money
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_profit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) 
    
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
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(default=7)
    roi_percentage = models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self):
        return self.name
    
# 3. Deposits (Cleaned & Smart)
class Deposit(models.Model):
    STATUS_CHOICES = [('Pending', 'Pending'), ('Approved', 'Approved'), ('Declined', 'Declined')]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
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

# 4. Withdrawals
class Withdrawal(models.Model):
    STATUS_CHOICES = [('Pending', 'Pending'), ('Completed', 'Completed'), ('Declined', 'Declined')]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    wallet_address = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - ${self.amount}"

# ... (Keep everything from the previous cleaned version)

class Investment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"