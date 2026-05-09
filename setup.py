from __future__ import annotations

import sys
from typing import List

from setuptools import Extension, setup


def _extra_compile_args() -> List[str]:
    if sys.platform == "win32":
        return [
            "/std:c++17",
            "/O2",
            "/GL",
            "/arch:AVX2",
        ]

    return [
        "-std=c++17",
        "-O3",
        "-mavx2",
        "-march=native",
        "-flto",
    ]


def _extra_link_args() -> List[str]:
    if sys.platform == "win32":
        return [
            "/LTCG",
        ]

    return [
        "-flto",
    ]


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
    package_data={
        "aiodeepseek.pow": ["*.pyi"],
    },
    include_package_data=True,
)