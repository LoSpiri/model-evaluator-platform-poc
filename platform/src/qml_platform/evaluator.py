"""
Evaluator — loads a model container from a .tar, runs it, asks it to
generate a dataset, calls /evaluate, and collects results.  Uses the Docker
SDK (synchronous calls offloaded via asyncio.to_thread) and httpx for
async HTTP.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import docker
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from qml_platform.models import EvaluationRun, RunStatus
from qml_platform.settings import settings

logger = logging.getLogger(__name__)


def _detect_network(client: docker.DockerClient) -> str | None:
    """Find the Docker network the platform container is connected to."""
    if settings.docker_network:
        return settings.docker_network
    try:
        hostname = os.uname().nodename
        info = client.containers.get(hostname)
        networks = info.attrs["NetworkSettings"]["Networks"]
        for name in networks:
            if "qml" in name:
                return name
        return next(iter(networks), None)
    except Exception:
        return None


def _get_container_ip(container, network_name: str | None) -> str:
    """Get the container's IP on the given network (or its global IP)."""
    container.reload()
    nets = container.attrs["NetworkSettings"]["Networks"]
    if network_name and network_name in nets:
        return nets[network_name]["IPAddress"]
    for net_info in nets.values():
        if net_info.get("IPAddress"):
            return net_info["IPAddress"]
    return container.attrs["NetworkSettings"]["IPAddress"]


def _docker_load_and_run(tar_path: str) -> tuple:
    """Synchronous Docker operations — called via to_thread."""
    client = docker.from_env()

    with open(tar_path, "rb") as f:
        images = client.images.load(f)
    image = images[0]
    image_tag = image.tags[0] if image.tags else image.id

    network_name = _detect_network(client)

    container = client.containers.run(
        image_tag,
        detach=True,
        network=network_name,
        remove=False,
    )

    ip = _get_container_ip(container, network_name)
    return client, container, image_tag, ip


def _docker_cleanup(container) -> None:
    """Stop and remove the container — called via to_thread."""
    try:
        container.stop(timeout=5)
    except Exception:
        pass
    try:
        container.remove(force=True)
    except Exception:
        pass


async def run_evaluation(
    session: AsyncSession,
    run_id: str,
    tar_path: str,
    n_samples: int,
) -> EvaluationRun:
    run = (await session.execute(
        select(EvaluationRun).where(EvaluationRun.id == run_id)
    )).scalar_one()

    run.status = RunStatus.running.value
    await session.commit()

    container = None

    try:
        _client, container, image_tag, ip = await asyncio.to_thread(
            _docker_load_and_run, tar_path
        )
        logger.info("Container %s started at %s:8000 (image %s)", container.short_id, ip, image_tag)

        base_url = f"http://{ip}:8000"
        async with httpx.AsyncClient(base_url=base_url, timeout=10) as http:
            for attempt in range(settings.health_poll_timeout):
                try:
                    resp = await http.get("/health")
                    if resp.status_code == 200:
                        break
                except (httpx.ConnectError, httpx.ReadError):
                    pass
                await asyncio.sleep(settings.health_poll_interval)
            else:
                raise TimeoutError(
                    f"Model container did not become healthy within {settings.health_poll_timeout}s"
                )

            gen_resp = await http.post(
                "/generate-dataset", json={"n_samples": n_samples}, timeout=120,
            )
            gen_resp.raise_for_status()
            dataset = gen_resp.json()
            logger.info("Generated %d samples for run %s", len(dataset), run_id)

            resp = await http.post("/evaluate", json={"dataset": dataset}, timeout=120)
            resp.raise_for_status()
            result = resp.json()

        run.accuracy = result.get("accuracy")
        run.latency_ms = result.get("latency_ms")
        run.extra_metrics = result.get("extra_metrics")
        run.status = RunStatus.completed.value
        run.completed_at = datetime.now(timezone.utc)

    except Exception as exc:
        logger.exception("Evaluation failed for run %s", run_id)
        run.status = RunStatus.failed.value
        run.error = str(exc)
        run.completed_at = datetime.now(timezone.utc)

    finally:
        if container is not None:
            await asyncio.to_thread(_docker_cleanup, container)
            logger.info("Container cleaned up for run %s", run_id)

    await session.commit()
    await session.refresh(run)
    return run
