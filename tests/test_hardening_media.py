# coding=utf-8
"""媒体下载加固:单文件大小/时长上限、拒绝播放列表链接、封面和电台读取有上限。"""
import configparser
import io
import itertools
import os
import struct
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import constants  # noqa: E402
import util  # noqa: E402
import variables as var  # noqa: E402


@pytest.fixture
def config(monkeypatch, tmp_path):
    cfg = configparser.ConfigParser(interpolation=None, allow_no_value=True)
    cfg.read(util.solve_filepath('configuration.default.ini'), encoding='utf-8')
    cfg.set('bot', 'tmp_folder_max_size', '-1')
    cfg.set('bot', 'download_attempts', '3')
    monkeypatch.setattr(var, 'config', cfg)
    monkeypatch.setattr(var, 'tmp_folder', str(tmp_path) + os.sep)
    monkeypatch.setattr(var, 'store', None, raising=False)
    constants.load_lang('en_US')
    return cfg


# ---- media/url.py ---------------------------------------------------------------

class RecordingYDL:
    """记录每次构造的 opts;download 按 behaviour 写文件/调进度钩子。"""
    instances = []
    behaviour = 'ok'
    info = None

    def __init__(self, opts):
        self.opts = opts
        self.cookiejar = mock.MagicMock()
        self.calls = 0
        RecordingYDL.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=True):
        self.calls += 1
        if not download:
            return dict(RecordingYDL.info)
        path = self.opts['outtmpl']
        if RecordingYDL.behaviour == 'ok':
            with open(path, 'wb') as f:
                f.write(b'audio')
        elif RecordingYDL.behaviour == 'huge':
            with open(path, 'wb') as f:
                f.write(b'x' * 10)
            for hook in self.opts['progress_hooks']:
                hook({'status': 'downloading', 'downloaded_bytes': self.opts['max_filesize'] + 1})
        # 'skip': yt-dlp 看到 Content-Length 超过 max_filesize 时什么都不写,也不报错
        return {'id': 'x', 'requested_downloads': [{'filepath': path}]}

    process_ie_result = extract_info


@pytest.fixture
def ydl(monkeypatch):
    import media.url
    RecordingYDL.instances, RecordingYDL.behaviour = [], 'ok'
    RecordingYDL.info = {'_type': 'video', 'title': 't', 'duration': 10}
    monkeypatch.setattr(media.url.youtube_dl, 'YoutubeDL', RecordingYDL)
    monkeypatch.setattr(media.url.time, 'sleep', lambda s: None)
    monkeypatch.setattr(media.url.artwork, 'ensure', lambda *a, **k: None)
    return RecordingYDL


def make_item(url='https://www.bilibili.com/video/av1'):
    from media.url import URLItem
    item = URLItem(url)
    item.title, item.duration, item.ready = 'Song', 200, 'validated'
    return item


def test_download_opts_cap_size_and_single_entry(config, ydl):
    item = make_item()
    assert item._download()
    opts = ydl.instances[0].opts
    assert opts['max_filesize'] == 300 * 1024 * 1024
    assert opts['playlist_items'] == '1'


def test_download_cap_follows_config(config, ydl):
    config.set('bot', 'max_download_mb', '5')
    item = make_item()
    assert item._download()
    assert ydl.instances[0].opts['max_filesize'] == 5 * 1024 * 1024


def test_progress_hook_aborts_when_downloaded_bytes_exceed_cap(config):
    import yt_dlp
    item = make_item()
    item._download_cap = 1000
    item._ydl_progress_hook({'status': 'downloading', 'downloaded_bytes': 500})  # 没有 total 也照常
    with pytest.raises(yt_dlp.utils.DownloadCancelled):
        item._ydl_progress_hook({'status': 'downloading', 'downloaded_bytes': 1001})


def test_progress_hook_aborts_when_total_exceeds_cap(config):
    import yt_dlp
    item = make_item()
    item._download_cap = 1000
    with pytest.raises(yt_dlp.utils.DownloadCancelled):
        item._ydl_progress_hook({'status': 'downloading', 'downloaded_bytes': 10, 'total_bytes': 5000})


def test_progress_hook_aborts_after_wall_clock_limit(config):
    import yt_dlp
    item = make_item()
    item._download_cap = 0
    item._download_deadline = 0  # 早就过了
    with pytest.raises(yt_dlp.utils.DownloadCancelled):
        item._ydl_progress_hook({'status': 'downloading', 'downloaded_bytes': 10})


def test_download_deadline_scales_with_duration(config, ydl, monkeypatch):
    import media.url
    monkeypatch.setattr(media.url.time, 'time', lambda: 1000.0)
    item = make_item()
    item.duration = 60
    item._download()
    assert item._download_deadline == 1000.0 + 3600
    item = make_item('https://www.bilibili.com/video/av2')
    item.duration = 7200
    item._download()
    assert item._download_deadline == 1000.0 + 3 * 7200


