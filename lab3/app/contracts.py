"""Shared, strict structured-output contracts advertised by the MCP SDK."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


Status = Literal["Действует", "Архив", "Черновик"]
Visibility = Literal["cloud_ok", "local_only"]


class Section(Contract):
    anchor: str
    title: str
    body: list[str]


class Document(Contract):
    id: str
    version: str
    title: str
    status: Status
    date: str
    owner: str
    visibility: Visibility
    path: list[str]
    replaces: str | None
    links: list[str]
    sections: list[Section]


class Fragment(Contract):
    anchor: str
    chunk_id: str
    heading: str
    text: str
    rank: float | int


class Card(Contract):
    id: str
    version: str
    title: str
    status: Status
    visibility: Visibility
    path: list[str]
    links: list[str]
    rank: int
    fragments: list[Fragment] = Field(max_length=3)


class SearchSnapshot(Contract):
    generation: str
    cards: list[Card] = Field(max_length=10)


class Leaf(Contract):
    id: str
    version: str
    title: str
    status: Status
    visibility: Visibility


class Subsection(Contract):
    id: str
    title: str
    documents: list[Leaf]


class Branch(Contract):
    id: str
    title: str
    subsections: list[Subsection]


class Tree(Contract):
    generation: str
    sections: list[Branch]


class ModelAnswer(Contract):
    answer: str = Field(min_length=1, max_length=900)
