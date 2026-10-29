"""Demo Studio rooms on the case store's SQLite/Postgres connection.

A room holds people, who presents each slide group, and one recorded take per group.
Takes arrive in fixed-size chunks so each request stays under the host's 4.5 MB body cap.
Every write locks the room row first and bumps `updated_at`, which clients poll.
"""
from __future__ import annotations

import json
import secrets
import time
import uuid

from fastapi import HTTPException

CHUNK_BYTES = 3 * 1024 * 1024
TAKE_MAX_BYTES = 150 * 1024 * 1024
ROOM_MAX_BYTES = 600 * 1024 * 1024
MAX_PEOPLE = 12
ROOM_SECONDS = 14 * 24 * 60 * 60
CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
CODE_LENGTH = 6

MIGRATIONS = (
    """CREATE TABLE IF NOT EXISTS studio_rooms (
        code TEXT PRIMARY KEY,
        created_at DOUBLE PRECISION NOT NULL,
        updated_at BIGINT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS studio_people (
        id TEXT PRIMARY KEY,
        room_code TEXT NOT NULL REFERENCES studio_rooms(code) ON DELETE CASCADE,
        name TEXT NOT NULL,
        name_key TEXT NOT NULL,
        joined_at DOUBLE PRECISION NOT NULL,
        UNIQUE(room_code, name_key))""",
    """CREATE TABLE IF NOT EXISTS studio_assignments (
        room_code TEXT NOT NULL REFERENCES studio_rooms(code) ON DELETE CASCADE,
        group_id TEXT NOT NULL,
        person_id TEXT NOT NULL REFERENCES studio_people(id) ON DELETE CASCADE,
        PRIMARY KEY(room_code, group_id))""",
    """CREATE TABLE IF NOT EXISTS studio_takes (
        id TEXT PRIMARY KEY,
        room_code TEXT NOT NULL REFERENCES studio_rooms(code) ON DELETE CASCADE,
        group_id TEXT NOT NULL,
        person_id TEXT NOT NULL,
        duration_ms BIGINT NOT NULL,
        cues_json TEXT NOT NULL,
        mime TEXT NOT NULL,
        size BIGINT NOT NULL,
        chunks INTEGER NOT NULL,
        created_at BIGINT NOT NULL,
        UNIQUE(room_code, group_id))""",
    """CREATE TABLE IF NOT EXISTS studio_chunks (
        take_id TEXT NOT NULL REFERENCES studio_takes(id) ON DELETE CASCADE,
        idx INTEGER NOT NULL,
        data BYTEA NOT NULL,
        PRIMARY KEY(take_id, idx))""",
)


def normal_code(code: str) -> str:
    return code.strip().upper()


