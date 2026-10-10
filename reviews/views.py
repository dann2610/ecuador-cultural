from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from communities.models import Community
from tourism.models import Place

from .forms import ReviewForm
from .models import Review


def _target(kind, slug):
    if kind == "pueblo":
        return "community", get_object_or_404(Community.objects.published(), slug=slug)
    if kind == "lugar":
        return "place", get_object_or_404(Place.objects.published(), slug=slug)
    raise PermissionDenied


@login_required
@require_POST
def create_review(request, kind, slug):
    field, target = _target(kind, slug)
    form = ReviewForm(request.POST, request.FILES)
    if form.is_valid():
        review = form.save(commit=False)
        review.user = request.user
        setattr(review, field, target)
        try:
            with transaction.atomic():
                review.save()
            messages.success(request, "¡Gracias! Tu reseña fue publicada.")
        except IntegrityError:
            messages.warning(request, "Ya publicaste una reseña aquí. Puedes editarla.")
    else:
        for errs in form.errors.values():
            messages.error(request, " ".join(errs))
    return redirect(target.get_absolute_url() + "#resenas")


@login_required
def edit_review(request, pk):
    review = get_object_or_404(Review, pk=pk)
    if review.user_id != request.user.id:
        raise PermissionDenied
    if review.status == Review.Status.HIDDEN:
        messages.warning(request, "Esta reseña fue ocultada por moderación y no puede editarse.")
        return redirect(review.get_absolute_url())
    form = ReviewForm(request.POST or None, request.FILES or None, instance=review)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Reseña actualizada.")
        return redirect(review.get_absolute_url())
    return render(request, "reviews/edit.html", {"form": form, "review": review})


@login_required
@require_POST
def delete_review(request, pk):
    review = get_object_or_404(Review, pk=pk)
    if review.user_id != request.user.id and not request.user.is_platform_admin:
        raise PermissionDenied
    url = review.get_absolute_url()
    review.delete()
    messages.success(request, "Reseña eliminada.")
    return redirect(url)


@login_required
def my_reviews(request):
    reviews = Review.objects.filter(user=request.user).select_related("community", "place")
    return render(request, "reviews/mine.html", {"reviews": reviews})
