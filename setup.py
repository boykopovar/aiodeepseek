from __future__ import annotations

import sys
from setuptools import setup, Extension


def _extra_compile_args() -> list:
    """Return platform-appropriate C++ compiler flags."""
    if sys.platform == "win32":
        return ["/std:c++17", "/O2", "/GL"]
    return ["-std=c++17", "-O3", "-fvisibility=hidden"]


def _extra_link_args() -> list:
    """Return platform-appropriate linker flags."""
    if sys.platform == "win32":
        return ["/LTCG"]
    return []


def _build_ext() -> Extension:
    """Construct the pybind11 Extension for the _pow module."""
    import pybind11

    return Extension(
        "aiodeepseek._pow",
        sources=["aiodeepseek/_pow.cpp"],
        include_dirs=[pybind11.get_include()],
        language="c++",
        extra_compile_args=_extra_compile_args(),
        extra_link_args=_extra_link_args(),
    )


setup(ext_modules=[_build_ext()])
