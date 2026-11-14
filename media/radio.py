import re
import json
import logging
import struct
import requests
import traceback
import hashlib

from media.item import BaseItem
from media.item import item_builders, item_loaders, item_id_generators
from constants import tr_cli as tr

log = logging.getLogger("bot")

MAX_DESCRIPTION_BYTES = 64 * 1024
MAX_ICY_METAINT = 64 * 1024


def _get_json(url):
    """读电台状态 JSON,最多 MAX_DESCRIPTION_BYTES 字节;超了或不是 JSON 都抛 ValueError。"""
    with requests.get(url, timeout=10, stream=True) as response:
        data = b''
        for chunk in response.iter_content(16 * 1024):
            data += chunk
            if len(data) > MAX_DESCRIPTION_BYTES:
                raise ValueError("radio status larger than %d bytes" % MAX_DESCRIPTION_BYTES)
    return json.loads(data)


def get_radio_server_description(url):

    log.debug("radio: fetching radio server description")
    p = re.compile('(https?://[^/]*)', re.IGNORECASE)
    res = re.search(p, url)
    base_url = res.group(1)
    url_icecast = base_url + '/status-json.xsl'
    url_shoutcast = base_url + '/stats?json=1'
    try:
        response = requests.head(url_shoutcast, timeout=3)
        if not response.headers.get('content-type', '').startswith(("audio/", "video/")):
            data = _get_json(url_shoutcast)
            title_server = data['servertitle']
            return title_server
            # logging.info("TITLE FOUND SHOUTCAST: " + title_server)
    except (requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.Timeout):
        error_traceback = traceback.format_exc()
        error = error_traceback.rstrip().split("\n")[-1]
        log.debug("radio: unsuccessful attempts on fetching radio description (shoutcast): " + error)
    except ValueError:
        return url
    except (KeyError, TypeError, IndexError):
        log.debug("radio: unexpected shoutcast status response")

    try:
        response = requests.head(url_shoutcast, timeout=3)
        if not response.headers.get('content-type', '').startswith(("audio/", "video/")):
            data = _get_json(url_icecast)
            source = data['icestats']['source']
            if type(source) is list:
                source = source[0]
            title_server = source['server_name']
            if 'server_description' in source:
                title_server += ' - ' + source['server_description']
            # logging.info("TITLE FOUND ICECAST: " + title_server)
            return title_server
    except (requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.Timeout):
        error_traceback = traceback.format_exc()
        error = error_traceback.rstrip().split("\n")[-1]
        log.debug("radio: unsuccessful attempts on fetching radio description (icecast): " + error)
    except (ValueError, KeyError, TypeError, IndexError):
        log.debug("radio: unexpected icecast status response")

    return url


def get_radio_title(url):

    log.debug("radio: fetching radio server description")
    try:
        with requests.get(url, headers={'Icy-MetaData': '1'}, stream=True, timeout=10) as r:
            icy_metaint_header = int(r.headers['icy-metaint'])
            # 这个数决定先读掉多少音频字节,服务器随便填就能让我们读上几个 G
            if not 0 < icy_metaint_header <= MAX_ICY_METAINT:
                raise ValueError("icy-metaint out of range: %d" % icy_metaint_header)
            r.raw.read(icy_metaint_header)

            metadata_length = struct.unpack('B', r.raw.read(1))[0] * 16  # length byte
            metadata = r.raw.read(metadata_length).rstrip(b'\0')
        logging.info(metadata)
        # extract title from the metadata
        m = re.search(br"StreamTitle='([^']*)';", metadata)
        if m:
            title = m.group(1)
            if title:
                return title.decode()
    except (requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.Timeout,
            KeyError, ValueError, struct.error):
        log.debug("radio: unsuccessful attempts on fetching radio title (icy)")
    return url


def radio_item_builder(**kwargs):
    if 'name' in kwargs:
        return RadioItem(kwargs['url'], kwargs['name'])
    else:
        return RadioItem(kwargs['url'], '')


def radio_item_loader(_dict):
    return RadioItem("", "", _dict)


def radio_item_id_generator(**kwargs):
    return hashlib.md5(kwargs['url'].encode()).hexdigest()


item_builders['radio'] = radio_item_builder
item_loaders['radio'] = radio_item_loader
item_id_generators['radio'] = radio_item_id_generator


class RadioItem(BaseItem):
    def __init__(self, url, name="", from_dict=None):
        if from_dict is None:
            super().__init__()
            self.url = url
            if not name:
                self.title = get_radio_server_description(self.url)  # The title of the radio station
            else:
                self.title = name
            self.id = hashlib.md5(url.encode()).hexdigest()
        else:
            super().__init__(from_dict)
            self.url = from_dict['url']
            self.title = from_dict['title']

        self.type = "radio"

    def validate(self):
        self.version += 1  # 0 -> 1, notify the wrapper to save me when validate() is visited the first time
        return True

    def is_ready(self):
        return True

    def uri(self):
        return self.url

    def to_dict(self):
        dict = super().to_dict()
        dict['url'] = self.url
        dict['title'] = self.title

        return dict

    def format_debug_string(self):
        return "[radio] {name} ({url})".format(
            name=self.title,
            url=self.url
        )

    def format_song_string(self, user):
        return tr("radio_item",
                  url=self.url,
                  title=get_radio_title(self.url),  # the title of current song
                  name=self.title,  # the title of radio station
                  user=user
                  )

    def format_current_playing(self, user):
        return tr("now_playing", item=self.format_song_string(user))

    def format_title(self):
        return self.title if self.title else self.url

    def display_type(self):
        return tr("radio")
