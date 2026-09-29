from enum import StrEnum
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class Environment(StrEnum):
    DEV = "DEV"
    QAS = "QAS"
    PRD = "PRD"


class Risk(StrEnum):
    READ = "READ"
    EXECUTE = "EXECUTE"
    WRITE = "WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"


# Deliberately conservative. Broaden only with a documented tenant use case.
Identifier = Annotated[str, StringConstraints(
    min_length=1, max_length=256, pattern=r"^[A-Za-z_][A-Za-z0-9_.:]*$"
)]
PageSize = Annotated[int, Field(ge=1, le=200, strict=True)]
Offset = Annotated[int, Field(ge=0, le=1000000, strict=True)]


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    environment: Environment


class SpaceRequest(Request):
    space: Identifier


class Page(BaseModel):
    limit: PageSize = 100
    offset: Offset = 0


class SafeError(BaseModel):
    code: str
    message: str


T = TypeVar("T")


class Result(BaseModel, Generic[T]):
    success: bool = True
    environment: Environment | None = None
    space: str | None = None
    data: T | None = None
    error: SafeError | None = None
    warnings: list[str] = Field(default_factory=list)
