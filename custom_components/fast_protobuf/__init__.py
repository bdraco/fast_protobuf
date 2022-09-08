"""The fast_protobuf integration."""

import logging
import asyncio
import google.protobuf
import os
import tempfile
import sys
import shutil
import glob
from typing import Optional, Dict
from homeassistant.config_entries import ConfigEntry
from google.protobuf.internal import api_implementation
import subprocess

PROTOBUF_VERSION = google.protobuf.__version__
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fast protobuf from a config entry."""

    if api_implementation.Type() == "cpp":
        _LOGGER.info("Using %s C++ implementation of protobuf", PROTOBUF_VERSION)
        return True

    _LOGGER.info(
        "Building cpp version in the background, this will be cpu intensive",
        PROTOBUF_VERSION,
    )
    asyncio.create_task(
        hass.async_add_executor_job(build_wheel, "/config", PROTOBUF_VERSION)
    )
    return True


def build_wheel(wheel_directory: str, version: str) -> str:
    """Build a wheel for the current platform."""
    python_bin = sys.executable
    cpu_count = os.cpu_count() or 4
    _LOGGER.info(f"*** Building protobuf wheel for {version}")
    wheel_directory = os.path.abspath(wheel_directory)
    with tempfile.TemporaryDirectory(
        dir=os.path.expanduser("~")  # /tmp may be non-executable
    ) as tmp_dist_dir:
        run_command(
            f"git clone --depth 1 --branch v{version}"
            " https://github.com/protocolbuffers/protobuf {tmp_dist_dir}/protobuf"
        )
        run_command(f"cd {tmp_dist_dir}/protobuf && /bin/sh ./autogen.sh")
        run_command(
            f'cd {tmp_dist_dir}/protobuf && /bin/sh ./configure "CFLAGS=-fPIC" "CXXFLAGS=-fPIC"'
        )
        run_command(f"cd {tmp_dist_dir}/protobuf && make -j{cpu_count}")
        run_command(
            f"cd {tmp_dist_dir}/protobuf/python && "
            "MAKEFLAGS=-j{cpu_count} LD_LIBRARY_PATH=../src/.libs "
            "{python_bin} setup.py build --cpp_implementation --compile_static_extension"
        )
        run_command(
            f"cd {tmp_dist_dir}/protobuf/python && "
            "MAKEFLAGS=-j{cpu_count} LD_LIBRARY_PATH=../src/.libs "
            "{python_bin} setup.py bdist_wheel --cpp_implementation --compile_static_extension"
        )
        wheel_file = glob.glob(f"{tmp_dist_dir}/protobuf/python/dist/*.whl")[0]
        result_basename = os.path.basename(wheel_file)
        target_dir = wheel_directory
        result_path = os.path.join(target_dir, result_basename)
        shutil.copy(wheel_file, result_path)
        _LOGGER.info("Moved into file: %s", result_path)
    _LOGGER.info("Finished building wheel: %s", result_path)
    run_command(
        "{python_bin} -m pip install --upgrade --no-deps --force-reinstall protobuf {result_path}"
    )
    _LOGGER.warning("Restart Home Assistant to use the new wheel")
    return result_path


def run_command(
    cmd: str, env: Optional[Dict[str, str]] = None, timeout: Optional[int] = None
) -> None:
    """Implement subprocess.run but handle timeout different."""
    subprocess.run(
        cmd,
        shell=True,  # nosec
        check=True,
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=env,
        timeout=timeout,
    )
