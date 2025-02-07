"""Photos app API v2 urls."""
from django.urls import path, include

from photos.api.v2.views import AlbumListView, AlbumDetailView

app_name = "photos"

urlpatterns = [
    path(
        "photos/",
        include(
            [
                path("albums/", AlbumListView.as_view(), name="album-list"),
                path(
                    "albums/<slug:slug>/",
                    AlbumDetailView.as_view(),
                    name="album-detail",
                ),
            ]
        ),
    ),
]
