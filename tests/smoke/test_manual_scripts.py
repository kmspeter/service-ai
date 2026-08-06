import json
import subprocess
import sys

from scripts import manual_chunking


def test_manual_chunking_runs_with_editable_module_variables(
    capsys,
) -> None:
    manual_chunking.main()

    output = json.loads(capsys.readouterr().out)
    assert output["document_id"] == manual_chunking.DOCUMENT_ID
    assert output["chunks"]


def test_external_manual_scripts_are_import_safe() -> None:
    from scripts import (
        manual_ingestion,
        manual_llm,
        manual_rag,
        manual_retrieval,
        manual_summary,
    )

    assert manual_ingestion.REQUEST_ID
    assert manual_llm.QUESTION
    assert manual_retrieval.QUERY
    assert manual_rag.QUESTION
    assert manual_summary.DOCUMENT_ID


def test_manual_chunking_is_directly_executable_as_python_file() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/manual_chunking.py"],
        check=True,
        capture_output=True,
        text=True,
    )

    output = json.loads(completed.stdout)
    assert output["document_id"] == manual_chunking.DOCUMENT_ID
