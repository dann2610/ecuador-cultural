from django import forms

from core.forms import BootstrapFormMixin

from .models import Place, TouristService


class PlaceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Place
        fields = ["name", "kind", "description", "heritage_features", "visiting_rules", "address", "opening_hours",
                  "latitude", "longitude", "source", "author_entity"]
        help_texts = {"latitude": "Solo coordenadas comprobadas. Déjelo vacío si la ubicación no está validada.",
                      "opening_hours": "Déjelo vacío si no está confirmado."}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None and user.is_platform_admin:
            self.fields["location_verified"] = forms.BooleanField(
                label="Ubicación verificada", required=False, initial=self.instance.location_verified,
                widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))

    def clean(self):
        data = super().clean()
        if (data.get("latitude") is None) != (data.get("longitude") is None):
            raise forms.ValidationError("Ingrese latitud y longitud juntas, o deje ambas vacías.")
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if "location_verified" in self.cleaned_data:
            obj.location_verified = self.cleaned_data["location_verified"]
        elif {"latitude", "longitude"} & set(self.changed_data):
            obj.location_verified = False
        if commit:
            obj.save()
        return obj


class TouristServiceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TouristService
        fields = ["name", "kind", "description", "contact", "price_note", "source", "author_entity"]
