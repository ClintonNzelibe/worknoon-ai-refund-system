from rest_framework.response import Response
from rest_framework.views import exception_handler


def safe_exception_handler(exc, context):
    """Return controlled API failures without exposing traceback or provider internals."""
    response = exception_handler(exc, context)
    if response is not None:
        return response
    return Response({"detail": "The request could not be completed."}, status=500)
