from setuptools import Extension

ext_modules = [Extension("syncra.cgraphlib", ["src/cgraphlib/cgraphlib.c"])]


def pdm_build_update_setup_kwargs(context, setup_kwargs):
    setup_kwargs.update(ext_modules=ext_modules)
