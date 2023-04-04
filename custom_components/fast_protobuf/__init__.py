"""The fast_protobuf integration."""
from __future__ import annotations

import asyncio
import contextlib
import awesomeversion
import logging
import subprocess
import sys

import google.protobuf
from google.protobuf.internal import api_implementation

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.start import async_at_start

PROTOBUF_VERSION = google.protobuf.__version__
PROTOBUF_MIN_VERSION = "4.22.1"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fast protobuf from a config entry."""

    current_type = api_implementation.Type()

    if current_type not in ("upb", "cpp"):
        _LOGGER.info(
            "Already using %s %s implementation of protobuf, enjoy :)",
            PROTOBUF_VERSION,
            current_type,
        )
        return True

    version_to_build = PROTOBUF_VERSION

    if awesomeversion.AwesomeVersion(PROTOBUF_VERSION) < awesomeversion.AwesomeVersion(
        PROTOBUF_MIN_VERSION
    ):
        version_to_build = PROTOBUF_MIN_VERSION

    _LOGGER.warning(
        "Building protobuf upb %s in the background to replace %s, this will be cpu intensive",
        version_to_build,
        current_type,
    )

    @callback
    def _async_reinstall_protobuf(_hass: HomeAssistant) -> None:
        # Create an untracked task to build the wheel in the background
        # so we don't block shutdown if its not done by the time we exit
        # since they can just try again next time.
        future = hass.loop.run_in_executor(None, reinstall_protobuf, version_to_build)
        asyncio.ensure_future(future)

    entry.async_on_unload(async_at_start(hass, _async_reinstall_protobuf))
    return True


def reinstall_protobuf(version: str) -> str:
    """Build a wheel for the current platform."""
    python_bin = sys.executable
    _LOGGER.info("Building protobuf wheel for %s", version)
    with contextlib.suppress(subprocess.CalledProcessError):
        run_command(
            "apk add "
            "autoconf automake libtool m4 gcc musl-dev "
            "openssl-dev libffi-dev zlib-dev jpeg-dev make git cmake"
        )
    run_command(
        f"{python_bin} -m pip install 'protobuf=={version}' --no-binary 'protobuf'"
    )
    _LOGGER.warning("Restart Home Assistant to use the new wheel")


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
            close_fds=False,
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
