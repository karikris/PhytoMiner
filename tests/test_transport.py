from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread, Lock
from contextlib import contextmanager
import time
import pytest
from phytominer.biomart import BioMartClient
from phytominer.models import ClientConfig, BatchSizeError, ServiceError

@contextmanager
def server(statuses):
    state = {'calls': 0, 'active': 0, 'peak': 0, 'starts': []}
    lock = Lock()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            with lock:
                idx = state['calls']; state['calls'] += 1
                state['active'] += 1; state['peak'] = max(state['peak'], state['active'])
                state['starts'].append(time.monotonic())
            time.sleep(0.015)
            self.send_response(statuses[min(idx,len(statuses)-1)])
            self.send_header('Retry-After', '0.02')
            self.end_headers()
            self.wfile.write(b'ok')
            with lock:
                state['active'] -= 1
        def log_message(self, *args): pass
    http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=http.serve_forever, daemon=True); thread.start()
    try: yield f'http://127.0.0.1:{http.server_port}', state
    finally: http.shutdown(); http.server_close(); thread.join()

def test_throttle_retry_and_reuse():
    with server([429,200]) as (url,state), BioMartClient(ClientConfig(endpoint=url, requests_per_second=100)) as client:
        with client._request('GET') as response: assert response.text == 'ok'
        assert client.effective_workers == 1
        assert state['calls'] == 2
        assert len(client._sessions) == 1

def test_concurrency_and_rate():
    with server([200]) as (url,state), BioMartClient(ClientConfig(endpoint=url, max_workers=2, requests_per_second=50)) as client:
        def fetch(i):
            with client._request('GET') as response: return response.text
        assert list(client.map(fetch, range(8))) == ['ok'] * 8
        assert state['peak'] <= 2
        starts=sorted(m['scheduled_at'] for m in client.metrics if 'scheduled_at' in m)
        assert len(starts)==8
        assert all(b-a >= .019 for a,b in zip(starts,starts[1:]))

@pytest.mark.parametrize('status,error', [(413,BatchSizeError),(400,ServiceError),(503,ServiceError)])
def test_terminal_failures(status,error):
    with server([status]) as (url,state), BioMartClient(ClientConfig(endpoint=url,attempts=1,requests_per_second=100)) as client:
        with pytest.raises(error):
            with client._request('GET'): pass
        assert client._active == 0

def test_multiple_clients_share_limits_and_cooldown():
    from concurrent.futures import ThreadPoolExecutor
    with server([200]) as (url,state), BioMartClient(ClientConfig(endpoint=url,max_workers=2,requests_per_second=50)) as a, BioMartClient(ClientConfig(endpoint=url,max_workers=4,requests_per_second=100)) as b:
        def fetch(client):
            with client._request('GET') as response:return response.text
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert list(pool.map(fetch,[a,b,a,b,a,b]))==['ok']*6
        assert state['peak']<=2
        starts=sorted(m['scheduled_at'] for c in (a,b) for m in c.metrics if 'scheduled_at' in m)
        assert len(starts)==6
        assert all(y-x>=.019 for x,y in zip(starts,starts[1:]))
        a.effective_workers=1
        assert b.effective_workers==1
        assert a._sessions[0] is not b._sessions[0]