def test_oversized_download_fails_once_and_removes_partial_file(config, ydl):
    from media.item import PreparationFailedError
    ydl.behaviour = 'huge'
    item = make_item()
    with pytest.raises(PreparationFailedError):
        item._download()
    assert sum(i.calls for i in ydl.instances) == 1  # 不重试
    assert not os.path.exists(item.path)
    assert item.ready == 'failed' and not item.downloading


def test_silently_skipped_download_is_a_failure(config, ydl):
    from media.item import PreparationFailedError
    ydl.behaviour = 'skip'
    item = make_item()
    with pytest.raises(PreparationFailedError):
        item._download()
    assert sum(i.calls for i in ydl.instances) == 1
    assert item.ready == 'failed'


def test_info_fetch_does_not_expand_playlists(config, ydl):
    item = make_item()
    assert item._get_info_from_url()
    opts = ydl.instances[0].opts
    assert opts['extract_flat'] == 'in_playlist'
    assert opts['playlist_items'] == '1'


@pytest.mark.parametrize('kind', ['playlist', 'multi_video'])
def test_playlist_url_is_rejected(config, ydl, kind):
    from media.item import ValidationFailedError
    ydl.info = {'_type': kind, 'title': 'feed', 'entries': [{'url': 'https://example.com/1'}]}
    item = make_item()
    with pytest.raises(ValidationFailedError):
        item._get_info_from_url()
    assert ydl.instances[0].calls == 1  # 不按重试次数再读
    assert item._info is None


# ---- media/artwork.py -----------------------------------------------------------

class FakeResponse:
    def __init__(self, chunks, headers=None, raw=None):
        self._chunks = chunks
        self.headers = headers or {}
        self.raw = raw
        self.read = 0
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.closed = True
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        for chunk in self._chunks:
            self.read += len(chunk)
            yield chunk


def png_bytes(size, mode='RGB'):
    from PIL import Image
    buf = io.BytesIO()
    Image.new(mode, size).save(buf, format='PNG')
    return buf.getvalue()


def test_decompression_bomb_limit_is_set():
    from PIL import Image
    import media.artwork  # noqa: F401
    assert Image.MAX_IMAGE_PIXELS == 40_000_000


def test_fetch_image_stops_reading_after_8mb(monkeypatch):
    import requests
    from media import artwork
    resp = FakeResponse(itertools.repeat(b'x' * 65536))  # 永远读不完
    monkeypatch.setattr(requests, 'get', lambda *a, **k: resp)
    with pytest.raises(ValueError):
        artwork._fetch_image('https://img.example.com/a.jpg')
    assert artwork.MAX_IMAGE_BYTES < resp.read <= artwork.MAX_IMAGE_BYTES + 65536
    assert resp.closed


def test_fetch_image_uses_streaming(monkeypatch):
    import requests
    from media import artwork
    seen = {}

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return FakeResponse([png_bytes((40, 30))])
    monkeypatch.setattr(requests, 'get', fake_get)
    im = artwork._fetch_image('https://img.example.com/a.png')
    assert im.size == (40, 30)
    assert seen.get('stream') is True


def test_fetch_image_refuses_huge_dimensions(monkeypatch):
    import warnings
    import requests
    from PIL import Image
    from media import artwork
    data = png_bytes((8000, 6000), mode='1')  # 48M 像素:PIL 只警告,得靠我们自己拦;压缩后很小
    assert len(data) < artwork.MAX_IMAGE_BYTES
    monkeypatch.setattr(requests, 'get', lambda *a, **k: FakeResponse([data]))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', Image.DecompressionBombWarning)
        with pytest.raises(ValueError):
            artwork._fetch_image('https://img.example.com/bomb.png')


def test_progress_hook_abort_is_not_a_download_error(config):
    # 分片下载器吞掉 DownloadError(只当这个分片失败),中止必须用别的异常
    import yt_dlp
    item = make_item()
    item._download_cap = 1000
    with pytest.raises(Exception) as exc:
        item._ydl_progress_hook({'status': 'downloading', 'downloaded_bytes': 1001})
    assert not isinstance(exc.value, yt_dlp.utils.DownloadError)


@pytest.fixture
def hls_server():
    """本机 HLS:40 个 64 KiB 分片,记下每个请求的路径。"""
    import http.server
    import threading
    hits = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            hits.append(self.path)
            if self.path.endswith('.m3u8'):
                body = ('#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:10\n#EXT-X-MEDIA-SEQUENCE:0\n'
                        + ''.join('#EXTINF:10.0,\nseg%d.ts\n' % i for i in range(40))
                        + '#EXT-X-ENDLIST\n').encode()
                ctype = 'application/vnd.apple.mpegurl'
            else:
                body, ctype = b'\x47' * 65536, 'video/mp2t'
            self.send_response(200)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield 'http://127.0.0.1:%d/a.m3u8' % server.server_address[1], hits
    finally:
        server.shutdown()
        server.server_close()


