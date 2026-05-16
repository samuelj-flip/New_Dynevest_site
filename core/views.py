from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Profile, Plan, Deposit, Investment, Withdrawal
from django.contrib import messages
from decimal import Decimal

@login_required
def dashboard_view(request):
    # This tries to get the profile. If it doesn't exist, it creates one!
    profile, created = Profile.objects.get_or_create(user=request.user)
    return render(request, 'core/dashboard.html', {'profile': profile})

@login_required
def dashboard_view(request):
    from .models import Profile  # <--- Move it here locally
    profile, created = Profile.objects.get_or_create(user=request.user)
    return render(request, 'core/dashboard.html', {'profile': profile})

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now login.')
            return redirect('login') # We will create the login url next
    else:
        form = UserCreationForm()
    return render(request, 'core/register.html', {'form': form})

def home_view(request):
    return render(request, 'core/home.html')

def investment_plans_view(request):
    plans = Plan.objects.all()
    return render(request, 'core/plans.html', {'plans': plans})

@login_required
def deposit_view(request):
    if request.method == "POST":
        amount = request.POST.get('amount')
        proof = request.FILES.get('proof')
        Deposit.objects.create(user=request.user, amount=amount, proof_of_payment=proof)
        return redirect('dashboard')
    return render(request, 'core/deposit.html')

@login_required
def dashboard_view(request):
    profile = request.user.profile
    deposits = Deposit.objects.filter(user=request.user).order_by('-created_at')
    
    # NEW: Fetch active investments
    active_investments = Investment.objects.filter(user=request.user, is_active=True)
    
    return render(request, 'core/dashboard.html', {
        'profile': profile,
        'deposits': deposits,
        'active_investments': active_investments # Pass this to the template
    })

@login_required
def dashboard(request):
    profile = request.user.profile
    # Get all deposits for this user, newest first
    deposits = Deposit.objects.filter(user=request.user).order_some('-created_at')
    active_investments = Investment.objects.filter(user=request.user, is_active=True)
    # Note: We added total_profit to the model, so we don't need a new view query!
    return render(request, 'core/dashboard.html', {
        'profile': profile,
        'deposits': deposits
    })

@login_required
def transactions_view(request):
    deposits = Deposit.objects.filter(user=request.user).order_by('-created_at')
    withdrawals = Withdrawal.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'core/transactions.html', {
        'deposits': deposits,
        'withdrawals': withdrawals,
    })

@login_required
def buy_plan(request, plan_id):
    plan = Plan.objects.get(id=plan_id)
    profile = request.user.profile

    if profile.balance >= plan.price:
        # 1. Deduct the money
        profile.balance -= plan.price
        profile.save()

        # 2. Create the investment record
        Investment.objects.create(user=request.user, plan=plan, amount=plan.price)
        
        messages.success(request, f"Successfully invested in {plan.name}!")
        return redirect('dashboard')
    else:
        messages.error(request, "Insufficient funds. Please make a deposit.")
        return redirect('deposit')
    
@login_required
def withdraw_view(request):
    profile = request.user.profile
    if request.method == "POST":
        amount_str = request.POST.get('amount')
        address = request.POST.get('wallet_address')
        
        if amount_str:
            # CHANGE THIS LINE: float() -> Decimal()
            amount = Decimal(amount_str) 
            
            if amount <= profile.balance:
                profile.balance -= amount
                profile.save()
                
                Withdrawal.objects.create(
                    user=request.user, 
                    amount=amount, 
                    wallet_address=address
                )
                messages.success(request, "Withdrawal requested successfully!")
                return redirect('dashboard')
            else:
                messages.error(request, "Insufficient funds!")
    return render(request, 'core/withdraw.html', {'profile': profile})