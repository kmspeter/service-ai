import asyncio
import os
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.factories.summary import create_document_summary_service
from app.infrastructure import create_infrastructure_resources
from app.models.summary import SummaryRequest, SummaryStrategy
from app.ports.qdrant import VectorPoint

pytestmark = [
    pytest.mark.infrastructure,
    pytest.mark.llm,
    pytest.mark.summary,
    pytest.mark.skipif(
        os.getenv("RUN_SUMMARY_INTEGRATION_TESTS") != "1",
        reason=(
            "Set RUN_SUMMARY_INTEGRATION_TESTS=1 with MinIO, Qdrant, and LLM "
            "credentials configured"
        ),
    ),
]


def test_real_minio_qdrant_and_llm_direct_and_hierarchical_summary() -> None:
    async def scenario() -> None:
        run_id = uuid4().hex
        user_id = f"phase11-user-{run_id}"
        collection_name = f"phase11_summary_{run_id}"
        bucket_name = f"phase11-{run_id}"
        direct_document_id = f"phase11-direct-{run_id}"
        hierarchical_document_id = f"phase11-hierarchical-{run_id}"
        direct_key = f"phase11/{run_id}/direct.txt"
        hierarchical_key = f"phase11/{run_id}/hierarchical.txt"
        direct_content = (
            "This is generated, non-sensitive test data. "
            "The synthetic marker SYNTH-DIRECT-418 is paired with a red circle "
            "and a blue square."
        )
        hierarchical_content = _large_document()

        settings = Settings(
            environment="test",
            qdrant_collection=collection_name,
            minio_bucket=bucket_name,
            minio_auto_create_bucket=False,
            llm_context_window=5_800,
            llm_max_output_tokens=4_096,
            llm_timeout_seconds=120,
            summary_safety_margin_tokens=64,
            tokenizer_encoding="cl100k_base",
            chunk_size=800,
            chunk_overlap=50,
        )
        settings.validate_summary_settings()
        infrastructure = create_infrastructure_resources(settings)
        summary = None
        stored_keys: list[str] = []
        collection_created = False
        bucket_created = False
        try:
            await infrastructure.storage.ensure_bucket()
            bucket_created = True
            await infrastructure.qdrant.create_collection(
                collection_name,
                vector_size=4,
            )
            collection_created = True

            await infrastructure.storage.put_object(
                direct_key,
                direct_content.encode("utf-8"),
                content_type="text/plain; charset=utf-8",
            )
            stored_keys.append(direct_key)
            await infrastructure.storage.put_object(
                hierarchical_key,
                hierarchical_content.encode("utf-8"),
                content_type="text/plain; charset=utf-8",
            )
            stored_keys.append(hierarchical_key)

            await _write_document_metadata(
                infrastructure.qdrant,
                collection_name=collection_name,
                user_id=user_id,
                document_id=direct_document_id,
                storage_key=direct_key,
                filename="direct.txt",
            )
            await _write_document_metadata(
                infrastructure.qdrant,
                collection_name=collection_name,
                user_id=user_id,
                document_id=hierarchical_document_id,
                storage_key=hierarchical_key,
                filename="hierarchical.txt",
            )

            summary = create_document_summary_service(settings, infrastructure)
            direct = await summary.summarize(
                SummaryRequest(
                    request_id="summary-direct-integration",
                    user_id=user_id,
                    document_id=direct_document_id,
                )
            )
            hierarchical = await summary.summarize(
                SummaryRequest(
                    request_id="summary-hierarchical-integration",
                    user_id=user_id,
                    document_id=hierarchical_document_id,
                )
            )

            assert direct.strategy is SummaryStrategy.DIRECT
            assert direct.llm_call_count == 1
            assert "SYNTH-DIRECT-418" in direct.summary.upper()

            assert hierarchical.strategy is SummaryStrategy.HIERARCHICAL
            assert hierarchical.chunk_summary_count > 1
            assert hierarchical.llm_call_count > hierarchical.chunk_summary_count
            normalized_summary = hierarchical.summary.upper()
            assert "SYNTH-MAP-FIRST-902" in normalized_summary
            assert "SYNTH-MAP-LAST-665" in normalized_summary
        finally:
            if summary is not None:
                await summary.close()
            if collection_created and await infrastructure.qdrant.collection_exists(
                collection_name
            ):
                await infrastructure.qdrant.delete_collection(collection_name)
            for object_name in reversed(stored_keys):
                await infrastructure.storage.delete_object(object_name)
            if bucket_created and await infrastructure.storage.bucket_exists():
                await infrastructure.storage.delete_bucket()
            await infrastructure.close()

    asyncio.run(scenario())


async def _write_document_metadata(
    qdrant,
    *,
    collection_name: str,
    user_id: str,
    document_id: str,
    storage_key: str,
    filename: str,
) -> None:
    await qdrant.replace_document_points(
        collection_name,
        user_id=user_id,
        document_id=document_id,
        points=(
            VectorPoint(
                point_id=str(uuid4()),
                vector=(1.0, 0.0, 0.0, 0.0),
                payload={
                    "user_id": user_id,
                    "document_id": document_id,
                    "chunk_id": str(uuid4()),
                    "filename": filename,
                    "source": storage_key,
                    "chunk_text": "Qdrant payload must not be used as summary content.",
                },
            ),
        ),
    )


def _large_document() -> str:
    sections = [
        (
            "This fixture is generated, non-sensitive test data. "
            "The first synthetic marker is SYNTH-MAP-FIRST-902 and it is paired "
            "with an orange triangle."
        )
    ]
    for index in range(1, 31):
        sections.append(
            f"Synthetic section {index} repeats harmless shape observations for "
            "summary chunk testing. The observed sequence is circle, square, "
            "triangle, and hexagon. Each section explicitly contains generated "
            "fixture text and no user, business, credential, or production data."
        )
    sections.append(
        "The last synthetic marker is SYNTH-MAP-LAST-665 and it is paired with "
        "a green hexagon. This concludes the generated non-sensitive fixture."
    )
    return "\n\n".join(sections)
