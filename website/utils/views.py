import os

from PIL import Image, ImageOps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlunquote
from sendfile import sendfile

from .snippets import sanitize_path


def _private_thumbnails_unauthed(request, size_fit, path):
    """This layer of indirection makes it possible to make exceptions
    to the authentication requirements for thumbnails, e.g. when sharing
    photo albums with external parties using access tokens."""
    path = sanitize_path(path)
    path = os.path.join(settings.MEDIA_ROOT, 'thumbnails', size_fit, path)
    if not os.path.isfile(path):
        raise Http404("Thumbnail not found.")
    return sendfile(request, path)


@login_required
def private_thumbnails(request, size_fit, path):
    return _private_thumbnails_unauthed(request, size_fit, path)


def generate_thumbnail(request, size_fit, path, thumbpath):
    """The thumbnails are generated with this route. Because the
    thumbnails will be generated in parallel, it will not block
    page load when many thumbnails need to be generated.
    After it is done, the user is redirected to the new location
    of the thumbnail."""
    thumbpath = urlunquote(thumbpath)
    path = urlunquote(path)
    full_thumbpath = os.path.join(settings.MEDIA_ROOT, thumbpath)
    full_path = os.path.join(settings.MEDIA_ROOT, path)
    size, fit = size_fit.split('_')

    os.makedirs(os.path.dirname(full_thumbpath), exist_ok=True)
    if (not os.path.isfile(full_thumbpath) or
            os.path.getmtime(full_path) > os.path.getmtime(full_thumbpath)):
        image = Image.open(full_path)
        size = tuple(int(dim) for dim in size.split('x'))
        if not fit:
            ratio = min([a / b for a, b in zip(size, image.size)])
            size = tuple(int(ratio * x) for x in image.size)
        thumb = ImageOps.fit(image, size, Image.ANTIALIAS)
        thumb.save(full_thumbpath)

    # We can instantly redirect to the new correct image url
    if path.split('/')[0] == 'public':
        return redirect(settings.MEDIA_URL + thumbpath, permanent=True)

    # Otherwise redirect to the route with an auth check
    return redirect(
        reverse('private-thumbnails', args=[size_fit, path]),
        permanent=True
    )
