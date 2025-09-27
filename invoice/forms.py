from django import forms
from .models import BankAccount, Company, AccountItem, InvoiceCode
from django.forms import modelformset_factory


"""
計上する項目を入力する
"""

class AccountItemForm(forms.ModelForm):
    DELETE = forms.BooleanField(required=False, widget=forms.HiddenInput) 
    
    class Meta:
        model = AccountItem
        fields = '__all__'
        widgets = {
            'invoice_bt': forms.TextInput(attrs={

                'class': 'form-control',
                'oninput': 'formatWithCommas(this)',
                'style': 'text-align: right;',
            }),
            'invoice_tax': forms.TextInput(attrs={
                'class': 'form-control',
                'oninput': 'formatWithCommas(this)',
                'style': 'text-align: right;',
            }),
            'invoice_at': forms.TextInput(attrs={
                'class': 'form-control',
                'oninput': 'formatWithCommas(this)',
                'style': 'text-align: right;',
            }),
        }

AccountItemFormSet = modelformset_factory(AccountItem, form=AccountItemForm, fields='__all__', extra=1, can_delete=True)

"""
請求書コードを修正
"""

class InvoiceCodeForm(forms.ModelForm):
    DELETE = forms.BooleanField(required=False, widget=forms.HiddenInput) 
    
    class Meta:
        model = InvoiceCode
        fields = '__all__'
        widgets = {
            'invoice_bt_ttl': forms.TextInput(attrs={

                'class': 'form-control',
                'oninput': 'formatWithCommas(this)',
                'style': 'text-align: right;',
            }),
            'invoice_tax_ttl': forms.TextInput(attrs={
                'class': 'form-control',
                'oninput': 'formatWithCommas(this)',
                'style': 'text-align: right;',
            }),
            'invoice_at_ttl': forms.TextInput(attrs={
                'class': 'form-control',
                'oninput': 'formatWithCommas(this)',
                'style': 'text-align: right;',
            }),
        }

InvoiceCodeFormSet = modelformset_factory(InvoiceCode, form=InvoiceCodeForm, fields='__all__', extra=1, can_delete=True)