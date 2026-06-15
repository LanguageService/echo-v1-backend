from django.core.management.base import BaseCommand
from billing.models import PricingConfig
from decimal import Decimal

class Command(BaseCommand):
    help = 'Seeds the database with the agreed upon pricing rates for ECHO UI and API.'

    def handle(self, *args, **options):
        # Define the exact pricing provided by the user
        pricing_data = [
            # UI (Consumer)
            {'channel': 'UI', 'translation_type': 'STS', 'cost_per_unit': '0.05'},
            {'channel': 'UI', 'translation_type': 'STT', 'cost_per_unit': '0.02'},
            {'channel': 'UI', 'translation_type': 'TTT', 'cost_per_unit': '1.00'},
            {'channel': 'UI', 'translation_type': 'TTS', 'cost_per_unit': '0.01'},
            
            # API (Developer)
            {'channel': 'API', 'translation_type': 'STS', 'cost_per_unit': '0.08'},
            {'channel': 'API', 'translation_type': 'STT', 'cost_per_unit': '0.03'},
            {'channel': 'API', 'translation_type': 'TTT', 'cost_per_unit': '1.50'},
            {'channel': 'API', 'translation_type': 'TTS', 'cost_per_unit': '0.015'},
        ]

        count = 0
        for config in pricing_data:
            obj, created = PricingConfig.objects.update_or_create(
                channel=config['channel'],
                translation_type=config['translation_type'],
                defaults={'cost_per_unit': Decimal(config['cost_per_unit'])}
            )
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{action}: {obj.channel} - {obj.translation_type} = ${obj.cost_per_unit}"))
            count += 1
            
        self.stdout.write(self.style.SUCCESS(f"Successfully processed {count} pricing configurations."))
