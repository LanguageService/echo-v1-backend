from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.exceptions import APIException


def error_400(message):
    return Response(
        {
            "code": status.HTTP_400_BAD_REQUEST,
            "status": "error",
            "message": message,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def error_404(message):
    return Response(
        {
            "code": status.HTTP_404_NOT_FOUND,
            "status": "error",
            "message": message,
        },
        status=status.HTTP_404_NOT_FOUND,
    )


def error_401(message):
    return Response(
        {
            "code": status.HTTP_401_UNAUTHORIZED,
            "status": "error",
            "message": message,
        },
        status=status.HTTP_401_UNAUTHORIZED,
    )


class CustomValidationError(APIException):
    default_detail = "A validation error occurred."
    default_code = "validation_error"

    def __init__(self, message, status_code):
        self.detail = {
            "code": status_code,
            "status": False,
            "message": "Validation error",
            "data": {},
            "error": message,
        }

        self.status_code = status_code


def serializer_error_400(
    message=None, error_key=None, status_code=status.HTTP_400_BAD_REQUEST
):
    if message is None:
        message = "Validation error"
    if error_key is None:
        error_key = "error"
    raise CustomValidationError(message, status_code)
    # raise serializers.ValidationError({error_key: message})


# def serializer_error_400(message):
#     return serializers.ValidationError(
#         {"code": 400, "status": "error", "message": message}
#     )


def serializer_errors(default_errors):
    error_messages = ""
    for field_name, field_errors in default_errors.items():
        if field_errors[0].code == "unique":
            error_messages += f"{field_name} already exists, "
        else:
            error_messages += f"{field_name} is {field_errors[0].code}, "
    return error_messages


# def serializer_errors(default_errors):
#     print("errors:",default_errors)
#     error_messages = ""
#     for field_name, field_errors in default_errors.items():
#         if isinstance(field_errors, (list, tuple)) and field_errors:
#             first_error = field_errors[0]

#             if hasattr(first_error, "code"):
#                 if first_error.code == "unique":
#                     error_messages += f"{field_name} already exists, "
#                 else:
#                     error_messages += f"{field_name} is {first_error.code}, "
#             else:
#                 # Fallback if it's just a string
#                 error_messages += f"{field_name} error: {str(first_error)}, "
#         else:
#             error_messages += f"{field_name} has an error, "
#     return error_messages.strip(", ")
