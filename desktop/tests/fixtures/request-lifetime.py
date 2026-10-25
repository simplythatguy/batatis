"""Synthetic intake over the production private bridge, without a socket or provider."""
import io
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from reportlab.pdfgen import canvas

from engine.desktop import bridge, composition, host_provider
from engine.identify.providers import transports
from engine.identify.screen import Judge
from engine.models import Case
from engine.routes_intake import create_router

document = io.BytesIO()
pdf = canvas.Canvas(document)
pdf.drawString(40, 750, 'Synthetic wall documentation. A novel cladding is proposed.')
pdf.save()


class Store:
    case = Case(id='case_synthetic', title='Synthetic request lifetime test')

    def get(self, case_id):
        return self.case.model_copy(deep=True)

    def get_file(self, case_id, file_id):
        return {'name': 'synthetic.pdf', 'data': document.getvalue()}

    def put(self, case, expected_version):
        self.case = case
        return case


store = Store()
app = FastAPI()
app.include_router(create_router(lambda: store, lambda: None), prefix='/api')
saved_calls = []


def generation_calls():
    selected = transports(scoring={'jev'})
    review, _ = composition.review_transport()
    direct = host_provider.host_transport('intake', model='gpt-6-luna', effort='medium', lease=composition.profile().lease)
    return [lambda: selected.openai('picks', {'type': 'object'}, 'Synthetic system', 'Synthetic user',
                                    model='gpt-6-luna', effort='medium'),
            lambda: review('Synthetic system', 'Synthetic user', {'type': 'object'}, 'gpt-6-luna', 'medium'),
            lambda: direct('Synthetic system', 'Synthetic user', {'type': 'object'}),
            lambda: selected.jev('Synthetic state', {'q': {'type': 'noul', 'instructions': 'Synthetic question.'}}, 5)]


def parallel(calls):
    def invoke(call):
        try:
            call()
            return 'ok'
        except Exception:
            return 'closed'
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(invoke, calls))


@app.post('/api/parallel')
def parallel_generation():
    return {'results': parallel(generation_calls())}


@app.post('/api/capture')
def capture():
    saved_calls[:] = generation_calls()
    return {'captured': len(saved_calls)}


@app.post('/api/reuse')
def reuse():
    return {'results': parallel(saved_calls)}


@app.post('/api/screen')
def screen():
    selected = transports(scoring={'jev'})
    assert selected.jev is not None, 'optional screening must stay enabled'
    threads = set()
    lock = threading.Lock()

    def ask(*args):
        with lock:
            threads.add(threading.current_thread().name)
        return selected.jev(*args)

    judge = Judge(ask, chars=700, max_state=450, workers=2, attempts=1)
    articles = {f'9.1.1.{n}.': {'part': 9, 'section': 'Synthetic', 'subsection': 'Fixture',
                              'title': 'Synthetic wall', 'text': 'Synthetic wall requirement. ' * 30}
                for n in range(1, 5)}
    ids = list(articles)
    assert len(judge.batches('Synthetic wall', articles, ids)) == 4
    return {'scores': judge.judge('Synthetic wall', articles, ids), 'threads': sorted(threads)}


@app.post('/api/large')
def large():
    from engine.desktop.composition import profile
    selected = profile()
    call = host_provider.host_transport('intake', model='gpt-6-luna', effort='medium', lease=selected.lease)
    result, _ = call('Synthetic system', 'éç' * 40_000, {'type': 'object'})
    return result


async def observed_app(scope, receive, send):
    try:
        await app(scope, receive, send)
    finally:
        if scope['type'] == 'http':
            print('request-lifetime: completed ' + scope['query_string'].decode(), file=sys.stderr, flush=True)


bridge.run(observed_app, hello={'workspace': {'kind': 'local', 'id': 'synthetic'},
                               'codedb': {'available': False, 'build': None, 'expectedBuild': 'synthetic'}},
           control=None, body_limit=5_000_000)
