"""The fast_protobuf integration."""
from __future__ import annotations

import asyncio
import contextlib
import glob
import logging
import os
import shutil
import subprocess
import sys
import tempfile

import google.protobuf
from google.protobuf.internal import api_implementation

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.start import async_at_start

PROTOBUF_VERSION = google.protobuf.__version__
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fast protobuf from a config entry."""

    if api_implementation.Type() == "cpp":
        _LOGGER.info(
            "Already using %s C++ implementation of protobuf, enjoy :)",
            PROTOBUF_VERSION,
        )
        return True

    _LOGGER.warning(
        "Building protobuf %s cpp version in the background, this will be cpu intensive",
        PROTOBUF_VERSION,
    )

    @callback
    def _async_build_wheel(_hass: HomeAssistant) -> None:
        # Create an untracked task to build the wheel in the background
        # so we don't block shutdown if its not done by the time we exit
        # since they can just try again next time.
        config_dir = hass.config.config_dir
        future = hass.loop.run_in_executor(
            None, build_wheel, config_dir, PROTOBUF_VERSION
        )
        asyncio.ensure_future(future)

    entry.async_on_unload(async_at_start(hass, _async_build_wheel))
    return True


def build_wheel(target_dir: str, version: str) -> str:
    """Build a wheel for the current platform."""
    python_bin = sys.executable
    cpu_count = (os.cpu_count() or 4) / 2
    _LOGGER.info("Building protobuf wheel for %s", version)
    if version.startswith("4."):
        version = version.lstrip("4.")
    target_dir = os.path.abspath(target_dir)
    with tempfile.TemporaryDirectory(
        dir=os.path.expanduser("~")  # /tmp may be non-executable
    ) as tmp_dist_dir:
        with contextlib.suppress(subprocess.CalledProcessError):
            run_command(
                "apk add "
                "autoconf automake libtool m4 gcc musl-dev "
                "openssl-dev libffi-dev zlib-dev jpeg-dev g++ make git cmake"
            )
        run_command(
            f"git clone --depth 1 --branch v{version}"
            f" https://github.com/protocolbuffers/protobuf {tmp_dist_dir}/protobuf"
        )
        run_command(
            f"cd {tmp_dist_dir}/protobuf && git submodule update --init --recursive --depth 1"
        )
        run_command(
            f"cd {tmp_dist_dir}/protobuf && CFLAGS='-fPIC' CXXFLAGS='-fPIC' cmake -DCMAKE_C_FLAGS=-fPIC -DCMAKE_CXX_FLAGS=-fPIC -Dprotobuf_BUILD_EXAMPLES=OFF -Dprotobuf_BUILD_TESTS=OFF ."
        )
        run_command(
            f"cd {tmp_dist_dir}/protobuf && CFLAGS='-fPIC' CXXFLAGS='-fPIC' cmake --build . --parallel 10"
        )
        run_command(f"cd {tmp_dist_dir}/protobuf/src && ln -s ../ .libs")
        run_command(
            f"cd {tmp_dist_dir}/protobuf/python && "
            f"MAKEFLAGS=-j{cpu_count} LD_LIBRARY_PATH=../ PROTOC=../protoc "
            f"{python_bin} setup.py build --cpp_implementation --compile_static_extension"
        )
        run_command(
            f"cd {tmp_dist_dir}/protobuf/python && "
            f"MAKEFLAGS=-j{cpu_count} LD_LIBRARY_PATH=../ PROTOC=../protoc "
            f"{python_bin} setup.py bdist_wheel --cpp_implementation --compile_static_extension"
        )
        wheel_file = glob.glob(f"{tmp_dist_dir}/protobuf/python/dist/*.whl")[0]
        _LOGGER.info("Built wheel %s", wheel_file)
        result_basename = os.path.basename(wheel_file)
        result_path = os.path.join(target_dir, result_basename)
        shutil.copy(wheel_file, result_path)
        _LOGGER.info("Moved into file: %s", result_path)
    _LOGGER.info("Finished building wheel: %s", result_path)
    run_command(
        f"{python_bin} -m pip install --upgrade --no-deps "
        f"--force-reinstall protobuf {result_path}"
    )
    _LOGGER.warning("Restart Home Assistant to use the new wheel")
    return result_path


def run_command(
    cmd: str, env: dict[str, str] | None = None, timeout: int | None = None
) -> None:
    """Implement subprocess.run but handle timeout different."""
    try:
        subprocess.run(
            cmd,
            shell=True,  # nosec
            check=True,
            env=env,
            timeout=timeout,
            capture_output=True,
        )
    except subprocess.CalledProcessError as err:
        _LOGGER.error(
            "Error running command: %s: %s - stderr:%s, stdout:%s",
            cmd,
            err,
            err.stderr,
            err.stdout,
        )
        raise
