from django.conf import settings


def assets(request):
    return {"ASSET_VERSION": settings.ASSET_VERSION}
