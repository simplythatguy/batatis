"""Bounded, decoded images for intake. Outbound JPEGs carry no original metadata."""
from __future__ import annotations

import base64
import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PIXELS = 25_000_000
MAX_EDGE = 1280
MIMES = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}


class InvalidImage(ValueError):
    pass


def image_format(data: bytes) -> str | None:
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'PNG'
    if data.startswith(b'\xff\xd8\xff'):
        return 'JPEG'
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return 'WEBP'
    return None


def open_image(data: bytes) -> Image.Image:
    expected = image_format(data)
    if expected is None:
        raise InvalidImage('Use a JPG, PNG or WebP picture.')
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format != expected or source.width * source.height > MAX_PIXELS or getattr(source, 'n_frames', 1) != 1:
                raise InvalidImage('Use one still picture, up to 25 million pixels.')
            source.verify()
        with Image.open(io.BytesIO(data)) as source:
            source.load()                       # truncated pixel payloads fail closed too
            with ImageOps.exif_transpose(source) as oriented:
                if 'A' in oriented.getbands() or 'transparency' in oriented.info:
                    with oriented.convert('RGBA') as rgba:
                        rgb = Image.new('RGB', rgba.size, 'white')
                        rgb.paste(rgba, mask=rgba.getchannel('A'))
                        return rgb
                return oriented.convert('RGB')
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise InvalidImage('This picture could not be opened.') from error


def image_type(data: bytes) -> str:
    with open_image(data):
        return MIMES[image_format(data)]


def data_url(image: Image.Image) -> str:
    copy = image.copy()
    try:
        copy.thumbnail((MAX_EDGE, MAX_EDGE))
        copy.info.clear()
        buf = io.BytesIO()
        copy.save(buf, 'JPEG', quality=75, optimize=True)
        return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    finally:
        copy.close()


def picture_url(data: bytes) -> str:
    with open_image(data) as image:
        return data_url(image)
