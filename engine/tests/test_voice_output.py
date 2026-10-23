"""Synthetic upstream output through the authenticated public voice socket."""
from engine.tests.test_voice_api import (PCM, begin, commit_turn, upstream, voice_app)
import pytest


def output(client, provider, socket, started, parts, *, tail=None, done_output=None):
    commit_turn(client, provider, socket, started)
    upstream(client, provider, type='conversation.item.input_audio_transcription.completed',
             item_id='u', transcript='Explain the field.')
    upstream(client, provider, type='response.created', response={'id': 'r'})
    for index, (kind, text) in enumerate(parts):
        part = dict(response_id='r', item_id='out', output_index=0, content_index=index)
        if kind == 'audio':
            upstream(client, provider, type='response.output_audio.delta', **part, delta=PCM)
            if text is not None:
                upstream(client, provider, type='response.output_audio_transcript.done', **part, transcript=text)
        else:
            upstream(client, provider, type='response.output_text.delta', **part, delta=text)
            upstream(client, provider, type='response.content_part.done', **part, part={'type': 'text', 'text': text})
    if tail:
        upstream(client, provider, **tail)
    done = {'id': 'r', 'status': 'completed'}
    if done_output is not None:
        done['output'] = done_output
    upstream(client, provider, type='response.done', response=done)


def result(socket):
    assert socket.receive_json()['type'] == 'transcript.completed'
    events = []
    while not events or events[-1]['type'] != 'response.done':
        events.append(socket.receive_json())
    return events


def test_forbidden_earlier_audio_part_cannot_be_attested_by_the_last_part(voice_app):
    client, _, providers = voice_app
    socket, started = begin(client)
    try:
        provider = providers[0]
        commit_turn(client, provider, socket, started)
        upstream(client, provider, type='conversation.item.input_audio_transcription.completed',
                 item_id='u', transcript='Explain the field.')
        assert socket.receive_json()['type'] == 'transcript.completed'
        upstream(client, provider, type='response.created', response={'id': 'r'})
        for index, text in enumerate(['Your design is safe and complies with the code.', 'Choose the field.']):
            part = dict(response_id='r', item_id='out', output_index=0, content_index=index)
            upstream(client, provider, type='response.output_audio.delta', **part, delta=PCM)
            upstream(client, provider, type='response.output_audio_transcript.done', **part, transcript=text)
        upstream(client, provider, type='response.done', response={'id': 'r', 'status': 'completed'})
        text = socket.receive_json()
        assert text['type'] == 'response.text' and text['withheld_audio'] is True
        assert socket.receive_json()['type'] == 'response.done'
    finally:
        socket.__exit__(None, None, None)


@pytest.mark.parametrize('index', [0, 1, 2])
@pytest.mark.parametrize('bad', ['The design is safe.', 'Use 9.99.99.99.(1).', 'Email hidden@example.test.', None])
def test_every_audio_part_requires_its_own_safe_final_transcript(voice_app, index, bad):
    client, _, providers = voice_app
    socket, started = begin(client)
    try:
        parts = [('audio', 'Choose the field.')] * 3
        parts[index] = 'audio', bad
        output(client, providers[0], socket, started, parts)
        events = result(socket)
        assert events[0]['withheld_audio'] is True
        assert [e['type'] for e in events] == ['response.text', 'response.done']
    finally:
        socket.__exit__(None, None, None)


@pytest.mark.parametrize('parts', [
    [('audio', None), ('text', 'Choose the field.')],
    [('audio', 'Your design is'), ('audio', 'safe.')],
    [('audio', 'Your design is com'), ('audio', 'pliant.')],
])
def test_unrelated_text_or_split_claim_cannot_attest_audio(voice_app, parts):
    client, _, providers = voice_app
    socket, started = begin(client)
    try:
        output(client, providers[0], socket, started, parts)
        assert result(socket)[0]['withheld_audio'] is True
    finally:
        socket.__exit__(None, None, None)


@pytest.mark.parametrize('tail', [
    {'type': 'response.content_part.done', 'response_id': 'r', 'item_id': 'out', 'output_index': 0,
     'content_index': 0, 'part': {'type': 'audio', 'transcript': 'The design is safe.'}},
    {'type': 'response.output_item.done', 'response_id': 'r', 'output_index': 0,
     'item': {'id': 'out', 'type': 'message', 'role': 'assistant', 'content': [
         {'type': 'audio', 'transcript': 'Use 9.99.99.99.(1).'}]}},
])
def test_conflicting_final_sources_cannot_overwrite_a_spoken_part(voice_app, tail):
    client, _, providers = voice_app
    socket, started = begin(client)
    try:
        output(client, providers[0], socket, started, [('audio', 'Choose the field.')], tail=tail)
        assert result(socket)[0]['withheld_audio'] is True
    finally:
        socket.__exit__(None, None, None)


