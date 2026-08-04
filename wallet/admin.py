from decimal import Decimal

from django import forms
from django.contrib import admin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Wallet, Transaction, GlobalConfig


class WalletTopUpForm(forms.Form):
    amount = forms.DecimalField(
        min_value=Decimal('0.01'),
        max_digits=14,
        decimal_places=2,
        label='Amount (credits)',
        help_text='Number of credits to add to this wallet.',
    )
    notes = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Admin Notes',
        help_text='Optional reason or context for this manual top-up.',
    )


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_email', 'balance', 'topup_button')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('user', 'balance', 'topup_button')
    ordering = ('user__email',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    @admin.display(description='Email', ordering='user__email')
    def get_email(self, obj):
        return obj.user.email

    @admin.display(description='Top Up')
    def topup_button(self, obj):
        url = reverse('admin:wallet-topup', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="padding:4px 10px;background:#417690;color:#fff;border-radius:4px;text-decoration:none;font-size:12px;">Top Up</a>',
            url,
        )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<pk>/topup/',
                self.admin_site.admin_view(self.topup_view),
                name='wallet-topup',
            ),
        ]
        return custom + urls

    def topup_view(self, request, pk):
        wallet = get_object_or_404(Wallet, pk=pk)

        if request.method == 'POST':
            form = WalletTopUpForm(request.POST)
            if form.is_valid():
                amount = form.cleaned_data['amount']
                notes = form.cleaned_data.get('notes', '')
                admin_label = f'Admin top-up by {request.user.email}'
                full_notes = f'{admin_label}. {notes}'.strip(' .') if notes else admin_label

                wallet.topup(
                    amount=amount,
                    created_by=request.user,
                    notes=full_notes,
                    initiated_by_admin=True,
                )

                self.message_user(
                    request,
                    f'Successfully added {amount} credits to {wallet.user.email}\'s wallet. '
                    f'New balance: {wallet.balance} credits.',
                )
                return redirect(reverse('admin:wallet_wallet_change', args=[pk]))
        else:
            form = WalletTopUpForm()

        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'wallet': wallet,
            'title': f'Top Up Wallet — {wallet.user}',
            'opts': self.model._meta,
        }
        return render(request, 'admin/wallet/wallet/topup.html', context)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'get_user_email', 'amount', 'withdrawable_amount',
        'service_fee', 'type', 'flow', 'initiated_by_admin', 'get_initiated_by', 'created',
    )
    list_filter = ('type', 'flow', 'initiated_by_admin', 'created')
    search_fields = ('wallet__user__email', 'wallet__user__first_name', 'wallet__user__last_name', 'notes', 'created_by__email')
    readonly_fields = ('created', 'modified', 'initiated_by_admin', 'created_by', 'notes')
    raw_id_fields = ('wallet',)
    ordering = ('-created',)

    fieldsets = (
        ('Transaction', {
            'fields': ('wallet', 'amount', 'withdrawable_amount', 'service_fee', 'type', 'flow'),
        }),
        ('Admin Info', {
            'fields': ('initiated_by_admin', 'created_by', 'notes'),
        }),
        ('Timestamps', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('wallet__user', 'created_by')

    @admin.display(description='User Email', ordering='wallet__user__email')
    def get_user_email(self, obj):
        return obj.wallet.user.email

    @admin.display(description='Initiated By', ordering='created_by__email')
    def get_initiated_by(self, obj):
        if obj.created_by:
            return obj.created_by.email
        return '—'


@admin.register(GlobalConfig)
class GlobalConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'free_credit')
