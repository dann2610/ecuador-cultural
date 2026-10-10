from django import forms

from core.forms import BootstrapFormMixin

from .models import Canton, Category, Community, CommunityRequest, Photo, Province


class CommunityFilterForm(BootstrapFormMixin, forms.Form):
    ORDER_CHOICES = [("name", "Nombre (A-Z)"), ("-name", "Nombre (Z-A)"), ("recent", "Más recientes"),
                     ("rating", "Mejor valorados")]
    q = forms.CharField(label="Buscar", required=False,
                        widget=forms.TextInput(attrs={"placeholder": "Nombre del pueblo o comunidad"}))
    province = forms.ModelChoiceField(Province.objects.all(), label="Provincia", required=False,
                                      empty_label="Todas las provincias", to_field_name="slug")
    canton = forms.ModelChoiceField(Canton.objects.select_related("province"), label="Cantón", required=False,
                                    empty_label="Todos los cantones")
    category = forms.ModelChoiceField(Category.objects.all(), label="Categoría", required=False,
                                      empty_label="Todas las categorías", to_field_name="slug")
    order = forms.ChoiceField(label="Ordenar", choices=ORDER_CHOICES, required=False)


class CommunityForm(BootstrapFormMixin, forms.ModelForm):
    """Edición de la información de un pueblo (administrador o representante asignado)."""

    class Meta:
        model = Community
        fields = ["name", "province", "canton", "parish", "short_description", "categories", "history",
                  "identity", "clothing", "music_dance", "activities", "latitude", "longitude",
                  "source", "author_entity"]
        widgets = {"categories": forms.CheckboxSelectMultiple}
        help_texts = {
            "latitude": "Use coordenadas comprobadas (p. ej. -2.897400). Déjelo vacío si aún no está verificado.",
            "history": "Solo información documentada. Indique la fuente abajo.",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["canton"].queryset = Canton.objects.select_related("province")
        if user is not None and user.is_platform_admin:
            self.fields["location_verified"] = forms.BooleanField(
                label="Ubicación verificada", required=False, initial=self.instance.location_verified,
                widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))

    def clean(self):
        data = super().clean()
        lat, lng = data.get("latitude"), data.get("longitude")
        if (lat is None) != (lng is None):
            raise forms.ValidationError("Ingrese latitud y longitud juntas, o deje ambas vacías.")
        canton, province = data.get("canton"), data.get("province")
        if canton and province and canton.province_id != province.id:
            self.add_error("canton", "El cantón no pertenece a la provincia seleccionada.")
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if "location_verified" in self.cleaned_data:
            obj.location_verified = self.cleaned_data["location_verified"]
        elif self.has_changed() and {"latitude", "longitude"} & set(self.changed_data):
            obj.location_verified = False  # cambios de coordenadas de un representante requieren validación
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class PhotoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Photo
        fields = ["image", "title", "description", "place", "kind", "alt_text", "author", "source", "license",
                  "is_featured", "is_cover", "order"]
        help_texts = {
            "license": "Ej.: «CC BY-SA 4.0», «Autorización escrita de la comunidad», «Fotografía propia».",
            "is_featured": "Máximo 3 por pueblo: rotan automáticamente en la tarjeta del catálogo.",
        }

    def __init__(self, *args, community=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.community = community or getattr(self.instance, "community", None)
        from tourism.models import Place

        self.fields["place"].required = False
        self.fields["place"].queryset = Place.objects.filter(community=self.community) if self.community \
            else Place.objects.none()
        self.fields["place"].help_text = "Opcional: asocie la foto a un lugar específico del pueblo."

    def clean(self):
        data = super().clean()
        if data.get("is_featured") and self.community is not None:
            others = Photo.objects.filter(community=self.community, is_featured=True).exclude(pk=self.instance.pk)
            if others.count() >= Photo.MAX_FEATURED:
                self.add_error("is_featured", "Este pueblo ya tiene 3 fotografías destacadas. Desmarque otra primero.")
        return data


class CommunityRequestForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CommunityRequest
        fields = ["community_name", "province", "canton", "role_in_community", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 5})}


class FeaturedCarouselForm(BootstrapFormMixin, forms.Form):
    """Selección de los cuatro destinos del carrusel principal."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Community.objects.published().select_related("province")
        current = {c.featured_order: c for c in Community.objects.filter(featured_order__isnull=False)}
        for i in range(1, 5):
            self.fields[f"slot_{i}"] = forms.ModelChoiceField(
                qs, label=f"Diapositiva {i}", required=False, initial=current.get(i),
                empty_label="— Sin asignar (se usará un destino de demostración) —",
                widget=forms.Select(attrs={"class": "form-select"}))

    def clean(self):
        data = super().clean()
        chosen = [c for c in (data.get(f"slot_{i}") for i in range(1, 5)) if c]
        if len(chosen) != len({c.pk for c in chosen}):
            raise forms.ValidationError("No repita un mismo destino en dos diapositivas.")
        return data

    def save(self):
        Community.objects.filter(featured_order__isnull=False).update(featured_order=None)
        for i in range(1, 5):
            c = self.cleaned_data.get(f"slot_{i}")
            if c:
                Community.objects.filter(pk=c.pk).update(featured_order=i)