def test_oversized_hls_download_stops_fetching_segments(config, monkeypatch, hls_server):
    # 真的 yt-dlp:分片没有 Content-Length 总数,max_filesize 管不到,只能靠进度钩子
    import media.url
    from media.item import PreparationFailedError
    url, hits = hls_server
    config.set('bot', 'max_download_mb', '1')  # 40 x 64 KiB = 2.5 MiB
    config.set('bot', 'download_attempts', '1')
    monkeypatch.setattr(media.url.artwork, 'ensure', lambda *a, **k: None)
    item = make_item(url)
    with pytest.raises(PreparationFailedError):
        item._download()
    segments = [h for h in hits if h.endswith('.ts')]
    assert len(segments) <= 18  # 1 MiB / 64 KiB = 16,再留点余量;以前 40 个全拉完
    assert not [f for f in os.listdir(var.tmp_folder) if f.startswith(item.id)]
    assert item.ready == 'failed'


def test_quick_video_runs_on_bounded_pool(monkeypatch, config):
    import threading
    from media import artwork
    submitted = []
    monkeypatch.setattr(artwork._thumb_pool, 'submit', lambda key, fn, *a: submitted.append((fn, a)))
    monkeypatch.setattr(threading, 'Thread', mock.Mock(side_effect=AssertionError('no thread per item')))
    monkeypatch.setattr(artwork, 'has_hd', lambda _id: False)
    monkeypatch.setattr(artwork, '_queue', mock.Mock())
    item = make_item()
    item.id = 'hardeningmediathumb'
    try:
        artwork.ensure(item, {'title': 't'})
        assert [fn for fn, _ in submitted] == [artwork._quick_video]
    finally:
        with artwork._lock:
            artwork._quick.discard(item.id)
            artwork._queued.discard(item.id)
            artwork._infos.pop(item.id, None)
    assert artwork._thumb_pool._max == 2


def test_thumb_pool_threads_do_not_block_exit():
    # 排着几百个封面任务时停 bot,不能等它们全跑完进程才退
    import threading
    from media import artwork
    seen = []
    done = threading.Event()

    def job():
        seen.append(threading.current_thread().daemon)
        done.set()
    artwork._thumb_pool.submit('hardening-daemon-check', job)
    assert done.wait(5)
    assert seen == [True]


# ---- media/radio.py -------------------------------------------------------------

@pytest.fixture
def radio(monkeypatch):
    import requests
    from media import radio
    head = mock.Mock(headers={'content-type': 'application/json'})
    monkeypatch.setattr(requests, 'head', lambda *a, **k: head)
    return radio


def test_radio_description_reads_bounded_json(monkeypatch, radio):
    import requests
    resp = FakeResponse(itertools.repeat(b' ' * 4096))
    monkeypatch.setattr(requests, 'get', lambda *a, **k: resp)
    url = 'https://radio.example.com/stream'
    assert radio.get_radio_server_description(url) == url
    assert resp.read <= radio.MAX_DESCRIPTION_BYTES + 16 * 1024
    assert resp.closed


def test_radio_description_still_parses_small_json(monkeypatch, radio):
    import requests
    seen = {}

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return FakeResponse([b'{"servertitle": "Lofi FM"}'])
    monkeypatch.setattr(requests, 'get', fake_get)
    assert radio.get_radio_server_description('https://radio.example.com/stream') == 'Lofi FM'
    assert seen.get('stream') is True


def test_radio_description_tolerates_unexpected_json(monkeypatch, radio):
    import requests
    monkeypatch.setattr(requests, 'get', lambda *a, **k: FakeResponse([b'[1, 2]']))
    url = 'https://radio.example.com/stream'
    assert radio.get_radio_server_description(url) == url


class FakeRaw:
    def __init__(self, body):
        self.stream = io.BytesIO(body)
        self.reads = []

    def read(self, n):
        self.reads.append(n)
        return self.stream.read(n)


def icy_response(metaint, body):
    return FakeResponse([], headers={'icy-metaint': metaint}, raw=FakeRaw(body))


def test_icy_title_normal(monkeypatch, radio):
    import requests
    meta = b"StreamTitle='Song A';"
    meta += b'\0' * (-len(meta) % 16)
    body = b'a' * 16 + struct.pack('B', len(meta) // 16) + meta
    monkeypatch.setattr(requests, 'get', lambda *a, **k: icy_response('16', body))
    assert radio.get_radio_title('https://radio.example.com/s') == 'Song A'


@pytest.mark.parametrize('metaint', [str(10 ** 10), '65537', '0', '-5', 'abc'])
def test_icy_metaint_out_of_range_is_ignored(monkeypatch, radio, metaint):
    import requests
    resp = icy_response(metaint, b'')
    monkeypatch.setattr(requests, 'get', lambda *a, **k: resp)
    url = 'https://radio.example.com/s'
    assert radio.get_radio_title(url) == url
    assert resp.raw.reads == []
    assert resp.closed


def test_icy_truncated_stream_is_ignored(monkeypatch, radio):
    import requests
    monkeypatch.setattr(requests, 'get', lambda *a, **k: icy_response('16', b'a' * 16))
    url = 'https://radio.example.com/s'
    assert radio.get_radio_title(url) == url
