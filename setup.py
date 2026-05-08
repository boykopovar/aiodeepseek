from __future__ import annotations

import sys

from setuptools import Extension, setup


def _extra_compile_args() -> list[str]:
    if sys.platform == "win32":
        return ["/std:c++17", "/O2"]

    return ["-std=c++17", "-O3"]


def _extra_link_args() -> list[str]:
    if sys.platform == "win32":
        return []

    return []


def _build_ext() -> Extension:
    import pybind11

    return Extension(
        "aiodeepseek.pow._pow",
        sources=["aiodeepseek/pow/_pow.cpp"],
        include_dirs=[pybind11.get_include()],
        language="c++",
        extra_compile_args=_extra_compile_args(),
        extra_link_args=_extra_link_args(),
    )


setup(
    ext_modules=[_build_ext()],
)