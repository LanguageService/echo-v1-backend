import os
import json
import django

from django.http import HttpResponse

from loguru import logger

from django.http import HttpResponse


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()


class LogRequest:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code >= 400:
            logger.warning(
                "Bad Request: User: {} ... {} {} with status code {}, {}",
                request.user.id if not request.user.is_anonymous else "Anonymous",
                request.method,
                request.path,
                response.status_code,
                (response.content),
                feature="f-strings",
            )

        return response


class Validation400ErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response: HttpResponse = self.get_response(request)

        content_type = response.headers.get("Content-Type")
        if (
            content_type
            and content_type == "application/json"
            and response.status_code == 400
        ):
            data = json.loads(response.content)
            if (
                isinstance(data, dict)
                and not data.get("detail")
                and not data.get("errors")
            ):
                data = {"success": False, "errors": data}
            response.content = json.dumps(data)

        return response


class UpdateLastLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.contrib.auth.models import update_last_login

        response = self.get_response(request)

        # Check if the user is authenticated and if there has been a successful login
        if request.user.is_authenticated and hasattr(request, "user"):
            update_last_login(None, request.user)

        return response
