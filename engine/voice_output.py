"""Collect complete, identified output parts before any generated audio is released."""
from dataclasses import dataclass, field

from .voice_grok import VoiceFailure


@dataclass
class _Part:
    kind: str
    delta: str = ''
    final: str | None = None
    audio: list[str] = field(default_factory=list, repr=False)


class ResponseOutput:
    def __init__(self):
        self.parts: dict[tuple[int, int], _Part] = {}
        self.items: dict[int, str] = {}
        self.invalid = False

    def part(self, event, kind):
        item, output, content = (event.get(key) for key in ('item_id', 'output_index', 'content_index'))
        if (not isinstance(item, str) or not 1 <= len(item) <= 100
                or type(output) is not int or not 0 <= output < 32
                or type(content) is not int or not 0 <= content < 32):
            raise VoiceFailure()
        if output in self.items and self.items[output] != item:
            self.invalid = True
        if item in self.items.values() and self.items.get(output) != item:
            self.invalid = True
        self.items[output] = item
        key = output, content
        if key not in self.parts:
            if len(self.parts) >= 32:
                raise VoiceFailure()
            self.parts[key] = _Part(kind)
        part = self.parts[key]
        if part.kind != kind:
            self.invalid = True
        return part

    def finish(self, part, text):
        if not isinstance(text, str):
            self.invalid = True
            return
        # No final source may overwrite a different final transcript, or attest
        # audio whose streamed transcript said something else.
        if (part.final is not None and part.final != text) or (part.delta and part.delta != text):
            self.invalid = True
        part.final = text

    def summary(self, event, content):
        if not isinstance(content, dict) or content.get('type') not in {'audio', 'text', 'output_audio', 'output_text'}:
            self.invalid = True
            return
        kind = 'audio' if content['type'] in {'audio', 'output_audio'} else 'text'
        part = self.part(event, kind)
        text = content.get('transcript' if kind == 'audio' else 'text')
        if text is not None:
            self.finish(part, text)

    def item_summary(self, index, item):
        if (not isinstance(item, dict) or item.get('type') != 'message'
                or item.get('role') != 'assistant' or item.get('status', 'completed') != 'completed'
                or not isinstance(item.get('content'), list) or len(item['content']) > 32):
            self.invalid = True
            return
        for content_index, content in enumerate(item['content']):
            self.summary({'item_id': item.get('id'), 'output_index': index,
                          'content_index': content_index}, content)

    def accept(self, type_, event):
        if type_ == 'response.content_part.done':
            self.summary(event, event.get('part'))
        elif type_ == 'response.output_item.done':
            self.item_summary(event.get('output_index'), event.get('item'))
        elif type_ == 'response.done':
            output = event['response'].get('output')
            if output is not None:
                if not isinstance(output, list) or len(output) > 32:
                    raise VoiceFailure()
                for index, item in enumerate(output):
                    self.item_summary(index, item)
        else:
            kind = 'audio' if 'audio' in type_ else 'text'
            part = self.part(event, kind)
            if type_ in {'response.output_audio.delta', 'response.audio.delta'}:
                part.audio.append(event['delta'])
            elif type_.endswith('.delta'):
                text = event.get('delta')
                if not isinstance(text, str):
                    raise VoiceFailure()
                if part.final is not None:
                    self.invalid = True
                part.delta += text
            else:
                self.finish(part, event.get('transcript' if kind == 'audio' else 'text'))

    @property
    def text_size(self):
        return sum(max(len(part.delta), len(part.final or '')) for part in self.parts.values())

    def checked(self):
        parts = [part for _, part in sorted(self.parts.items())]
        texts = [part.final if part.final is not None else part.delta for part in parts]
        # A text part cannot attest a different audio part. Every spoken part
        # needs its own nonempty final transcript, even if other parts are safe.
        valid = (not self.invalid and bool(parts)
                 and all(part.final is not None and part.final.strip() for part in parts))
        return texts, [chunk for part in parts for chunk in part.audio], valid
