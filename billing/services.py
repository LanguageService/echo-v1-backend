from django.db import transaction
from decimal import Decimal
from wallet.models import Wallet
from .models import PricingConfig

class BillingService:
    @staticmethod
    @transaction.atomic
    def calculate_and_deduct_cost(user, channel, translation_type, units) -> dict:
        """
        Calculates the cost of a translation and deducts it from the user's wallet.
        Returns a dict: {'success': bool, 'cost_deducted': Decimal, 'currency': str, 'error': str}
        """
        # SuperAdmins bypass this if we want, but typically we want to log it or skip deduction
        if user.user_type in ['SUPER_ADMIN', 'OPERATOR']:
            return {'success': True, 'cost_deducted': Decimal('0'), 'currency': 'FREE', 'error': None}

        try:
            config = PricingConfig.objects.get(channel=channel, translation_type=translation_type)
        except PricingConfig.DoesNotExist:
            # If no pricing config exists, default to failing to prevent free translations
            # Alternatively, could default to a hardcoded rate.
            return {'success': False, 'error': f"No pricing config found for {channel} - {translation_type}", 'cost_deducted': 0, 'currency': ''}

        cost = config.cost_per_unit * Decimal(str(units))
        currency = "USD" if channel == "API" else "CREDITS"

        wallet = Wallet.fetch_for_user(user)

        if wallet.balance < cost:
            return {'success': False, 'error': f"Insufficient wallet balance. Needed: {cost} {currency}", 'cost_deducted': 0, 'currency': currency}

        wallet.balance -= cost
        wallet.save()

        return {'success': True, 'cost_deducted': cost, 'currency': currency, 'error': None}
