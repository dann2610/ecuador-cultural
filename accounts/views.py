from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from communities.models import Favorite
from core.models import Notification

from .forms import LoginForm, NewPasswordForm, ProfileForm, ResetForm, SignUpForm


def signup(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "¡Bienvenido/a a Ecuador Cultural! Tu cuenta fue creada.")
        return redirect("accounts:profile")
    return render(request, "accounts/signup.html", {"form": form})


class RoleLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        nxt = self.request.POST.get("next") or self.request.GET.get("next")
        if nxt and url_has_allowed_host_and_scheme(nxt, {self.request.get_host()},
                                                   require_https=self.request.is_secure()):
            return nxt
        user = self.request.user
        if user.is_platform_admin:
            return reverse("core:admin_dashboard")
        if user.is_representative:
            return reverse("core:rep_dashboard")
        return reverse("core:home")

    def form_valid(self, form):
        messages.success(self.request, f"Hola, {form.get_user()}.")
        return super().form_valid(form)


class PasswordReset(auth_views.PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    form_class = ResetForm
    success_url = reverse_lazy("accounts:password_reset_done")


class PasswordResetConfirm(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = NewPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Perfil actualizado.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def favorites(request):
    favs = (Favorite.objects.filter(user=request.user)
            .select_related("community__province", "place__community"))
    trips_fav = request.user.favorite_itineraries.select_related("itinerary")
    return render(request, "accounts/favorites.html", {"favorites": favs, "fav_itineraries": trips_fav})


@login_required
def notifications(request):
    items = Notification.objects.filter(user=request.user)[:100]
    if request.method == "POST":
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        messages.info(request, "Notificaciones marcadas como leídas.")
        return redirect("accounts:notifications")
    return render(request, "accounts/notifications.html", {"items": items})
