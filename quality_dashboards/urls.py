from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import station_list_view, yield_view


urlpatterns = [
    path('stations/',station_list_view, name='station-manager'),
    path('yields/', yield_view, name='yields'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
