from typing import Annotated

from fastapi import Depends, Request

from app.composition.container import ApplicationContainer
from app.core.config import Settings
from app.ports.documents import DocumentIngestionPort, DocumentManagementPort


def get_application_container(request: Request) -> ApplicationContainer:
    return request.app.state.container


def get_application_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_document_ingestion(request: Request) -> DocumentIngestionPort | None:
    return get_application_container(request).document_ingestion


def get_document_management(request: Request) -> DocumentManagementPort | None:
    return get_application_container(request).document_management


ApplicationContainerDependency = Annotated[
    ApplicationContainer,
    Depends(get_application_container),
]
SettingsDependency = Annotated[Settings, Depends(get_application_settings)]
DocumentIngestionDependency = Annotated[
    DocumentIngestionPort | None,
    Depends(get_document_ingestion),
]
DocumentManagementDependency = Annotated[
    DocumentManagementPort | None,
    Depends(get_document_management),
]
