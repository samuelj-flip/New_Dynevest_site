from django.shortcuts import redirect
from django.urls import reverse

class ComplianceLockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Let unauthenticated users see public pages
        if not request.user.is_authenticated:
            return self.get_response(request)

        # 2. SAFE PASS: Allow assets, styles, and uploads to load normally
        current_path = request.path
        if (
            current_path.startswith('/static/') or 
            current_path.startswith('/media/') or 
            current_path.startswith('/admin/') or 
            current_path.startswith('/staff/')
        ):
            return self.get_response(request)

        # 3. Define allowed named routes
        allowed_url_names = ['compliance_status', 'logout', 'deposit']
        allowed_paths = []
        for name in allowed_url_names:
            try:
                allowed_paths.append(reverse(name))
            except:
                pass
        
        # 4. If they are on an allowed page, let them through
        if current_path in allowed_paths:
            return self.get_response(request)

        # 5. Enforce the lock
        try:
            if request.user.profile.require_external_deposit:
                return redirect('compliance_status')
        except AttributeError:
            pass

        return self.get_response(request)