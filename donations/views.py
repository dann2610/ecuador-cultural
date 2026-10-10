from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.permissions import manager_required
from core.services import log_action, notify, notify_admins

from .forms import DonationForm, ProjectUpdateForm
from .models import Donation, Project


def confirmed_annotation():
    return Sum("donations__amount", filter=Q(donations__status=Donation.Status.CONFIRMED))


def project_list(request):
    qs = (Project.objects.published().select_related("community__province")
          .annotate(confirmed_total=confirmed_annotation()))
    phase = request.GET.get("estado")
    if phase in Project.Phase.values:
        qs = qs.filter(phase=phase)
    page = Paginator(qs.order_by("-created_at"), 9).get_page(request.GET.get("page"))
    return render(request, "donations/project_list.html", {"page": page, "phases": Project.Phase.choices,
                                                            "current_phase": phase})


def project_detail(request, slug):
    project = get_object_or_404(Project.objects.select_related("community__province")
                                .annotate(confirmed_total=confirmed_annotation()), slug=slug)
    can_manage = request.user.is_authenticated and request.user.can_manage_community(project.community)
    if not project.is_published and not can_manage:
        raise Http404
    confirmed = project.donations.filter(status=Donation.Status.CONFIRMED)
    return render(request, "donations/project_detail.html", {
        "project": project, "updates": project.updates.all(), "can_manage": can_manage,
        "recent_confirmed": confirmed.order_by("-verified_at")[:10], "confirmed_count": confirmed.count(),
        "form": DonationForm(initial={"project": project}) if project.accepts_donations else None,
    })


@login_required
def donate(request):
    initial = {}
    if request.GET.get("proyecto"):
        initial["project"] = Project.objects.published().filter(slug=request.GET["proyecto"]).first()
    form = DonationForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        donation = form.save(commit=False)
        donation.user = request.user
        donation.save()
        log_action(request.user, "aporte_registrado", donation)
        notify_admins(f"Nuevo aporte por verificar: ${donation.amount} para {donation.project}",
                      reverse("core:admin_donations"))
        messages.success(request, "Registramos tu aporte. Aparecerá como confirmado cuando el administrador "
                                  "verifique el comprobante con la comunidad.")
        return redirect("donations:mine")
    return render(request, "donations/donate.html", {"form": form})


@login_required
def my_donations(request):
    donations = request.user.donations.select_related("project__community")
    return render(request, "donations/mine.html", {"donations": donations})


@manager_required
def add_update(request, slug):
    project = get_object_or_404(Project, slug=slug)
    if not request.user.can_manage_community(project.community):
        raise PermissionDenied
    form = ProjectUpdateForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        upd = form.save(commit=False)
        upd.project = project
        upd.created_by = request.user
        upd.save()
        log_action(request.user, "avance_publicado", upd)
        donors = {d.user for d in project.donations.filter(user__isnull=False).select_related("user")}
        for u in donors:
            notify(u, f"Nuevo avance en «{project.name}»: {upd.title}", project.get_absolute_url())
        messages.success(request, "Avance publicado.")
        return redirect(project.get_absolute_url() + "#avances")
    return render(request, "donations/update_form.html", {"form": form, "project": project})


@manager_required
def project_donations(request, slug):
    """Donaciones de un proyecto para su representante (sin datos privados innecesarios)."""
    project = get_object_or_404(Project.objects.annotate(confirmed_total=confirmed_annotation()), slug=slug)
    if not request.user.can_manage_community(project.community):
        raise PermissionDenied
    return render(request, "donations/project_donations.html", {
        "project": project, "donations": project.donations.all()})
