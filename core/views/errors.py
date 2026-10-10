from django.shortcuts import render


def not_found(request, exception=None):
    return render(request, "errors/error.html", {"code": 404, "title": "Página no encontrada",
                                                 "message": "El contenido que buscas no existe o aún no está publicado."},
                  status=404)


def forbidden(request, exception=None):
    return render(request, "errors/error.html", {"code": 403, "title": "Acceso restringido",
                                                 "message": "No tienes permisos para realizar esta acción."}, status=403)


def server_error(request):
    return render(request, "errors/error.html", {"code": 500, "title": "Ocurrió un problema",
                                                 "message": "Estamos trabajando para resolverlo. Intenta nuevamente."},
                  status=500)