def expected_chunks(size: int) -> int:
    return -(-size // CHUNK_BYTES)


def chunk_length(size: int, chunks: int, index: int) -> int:
    return size - CHUNK_BYTES * (chunks - 1) if index == chunks - 1 else CHUNK_BYTES


class StudioStore:
    def __init__(self, store):
        self.store = store
        with store.account_db() as db:
            if db.postgres:
                db.execute('SELECT pg_advisory_xact_lock(727276)')
            for statement in MIGRATIONS:
                db.execute(statement)

    def _stamp(self, db, code: str) -> None:
        now = int(time.time() * 1000)
        db.execute('UPDATE studio_rooms SET updated_at=CASE WHEN updated_at>=? THEN updated_at+1 ELSE ? END '
                   'WHERE code=?', (now, now, code))

    def _room(self, db, code: str, *, lock=True) -> str:
        """Return the live room's code (locked for writes), or 404. An expired room is deleted on sight."""
        code = normal_code(code)
        row = db.execute('SELECT created_at FROM studio_rooms WHERE code=?' + (' FOR UPDATE' if lock and db.postgres else ''),
                         (code,)).fetchone()
        if row is not None and row[0] < time.time() - ROOM_SECONDS:
            db.execute('DELETE FROM studio_rooms WHERE code=?', (code,))
            row = None
        if row is None:
            raise HTTPException(404, 'Room not found')
        return code

    def _state(self, db, code: str) -> dict:
        updated = db.execute('SELECT updated_at FROM studio_rooms WHERE code=?', (code,)).fetchone()[0]
        people = [{'id': row[0], 'name': row[1]} for row in
                  db.execute('SELECT id,name FROM studio_people WHERE room_code=? ORDER BY joined_at,id', (code,))]
        assignments = {row[0]: row[1] for row in
                       db.execute('SELECT group_id,person_id FROM studio_assignments WHERE room_code=?', (code,))}
        received = dict(db.execute('SELECT c.take_id,COUNT(*) FROM studio_chunks c JOIN studio_takes t ON t.id=c.take_id '
                                   'WHERE t.room_code=? GROUP BY c.take_id', (code,)).fetchall())
        takes = {row[1]: self._take(row, received.get(row[0], 0)) for row in
                 db.execute('SELECT id,group_id,person_id,duration_ms,cues_json,mime,size,chunks,created_at '
                            'FROM studio_takes WHERE room_code=?', (code,))}
        return {'code': code, 'people': people, 'assignments': assignments, 'takes': takes, 'updated_at': int(updated)}

    @staticmethod
    def _take(row, received: int) -> dict:
        return {'id': row[0], 'group_id': row[1], 'person_id': row[2], 'duration_ms': int(row[3]),
                'cues': json.loads(row[4]), 'mime': row[5], 'size': int(row[6]), 'chunks': int(row[7]),
                'received': int(received), 'created_at': int(row[8])}

    def create_room(self) -> dict:
        with self.store.account_db() as db:
            now = time.time()
            db.execute('DELETE FROM studio_rooms WHERE created_at<?', (now - ROOM_SECONDS,))
            while True:
                code = ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
                if db.execute('SELECT 1 FROM studio_rooms WHERE code=?', (code,)).fetchone() is None:
                    break
            db.execute('INSERT INTO studio_rooms(code,created_at,updated_at) VALUES (?,?,?)',
                       (code, now, int(now * 1000)))
            return self._state(db, code)

    def room(self, code: str) -> dict:
        with self.store.account_db() as db:
            return self._state(db, self._room(db, code, lock=False))

    def join(self, code: str, name: str) -> dict:
        key = name.casefold()
        with self.store.account_db() as db:
            code = self._room(db, code)
            row = db.execute('SELECT id,name FROM studio_people WHERE room_code=? AND name_key=?', (code, key)).fetchone()
            if row is not None:
                return {'id': row[0], 'name': row[1]}
            if db.execute('SELECT COUNT(*) FROM studio_people WHERE room_code=?', (code,)).fetchone()[0] >= MAX_PEOPLE:
                raise HTTPException(409, 'Room is full')
            person = {'id': uuid.uuid4().hex[:12], 'name': name}
            db.execute('INSERT INTO studio_people(id,room_code,name,name_key,joined_at) VALUES (?,?,?,?,?)',
                       (person['id'], code, name, key, time.time()))
            self._stamp(db, code)
            return person

    def leave(self, code: str, person_id: str) -> dict:
        with self.store.account_db() as db:
            code = self._room(db, code)
            db.execute('DELETE FROM studio_assignments WHERE room_code=? AND person_id=?', (code, person_id))
            if db.execute('DELETE FROM studio_people WHERE room_code=? AND id=?', (code, person_id)).rowcount == 0:
                raise HTTPException(404, 'Person not found')
            self._stamp(db, code)
            return self._state(db, code)

    def _person(self, db, code: str, person_id: str) -> None:
        if db.execute('SELECT 1 FROM studio_people WHERE room_code=? AND id=?', (code, person_id)).fetchone() is None:
            raise HTTPException(404, 'Person not found')

    def assign(self, code: str, group_id: str, person_id: str | None) -> dict:
        with self.store.account_db() as db:
            code = self._room(db, code)
            db.execute('DELETE FROM studio_assignments WHERE room_code=? AND group_id=?', (code, group_id))
            if person_id is not None:
                self._person(db, code, person_id)
                db.execute('INSERT INTO studio_assignments(room_code,group_id,person_id) VALUES (?,?,?)',
                           (code, group_id, person_id))
            self._stamp(db, code)
            return self._state(db, code)

    def start_take(self, code: str, *, group_id: str, person_id: str, duration_ms: int, cues: list[dict],
                   mime: str, size: int, chunks: int) -> dict:
        if chunks != expected_chunks(size):
            raise HTTPException(422, f'A take of {size} bytes has {expected_chunks(size)} chunks')
        with self.store.account_db() as db:
            code = self._room(db, code)
            self._person(db, code, person_id)
            others = db.execute('SELECT COALESCE(SUM(size),0) FROM studio_takes WHERE room_code=? AND group_id<>?',
                                (code, group_id)).fetchone()[0]
            if int(others) + size > ROOM_MAX_BYTES:
                raise HTTPException(413, 'This room is out of space')
            # Chunks cascade with the take they belong to.
            db.execute('DELETE FROM studio_takes WHERE room_code=? AND group_id=?', (code, group_id))
            row = (uuid.uuid4().hex, group_id, person_id, duration_ms, json.dumps(cues), mime, size, chunks,
                   int(time.time() * 1000))
            db.execute('INSERT INTO studio_takes(id,group_id,person_id,duration_ms,cues_json,mime,size,chunks,'
                       'created_at,room_code) VALUES (?,?,?,?,?,?,?,?,?,?)', (*row, code))
            self._stamp(db, code)
            return self._take(row, 0)

    def _take_shape(self, db, code: str, take_id: str) -> tuple[int, int]:
        row = db.execute('SELECT size,chunks FROM studio_takes WHERE room_code=? AND id=?', (code, take_id)).fetchone()
        if row is None:
            raise HTTPException(404, 'Take not found')
        return int(row[0]), int(row[1])

    def put_chunk(self, code: str, take_id: str, index: int, data: bytes) -> int:
        with self.store.account_db() as db:
            code = self._room(db, code)
            size, chunks = self._take_shape(db, code, take_id)
            if not 0 <= index < chunks:
                raise HTTPException(404, 'Chunk not found')
            if len(data) != chunk_length(size, chunks, index):
                raise HTTPException(422, f'Chunk {index} must be {chunk_length(size, chunks, index)} bytes')
            db.execute('INSERT INTO studio_chunks(take_id,idx,data) VALUES (?,?,?) '
                       'ON CONFLICT(take_id,idx) DO UPDATE SET data=excluded.data', (take_id, index, data))
            self._stamp(db, code)
            return int(db.execute('SELECT COUNT(*) FROM studio_chunks WHERE take_id=?', (take_id,)).fetchone()[0])

    def get_chunk(self, code: str, take_id: str, index: int) -> bytes:
        with self.store.account_db() as db:
            code = self._room(db, code, lock=False)
            self._take_shape(db, code, take_id)
            row = db.execute('SELECT data FROM studio_chunks WHERE take_id=? AND idx=?', (take_id, index)).fetchone()
            if row is None:
                raise HTTPException(404, 'Chunk not found')
            return bytes(row[0])
