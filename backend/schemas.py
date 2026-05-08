"""
schemas.py — Pydantic request/response models for the Yu-Gi-Oh! Assistant API.
"""
from typing import List, Optional
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class ChatRequest(BaseModel):
    message: str


class DeckSaveRequest(BaseModel):
    name: str
    main: List[dict]
    extra: List[dict]
    side: List[dict]


class StructuredDeckSaveRequest(BaseModel):
    name: str
    main: List[str]
    extra: List[str]
    side: List[str]
    overwrite: Optional[bool] = False
