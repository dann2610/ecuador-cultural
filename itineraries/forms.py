from django import forms
from django.forms import inlineformset_factory

from communities.models import Community, Province
from core.forms import DATE_WIDGET, BootstrapFormMixin
from tourism.models import Place

from .models import CustomTrip, CustomTripStop, Itinerary, ItineraryStop


class ItineraryFilterForm(BootstrapFormMixin, forms.Form):
    DURATIONS = [("", "Cualquier duración"), ("1", "1 día"), ("2", "2 días"), ("3", "3 días o más")]
    q = forms.CharField(label="Buscar", required=False)
    province = forms.ModelChoiceField(Province.objects.all(), required=False, label="Provincia",
                                      empty_label="Todas", to_field_name="slug")
    kind = forms.ChoiceField(label="Categoría", required=False,
                             choices=[("", "Todas")] + list(Itinerary.Kind.choices))
    duration = forms.ChoiceField(label="Duración", required=False, choices=DURATIONS)
    max_budget = forms.DecimalField(label="Presupuesto máx. (USD)", required=False, min_value=0)


def _place_qs():
    return Place.objects.published().select_related("community").order_by("community__name", "name")


def _community_qs():
    return Community.objects.published().order_by("name")


class ItineraryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Itinerary
        fields = ["name", "kind", "description", "community", "province", "duration_days", "difficulty",
                  "budget_estimate", "budget_note", "distance_km", "estimates_verified", "recommendations",
                  "cover", "cover_credit", "source", "author_entity"]
        help_texts = {"budget_estimate": "Déjelo vacío si no hay datos fiables.",
                      "distance_km": "Déjelo vacío si no está confirmada.",
                      "estimates_verified": "Marque solo si distancias y tiempos fueron comprobados."}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None and not user.is_platform_admin:
            self.fields["community"].queryset = user.managed_communities()
            self.fields["community"].required = True


class ItineraryStopForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ItineraryStop
        fields = ["order", "day", "place", "community", "travel_time_note", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["place"].queryset = _place_qs()
        self.fields["community"].queryset = _community_qs()
        self.fields["order"].widget.attrs["min"] = 1

    def clean(self):
        data = super().clean()
        if self.cleaned_data.get("DELETE"):
            return data
        if bool(data.get("place")) == bool(data.get("community")):
            raise forms.ValidationError("Cada parada debe tener un lugar o un pueblo (solo uno).")
        return data


ItineraryStopFormSet = inlineformset_factory(
    Itinerary, ItineraryStop, form=ItineraryStopForm, extra=3, can_delete=True, min_num=1, validate_min=True)


class CustomTripForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CustomTrip
        fields = ["name", "start_date", "end_date", "notes"]
        widgets = {"start_date": DATE_WIDGET, "end_date": DATE_WIDGET, "notes": forms.Textarea(attrs={"rows": 2})}


class AddTripStopForm(BootstrapFormMixin, forms.Form):
    place = forms.ModelChoiceField(_place_qs(), required=False, label="Lugar", empty_label="— Elige un lugar —")
    community = forms.ModelChoiceField(_community_qs(), required=False, label="o un pueblo",
                                       empty_label="— Elige un pueblo —")
    visit_date = forms.DateField(required=False, label="Fecha de visita", widget=DATE_WIDGET)
    notes = forms.CharField(required=False, max_length=300, label="Notas")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["place"].queryset = _place_qs()
        self.fields["community"].queryset = _community_qs()

    def clean(self):
        data = super().clean()
        if bool(data.get("place")) == bool(data.get("community")):
            raise forms.ValidationError("Selecciona un lugar o un pueblo (solo uno).")
        return data


class TripStopDateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CustomTripStop
        fields = ["visit_date", "notes"]
        widgets = {"visit_date": DATE_WIDGET}
