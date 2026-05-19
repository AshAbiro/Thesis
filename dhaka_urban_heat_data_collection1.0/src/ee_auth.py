"""Earth Engine authentication and initialization helpers."""

from __future__ import annotations

import ee


def initialize_earth_engine(project: str | None = None) -> None:
    """Initialize the Google Earth Engine Python API.

    Parameters
    ----------
    project:
        Optional Google Cloud project ID registered for Earth Engine.

    Raises
    ------
    RuntimeError
        If Earth Engine credentials are missing or initialization fails.
    """
    try:
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
    except Exception as exc:
        project_hint = f" --project {project}" if project else ""
        raise RuntimeError(
            "Google Earth Engine could not be initialized. "
            "Run `earthengine authenticate` in this environment, then retry "
            f"`python main.py{project_hint}`. If your account requires a Cloud "
            "project, pass `--project your-ee-project-id`."
        ) from exc