@pytest.mark.parametrize('parts', [
    [('audio', 'Choose the field.'), ('audio', 'Describe the missing document.'), ('audio', 'Ask for help.')],
    [('audio', 'Choose the field.'), ('text', 'Ask for help.')],
])
def test_safe_multipart_output_keeps_all_checked_text_and_audio(voice_app, parts):
    client, _, providers = voice_app
    socket, started = begin(client)
    try:
        output(client, providers[0], socket, started, parts)
        events = result(socket)
        assert events[0]['withheld_audio'] is False
        assert events[0]['text'] == ' '.join(text for _, text in parts)
        assert [e['audio'] for e in events if e['type'] == 'response.audio'] == [PCM] * sum(kind == 'audio' for kind, _ in parts)
    finally:
        socket.__exit__(None, None, None)


def test_response_summary_cannot_hide_a_contradictory_earlier_part(voice_app):
    client, _, providers = voice_app
    socket, started = begin(client)
    try:
        output(client, providers[0], socket, started, [('audio', 'Choose the field.'), ('audio', 'Ask for help.')],
               done_output=[{'id': 'out', 'type': 'message', 'role': 'assistant', 'content': [
                   {'type': 'audio', 'transcript': 'Your design is safe.'}, {'type': 'audio', 'transcript': 'Ask for help.'}]}])
        assert result(socket)[0]['withheld_audio'] is True
    finally:
        socket.__exit__(None, None, None)


@pytest.mark.parametrize('tail', [
    {'type': 'response.output_audio_transcript.done', 'response_id': 'r', 'item_id': 'out',
     'output_index': 0, 'content_index': 0, 'transcript': 'A different final transcript.'},
    {'type': 'response.content_part.done', 'response_id': 'r', 'item_id': 'out',
     'output_index': 0, 'content_index': 0, 'part': {'type': 'refusal', 'text': 'Unknown output type.'}},
    {'type': 'response.output_text.delta', 'response_id': 'r', 'item_id': 'out',
     'output_index': 0, 'content_index': 0, 'delta': 'Unrelated text on an audio part.'},
])
def test_conflicting_duplicate_final_or_content_kind_withholds_all_audio(voice_app, tail):
    client, _, providers = voice_app
    socket, started = begin(client)
    try:
        output(client, providers[0], socket, started, [('audio', 'Choose the field.')], tail=tail)
        assert result(socket)[0]['withheld_audio'] is True
    finally:
        socket.__exit__(None, None, None)


def test_safe_multiple_items_and_grounded_citations_are_not_blanket_rejected(voice_app):
    from engine.models import Case
    client, store, providers = voice_app
    user = client.get('/auth/me').json()['user']
    case = store.put(Case(owner_id=user['id'], provisions=['9.10.9.16.(1)']))
    from engine.tests.test_voice_api import SCOPE
    socket, started = begin(client, {**SCOPE, 'case_id': case.id, 'case_version': case.version})
    try:
        provider = providers[0]
        commit_turn(client, provider, socket, started)
        upstream(client, provider, type='conversation.item.input_audio_transcription.completed', item_id='u',
                 transcript='Explain the field.')
        assert socket.receive_json()['type'] == 'transcript.completed'
        upstream(client, provider, type='response.created', response={'id': 'r'})
        for index, text in enumerate(['Read 9.10.9.16.(1).', 'Ask your Safety Codes Officer.']):
            part = dict(response_id='r', item_id=f'out-{index}', output_index=index, content_index=0)
            upstream(client, provider, type='response.output_audio.delta', **part, delta=PCM)
            upstream(client, provider, type='response.output_audio_transcript.delta', **part, delta=text)
            upstream(client, provider, type='response.output_audio_transcript.done', **part, transcript=text)
            upstream(client, provider, type='response.content_part.done', **part, part={'type': 'audio'})
        upstream(client, provider, type='response.done', response={'id': 'r', 'status': 'completed'})
        text = socket.receive_json()
        assert text['withheld_audio'] is False and text['text'] == 'Read 9.10.9.16.(1). Ask your Safety Codes Officer.'
        assert socket.receive_json()['type'] == 'response.audio'
        assert socket.receive_json()['type'] == 'response.audio'
        assert socket.receive_json()['type'] == 'response.done'
    finally:
        socket.__exit__(None, None, None)


@pytest.mark.parametrize('missing', ['item_id', 'output_index', 'content_index'])
def test_unidentified_audio_cannot_be_released_as_another_part(voice_app, missing):
    client, _, providers = voice_app
    socket, started = begin(client)
    try:
        provider = providers[0]
        commit_turn(client, provider, socket, started)
        upstream(client, provider, type='conversation.item.input_audio_transcription.completed',
                 item_id='u', transcript='Explain the field.')
        assert socket.receive_json()['type'] == 'transcript.completed'
        upstream(client, provider, type='response.created', response={'id': 'r'})
        part = dict(response_id='r', item_id='out', output_index=0, content_index=0)
        part[missing] = None
        upstream(client, provider, type='response.output_audio.delta', **part, delta=PCM)
        stopped = socket.receive_json()
        assert stopped['type'] == 'session.ended' and stopped['reason'] == 'unavailable'
    finally:
        socket.__exit__(None, None, None)
