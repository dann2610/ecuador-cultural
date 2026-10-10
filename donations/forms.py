import re

from django import forms

from core.forms import DATE_WIDGET, BootstrapFormMixin

from .models import Donation, Project, ProjectUpdate

CARD_LIKE = re.compile(r"(?:\d[ -]?){13,19}")


class DonationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Donation
        fields = ["project", "amount", "donor_name", "is_anonymous", "method", "transaction_reference", "receipt"]
        help_texts = {
            "receipt": "Opcional: imagen o PDF del comprobante (máx. 5 MB).",
            "is_anonymous": "Si lo marcas, tu nombre no se mostrará públicamente.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.published().filter(
            phase__in=[Project.Phase.FUNDRAISING, Project.Phase.IN_PROGRESS]).select_related("community")
        self.fields["project"].empty_label = "— Selecciona un proyecto —"
        self.fields["method"].choices = [c for c in Donation.Method.choices if c[0] != Donation.Method.GATEWAY]
        self.fields["amount"].widget.attrs.update({"min": "1", "step": "0.01"})

    def clean_transaction_reference(self):
        ref = self.cleaned_data.get("transaction_reference", "").strip()
        if CARD_LIKE.fullmatch(ref.replace(" ", "")) or CARD_LIKE.search(ref):
            raise forms.ValidationError("Por seguridad no ingreses números de tarjeta. "
                                        "Usa solo el número de comprobante o transferencia.")
        return ref

    def save(self, commit=True):
        obj = super().save(commit=False)
        # Nunca se confirma automáticamente: sin pasarela real, solo un administrador verifica.
        obj.status = Donation.Status.UNDER_REVIEW if (obj.receipt or obj.transaction_reference) \
            else Donation.Status.PLEDGED
        if commit:
            obj.save()
        return obj


class ProjectForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description", "objective", "goal_amount", "start_date", "deadline", "phase",
                  "responsible_name", "image", "image_credit", "payment_instructions", "source"]
        widgets = {"start_date": DATE_WIDGET, "deadline": DATE_WIDGET}

    def clean(self):
        data = super().clean()
        if data.get("deadline") and data.get("start_date") and data["deadline"] < data["start_date"]:
            self.add_error("deadline", "La fecha límite debe ser posterior al inicio.")
        return data


class ProjectUpdateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProjectUpdate
        fields = ["title", "date", "description", "evidence"]
        widgets = {"date": DATE_WIDGET}
