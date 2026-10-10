from django import forms


class BootstrapFormMixin:
    """Aplica las clases de Bootstrap 5 a todos los widgets del formulario."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, (forms.CheckboxInput,)):
                w.attrs.setdefault("class", "form-check-input")
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", "form-select")
            elif isinstance(w, forms.CheckboxSelectMultiple):
                continue
            else:
                w.attrs.setdefault("class", "form-control")
            if isinstance(w, forms.Textarea):
                w.attrs.setdefault("rows", 4)


DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
