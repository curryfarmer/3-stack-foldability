"""thumbs.py — load an engine PNG into a bounded Tk image for the results preview.

Pillow (present but undeclared in pyproject) gives clean downscaling; the fallback is pure-Tk
PhotoImage.subsample (integer downscale only), which Tk 8.6 supports for PNG. `use_pillow=False`
forces the fallback so both paths are testable even where Pillow is installed. A Tk image needs a
root/master, so `master` is threaded through.
"""


def load(path, master=None, max_px=240, use_pillow=True):
    """A Tk-usable image for `path`, downscaled to fit `max_px`. I/O: (str, tk widget|None, int, bool)
    -> a Tk PhotoImage / ImageTk.PhotoImage."""
    if use_pillow:
        try:
            from PIL import Image, ImageTk
        except ImportError:
            return _tk_load(path, master, max_px)
        img = Image.open(path)
        img.thumbnail((max_px, max_px))
        return ImageTk.PhotoImage(img, master=master)
    return _tk_load(path, master, max_px)


def _tk_load(path, master, max_px):
    import tkinter as tk
    photo = tk.PhotoImage(file=path, master=master)
    w, h = photo.width(), photo.height()
    k = max(1, (max(w, h) + max_px - 1) // max_px)   # smallest integer factor that fits max_px
    return photo.subsample(k, k) if k > 1 else photo
