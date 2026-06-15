from rest_framework import permissions
from wallet.models import Wallet

class HasTranslationQuota(permissions.BasePermission):
    """
    Checks if the user has enough wallet balance to perform a translation.
    - Developer APIs deduct metered USD dynamically.
    - Consumer UI deducts Credits (fixed rates).
    
    Both deduct from the Wallet balance. We simply check if balance > 0 or if 
    it's an anonymous user that still has free trials remaining.
    """
    
    def has_permission(self, request, view):
        # Allow read operations
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Anonymous users are handled by check_and_increment_trial in the view
        if not request.user or not request.user.is_authenticated:
            return True
            
        user = request.user
        
        # SuperAdmins always bypass quotas
        if user.user_type in ['SUPER_ADMIN', 'OPERATOR']:
            return True

        wallet = Wallet.fetch_for_user(user)
        if wallet.balance > 0:
            return True
            
        self.message = "Payment Required. Please top-up your wallet to continue."
        return False
