import contextlib

try:
    import importlib.resources as resources
except ImportError:  # for Python<3.7
    import importlib_resources as resources


class IconDist:

    def __init__(self):
        self._context = contextlib.ExitStack()
        self._paths = {}

    def patch_list(self, icons):
        return [
            path
            for icon in icons
            for path in [icon, self.lookup(icon)]
            if path
        ]

    def lookup(self, name):
        if name in self._paths:
            return self._paths[name]
        try:
            path = self._context.enter_context(
                resources.path('udiskie.icons', name + '.svg'))
            path = str(path.absolute())
        except FileNotFoundError:
            path = None
        self._paths[name] = path
        return path
