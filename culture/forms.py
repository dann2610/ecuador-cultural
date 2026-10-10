from django import forms

from core.forms import BootstrapFormMixin

from .models import Craft, CulturalContent, Dish, Festivity

COMMON = ["source", "author_entity"]


class CulturalContentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CulturalContent
        fields = ["kind", "category", "title", "description", "photo"] + COMMON

    def __init__(self, *args, community=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["photo"].queryset = community.photos.all() if community else self.fields["photo"].queryset.none()


class DishForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Dish
        fields = ["name", "description", "ingredients", "cultural_context", "image", "image_credit"] + COMMON


class CraftForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Craft
        fields = ["name", "kind", "description", "materials", "technique", "cultural_meaning", "image",
                  "image_credit"] + COMMON


class FestivityForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Festivity
        fields = ["name", "period", "location", "description", "history", "visitor_tips", "image",
                  "image_credit"] + COMMON
