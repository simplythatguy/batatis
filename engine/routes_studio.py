"""Demo Studio rooms: the team joins by code, assigns slide groups, and shares recorded takes in chunks."""
from __future__ import annotations

import json
from typing import Annotated, Any, Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

from .accounts import require_user
from .studio_store import CHUNK_BYTES, SIGNAL_DATA_BYTES, StudioStore, TAKE_MAX_BYTES

GroupId = Annotated[str, StringConstraints(pattern=r'^[a-z0-9-]{1,40}$')]
Code = Annotated[str, Path(pattern=r'^[A-Za-z0-9]{6}$')]
Index = Annotated[int, Path(ge=0, le=1000)]


class Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra='forbid')


class Cue(Camel):
    slide: int = Field(ge=0, le=1000)
    at_ms: int = Field(ge=0)


class Person(Camel):
    id: str
    name: str


class TakeInfo(Camel):
    id: str
    group_id: str
    person_id: str
    duration_ms: int
    cues: list[Cue]
    mime: str
    size: int
    chunks: int
    received: int
    created_at: int


class RoomState(Camel):
    code: str
    people: list[Person]
    assignments: dict[str, str]
    takes: dict[str, TakeInfo]
    updated_at: int


class Join(Camel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class Assign(Camel):
    person_id: str | None


class NewTake(Camel):
    group_id: GroupId
    person_id: str
    duration_ms: int = Field(ge=0, le=60 * 60 * 1000)
    cues: list[Cue] = Field(max_length=100)
    mime: Annotated[str, StringConstraints(pattern=r'^video/[\w.+-]+(;[\w=.,\s"+-]*)?$', max_length=120)]
    size: int = Field(gt=0, le=TAKE_MAX_BYTES)
    chunks: int = Field(gt=0)


class Received(Camel):
    received: int


PersonId = Annotated[str, StringConstraints(min_length=1, max_length=40)]
SignalKind = Literal['offer', 'answer', 'candidate', 'bye']


class NewSignal(Camel):
    from_: PersonId = Field(alias='from')
    to: PersonId
    kind: SignalKind
    data: Any = None


class Sent(Camel):
    seq: int


class Signal(Camel):
    seq: int
    from_: str = Field(alias='from')
    kind: SignalKind
    data: Any
    at: int


class Signals(Camel):
    signals: list[Signal]
    last: int


def create_router(cases: Callable) -> APIRouter:
    router = APIRouter(tags=['demo studio'], dependencies=[Depends(require_user)])
    state: dict = {}

    def studio() -> StudioStore:
        if 'store' not in state:
            state['store'] = StudioStore(cases())
        return state['store']

    @router.post('/studio/rooms', response_model=RoomState, status_code=201)
    def create_room():
        return studio().create_room()

    @router.get('/studio/rooms/{code}', response_model=RoomState)
    def room(code: Code):
        return studio().room(code)

    @router.post('/studio/rooms/{code}/people', response_model=Person)
    def join(code: Code, body: Join):
        return studio().join(code, body.name)

    @router.delete('/studio/rooms/{code}/people/{person_id}', response_model=RoomState)
    def leave(code: Code, person_id: str):
        return studio().leave(code, person_id)

    @router.put('/studio/rooms/{code}/assignments/{group_id}', response_model=RoomState)
    def assign(code: Code, group_id: Annotated[str, Path(pattern=r'^[a-z0-9-]{1,40}$')], body: Assign):
        return studio().assign(code, group_id, body.person_id)

    @router.post('/studio/rooms/{code}/takes', response_model=TakeInfo, status_code=201)
    def start_take(code: Code, body: NewTake):
        return studio().start_take(code, group_id=body.group_id, person_id=body.person_id,
                                   duration_ms=body.duration_ms, cues=[cue.model_dump() for cue in body.cues],
                                   mime=body.mime, size=body.size, chunks=body.chunks)

    @router.put('/studio/rooms/{code}/takes/{take_id}/chunks/{index}', response_model=Received)
    async def put_chunk(code: Code, take_id: str, index: Index, request: Request):
        data = bytearray()
        async for part in request.stream():
            data += part
            if len(data) > CHUNK_BYTES:
                raise HTTPException(413, f'A chunk is at most {CHUNK_BYTES} bytes')
        received = await run_in_threadpool(lambda: studio().put_chunk(code, take_id, index, bytes(data)))
        return {'received': received}

    @router.get('/studio/rooms/{code}/takes/{take_id}/chunks/{index}')
    def get_chunk(code: Code, take_id: str, index: Index):
        return Response(studio().get_chunk(code, take_id, index), media_type='application/octet-stream')

    @router.post('/studio/rooms/{code}/signals', response_model=Sent, status_code=201)
    def send_signal(code: Code, body: NewSignal):
        data = json.dumps(body.data, separators=(',', ':'))
        if len(data.encode()) > SIGNAL_DATA_BYTES:
            raise HTTPException(413, f'Signal data is at most {SIGNAL_DATA_BYTES} bytes')
        return {'seq': studio().send_signal(code, from_id=body.from_, to_id=body.to, kind=body.kind, data=data)}

    @router.get('/studio/rooms/{code}/signals', response_model=Signals)
    def signals(code: Code, to: Annotated[str, Query(min_length=1, max_length=40)],
                after: Annotated[int | None, Query(ge=0)] = None):
        return studio().signals(code, to, after)

    return router
