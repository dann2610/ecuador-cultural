from django.urls import path

from .views import admin_panel, manage, public

app_name = "core"

urlpatterns = [
    path("", public.home, name="home"),
    path("buscar/", public.search, name="search"),
    path("privacidad/", public.privacy, name="privacy"),
    path("condiciones/", public.terms, name="terms"),
    path("acerca/", public.about, name="about"),
    # Panel del administrador
    path("panel/administracion/", admin_panel.dashboard, name="admin_dashboard"),
    path("panel/administracion/moderacion/", admin_panel.moderation, name="admin_moderation"),
    path("panel/administracion/moderar/<str:key>/<int:pk>/<str:action>/", admin_panel.moderate, name="moderate"),
    path("panel/administracion/destacados/", admin_panel.featured, name="admin_featured"),
    path("panel/administracion/donaciones/", admin_panel.donations, name="admin_donations"),
    path("panel/administracion/donaciones/<int:pk>/<str:action>/", admin_panel.donation_action,
         name="donation_action"),
    path("panel/administracion/resenas/", admin_panel.reviews, name="admin_reviews"),
    path("panel/administracion/resenas/<int:pk>/<str:action>/", admin_panel.review_action, name="review_action"),
    path("panel/administracion/solicitudes/", admin_panel.requests_list, name="admin_requests"),
    path("panel/administracion/solicitudes/<int:pk>/<str:action>/", admin_panel.request_action,
         name="request_action"),
    path("panel/administracion/comunidades/nueva/", admin_panel.community_create, name="community_create"),
    path("panel/administracion/usuarios/", admin_panel.users, name="admin_users"),
    path("panel/administracion/usuarios/<int:pk>/rol/", admin_panel.user_role, name="user_role"),
    path("panel/administracion/auditoria/", admin_panel.audit, name="admin_audit"),
    # Panel del representante y gestión por comunidad
    path("panel/representante/", manage.rep_dashboard, name="rep_dashboard"),
    path("panel/comunidad/<slug:slug>/", manage.manage_community, name="manage_community"),
    path("panel/comunidad/<slug:slug>/editar/", manage.edit_community, name="edit_community"),
    path("panel/comunidad/<slug:slug>/estado/", manage.community_status, name="community_status"),
    path("panel/comunidad/<slug:slug>/representantes/", admin_panel.assign_representative,
         name="assign_representative"),
    path("panel/comunidad/<slug:slug>/fotos/<int:pk>/mover/<str:direction>/", manage.photo_move, name="photo_move"),
    path("panel/comunidad/<slug:slug>/fotos/<int:pk>/marcar/<str:flag>/", manage.photo_flag, name="photo_flag"),
    path("panel/comunidad/<slug:slug>/<str:kind>/nuevo/", manage.item_form, name="item_create"),
    path("panel/comunidad/<slug:slug>/<str:kind>/<int:pk>/editar/", manage.item_form, name="item_edit"),
    path("panel/comunidad/<slug:slug>/<str:kind>/<int:pk>/eliminar/", manage.item_delete, name="item_delete"),
]
