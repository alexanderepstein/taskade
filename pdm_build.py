import os

from setuptools import Extension

if os.environ.get("C_GRAPHLIB_EXT", "").lower() == "true":
    ext_modules = [Extension("syncra.cgraphlib", ["src/cgraphlib/cgraphlib.c"])]

    def pdm_build_update_setup_kwargs(context, setup_kwargs):
        setup_kwargs.update(ext_modules=ext_modules)
