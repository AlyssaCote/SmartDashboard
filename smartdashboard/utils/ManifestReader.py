# BSD 2-Clause License
#
# Copyright (c) 2021-2024, Hewlett Packard Enterprise
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import io
import itertools
import json
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List

from pydantic import ValidationError

from smartdashboard.schemas.application import Application
from smartdashboard.schemas.ensemble import Ensemble
from smartdashboard.schemas.experiment import Experiment
from smartdashboard.schemas.orchestrator import Orchestrator
from smartdashboard.schemas.run import Run
from smartdashboard.utils.errors import (
    MalformedManifestError,
    ManifestError,
    VersionIncompatibilityError,
)


@dataclass
class Manifest:
    """Data class representing a manifest

    :param experiment: Experiment
    :type experiment: Experiment
    :param runs: Runs of an experiment
    :type runs: List[Run]
    """

    experiment: Experiment
    runs: List[Run]

    @property
    def apps_with_run_ctx(self) -> t.Iterable[t.Tuple[str, Application]]:
        return itertools.chain.from_iterable(run.apps_with_ctx for run in self.runs)

    @property
    def orcs_with_run_ctx(self) -> t.Iterable[t.Tuple[str, Orchestrator]]:
        return itertools.chain.from_iterable(run.orcs_with_ctx for run in self.runs)

    @property
    def ensemble_with_run_ctx(self) -> t.Iterable[t.Tuple[str, Ensemble]]:
        return itertools.chain.from_iterable(run.ensemble_with_ctx for run in self.runs)


class ManifestReader(ABC):
    """Base class for a ManifestReader"""

    @abstractmethod
    def get_manifest(self) -> Manifest:
        """Abstract method to get the manifest from a ManifestReader subclass"""


class ManifestFileReader(ManifestReader):
    """ManifestReader class for file-based manifests"""

    def __init__(self, file_path: str) -> None:
        """Initialize a ManifestFileReader

        :param file_path: Path to the manifest file
        :type file_path: str
        """
        self._file_path = file_path
        self._data = self.from_file(self._file_path)

        try:
            version = self._data["schema info"]["version"]
        except KeyError as key:
            raise MalformedManifestError(
                "Version data is malformed.", file=self._file_path, exception=key
            ) from key

        if version != "0.0.2":
            version_exception = Exception(
                "SmartDashboard version 0.0.2 is unable to parse manifest "
                f"file at version {version}."
            )
            raise VersionIncompatibilityError(
                title="Invalid Version Number",
                file=file_path,
                exception=version_exception,
            )

    def get_manifest(self) -> Manifest:
        """Get the Manifest from self._data

        :return: Manifest
        :rtype: Manifest
        """
        experiment = Experiment(**self._data.get("experiment", {}))
        runs_data = self._data.get("runs", [])

        runs = [Run(**run_data) for run_data in runs_data]

        return Manifest(
            experiment=experiment,
            runs=runs,
        )

    @classmethod
    def from_file(cls, file_path: str) -> Dict[str, Any]:
        """Initialize self._data

        :param file_path: File path of the manifest
        :type file_path: str
        :return: self._data
        :rtype: Dict[str, Any]
        """
        with open(file_path, encoding="utf-8") as file:
            return cls.from_io_stream(file)

    @classmethod
    def from_io_stream(cls, stream: io.TextIOBase) -> Dict[str, Any]:
        """Continue initializing self._data

        :param stream: io.TextIOBase to be decoded
        :type stream: io.TextIOBase
        :return: self._data
        :rtype: Dict[str, Any]
        """
        data: Dict[str, Any] = json.loads(stream.read())
        return data


def load_manifest(path: str) -> Manifest:
    """Instantiate and call get_manifest

    This is where we're checking for any errors
    that could occur when creating a manifest
    from file.

    :param path: Path to the manifest file
    :type path: str
    :return: Manifest
    :rtype: Optional[Manifest]
    """
    try:
        manifest_file_reader = ManifestFileReader(path)
        manifest = manifest_file_reader.get_manifest()
    except FileNotFoundError as fnf:
        raise ManifestError(
            title="Manifest file does not exist.", file=path, exception=fnf
        ) from fnf
    except json.decoder.JSONDecodeError as jde:
        raise ManifestError(
            title="Manifest file could not be decoded.", file=path, exception=jde
        ) from jde
    except ValidationError as val:
        raise MalformedManifestError(
            title="Manifest file is malformed.", file=path, exception=val
        ) from val
    return manifest
