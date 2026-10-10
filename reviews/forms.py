from django import forms

from core.forms import BootstrapFormMixin

from .models import Review


class ReviewForm(BootstrapFormMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(label="Puntuación", coerce=int,
                                    choices=[(i, "★" * i) for i in range(5, 0, -1)])

    class Meta:
        model = Review
        fields = ["rating", "comment", "photo"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 3, "placeholder": "Cuéntanos tu experiencia real…"})}

    def clean_comment(self):
        text = self.cleaned_data["comment"].strip()
        if len(text) < 10:
            raise forms.ValidationError("Escribe al menos 10 caracteres.")
        return text
