# coding=utf-8
"""斜杠命令表:每条命令的名字、参数、权限和三种语言的说明。

这一层与 Discord 无关(只是数据),DiscordLink 据此生成 app_commands,/help 据此生成帮助。
命令处理函数还是旧的 handler(bot, user, text, command, parameter) 签名:各参数的值按
这里声明的顺序用空格拼成 parameter 字符串传进去,所以原有的解析逻辑不用改。

名字可以在 configuration.ini 的 [commands] 段改(值 = 斜杠命令名,只取逗号前第一个)。
"""
import re
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

#: Discord 支持的本地化 locale -> 我们的语言包
LOCALES = {'en': 'en_US', 'zh-CN': 'zh_CN', 'ja': 'ja_JP'}
LANG_TO_LOCALE = {v: k for k, v in LOCALES.items()}

NAME_RE = re.compile(r'^[-_a-z0-9]{1,32}$')


@dataclass(frozen=True)
class Opt:
    name: str
    desc: dict
    kind: str = 'str'        # str | int | user | choice | bool
    required: bool = False
    choices: Tuple[str, ...] = ()
    min: Optional[int] = None
    max: Optional[int] = None
    autocomplete: Optional[str] = None  # queue | playlist | file | radio | tag


@dataclass(frozen=True)
class Spec:
    key: str                  # [commands] 里的键,也是 handler 的标识
    name: str                 # 默认斜杠命令名
    handler: Callable
    desc: dict
    options: Tuple[Opt, ...] = ()
    admin: bool = False
    ephemeral: bool = False   # 回复只给发命令的人看
    outside_channel: bool = False  # 不在 bot 所在语音频道也能用
    joins_voice: bool = False  # bot 不在语音频道时先进发命令的人所在的频道
    group: str = 'other'      # /help 里的分组


def _d(en, zh, ja):
    return {'en': en, 'zh-CN': zh, 'ja': ja}


def specs():
    """所有斜杠命令(按 /help 的显示顺序)。延迟导入 handler,避免循环导入。"""
    from . import admin, library, personal, playback, sources, streaming, volume, web

    def opt_query(required=True):
        return Opt('query', _d('Song name, URL, or queue number', '歌名、链接,或队列序号', '曲名・URL・キュー番号'),
                   required=required)

    def opt_url(required=True):
        return Opt('url', _d('URL', '链接', 'URL'), required=required)

    def opt_index(desc=None, required=False, autocomplete='queue'):
        return Opt('index', desc or _d('Position in the queue', '队列中的序号', 'キュー内の番号'),
                   kind='int', required=required, min=1, autocomplete=autocomplete)

    tags_opt = Opt('tags', _d('Tags, separated by ","', '标签,用 "," 分隔', 'タグ(「,」区切り)'), required=True,
                   autocomplete='tag')

    return [
        # ---- 播放控制 ----
        Spec('play', 'play', playback.cmd_play, group='control', joins_voice=True,
             desc=_d('Play a song (name / URL) or resume; a number plays that queue entry',
                     '点歌(歌名 / 链接)或继续播放;填数字则播放队列里的第几首',
                     '曲を再生(曲名・URL)/再開。数字ならキューのその曲を再生'),
             options=(Opt('query', _d('Song name, URL, or queue number', '歌名、链接,或队列序号',
                                      '曲名・URL・キュー番号'), autocomplete='queue'),
                      Opt('start', _d('Start at (e.g. 1:30), only with a queue number',
                                      '从这里开始(如 1:30),仅配合队列序号',
                                      '開始位置(例 1:30)、キュー番号と一緒に')))),
        Spec('pause', 'pause', playback.cmd_pause, group='control',
             desc=_d('Pause playback', '暂停', '一時停止')),
        Spec('stop', 'stop', playback.cmd_stop, group='control',
             desc=_d('Stop playback', '停止播放', '再生を停止')),
        Spec('skip', 'skip', playback.cmd_skip, group='control',
             desc=_d('Skip to the next song', '下一首', '次の曲へ')),
        Spec('last', 'last', playback.cmd_last, group='control',
             desc=_d('Jump to the last song in the queue', '跳到队列最后一首', 'キューの最後の曲へ')),
        Spec('volume', 'volume', volume.cmd_volume, group='control',
             desc=_d('Show or set the volume', '查看或设置音量', '音量を表示・設定'),
             options=(Opt('percent', _d('0–100', '0–100', '0–100'), kind='int', min=0, max=100),)),
        Spec('mode', 'mode', playback.cmd_mode, group='control',
             desc=_d('Show or set the playback mode', '查看或设置播放模式', '再生モードを表示・設定'),
             options=(Opt('mode', _d('one-shot · repeat (loop the queue) · random · autoplay (from the library) · '
                                     'single (loop one song)',
                                     'one-shot 播完即删 · repeat 循环队列 · random 随机 · autoplay 从曲库随机 · single 单曲循环',
                                     'one-shot 再生後削除・repeat キューをループ・random・autoplay ライブラリから・single 1曲ループ'),
                          kind='choice', choices=('one-shot', 'repeat', 'random', 'autoplay', 'single')),)),
        Spec('stop_and_getout', 'leave', playback.cmd_stop_and_getout, group='control',
             desc=_d('Stop and leave the voice channel', '停止并离开语音频道', '停止してボイスチャンネルから退出')),
        Spec('joinme', 'join', admin.cmd_joinme, group='control', outside_channel=True,
             desc=_d('Join your voice channel', '进入你所在的语音频道', 'あなたのボイスチャンネルに参加')),

        # ---- 队列 ----
        Spec('current_music', 'np', playback.cmd_current_music, group='queue',
             desc=_d('Show the current song', '显示正在播放的歌', '再生中の曲を表示')),
        Spec('queue', 'queue', playback.cmd_queue, group='queue',
             desc=_d('Show the queue', '显示播放队列', 'キューを表示')),
        Spec('lyrics', 'lyrics', playback.cmd_lyrics, group='queue',
             desc=_d('Post the lyrics of the current song', '发送当前歌曲的歌词', '再生中の曲の歌詞を表示')),
        Spec('remove', 'remove', playback.cmd_remove, group='queue',
             desc=_d('Remove a song from the queue', '从队列删除一首', 'キューから曲を削除'),
             options=(opt_index(required=True),)),
        Spec('repeat', 'repeat', playback.cmd_repeat, group='queue',
             desc=_d('Repeat the current song N more times', '当前歌曲再重复 N 遍', '再生中の曲を N 回リピート'),
             options=(Opt('times', _d('1–20 (default 1)', '1–20(默认 1)', '1–20(既定 1)'),
                          kind='int', min=1, max=20),)),
        Spec('random', 'shuffle', playback.cmd_random, group='queue',
             desc=_d('Shuffle the queue', '打乱队列', 'キューをシャッフル')),
        Spec('clear', 'clear', playback.cmd_clear, group='queue',
             desc=_d('Clear the queue', '清空队列', 'キューをクリア')),
        Spec('add_from_shortlist', 'pick', library.cmd_shortlist, group='queue', joins_voice=True,
             desc=_d('Queue items from the last search results', '从上次搜索结果里选歌加入队列',
                     '直前の検索結果からキューに追加'),
             options=(Opt('indexes', _d('Numbers separated by spaces, or * for all', '序号(空格分隔),* 表示全部',
                                        '番号(スペース区切り)、* で全部'), required=True),)),

        # ---- 点歌来源 ----
        Spec('play_url', 'url', sources.cmd_play_url, group='sources', joins_voice=True,
             desc=_d('Queue a YouTube / SoundCloud / … URL', '添加 YouTube / SoundCloud 等链接',
                     'YouTube / SoundCloud などの URL を追加'),
             options=(opt_url(),)),
        Spec('play_playlist', 'playlist', sources.cmd_play_playlist, group='sources', joins_voice=True,
             desc=_d('Queue a whole YouTube / SoundCloud playlist', '添加整个 YouTube / SoundCloud 播放列表',
                     'YouTube / SoundCloud のプレイリストを追加'),
             options=(opt_url(), Opt('offset', _d('Start from this entry', '从第几首开始', '何曲目から'),
                                     kind='int', min=1))),
        Spec('yt_search', 'ysearch', sources.cmd_yt_search, group='sources',
             desc=_d('Search YouTube (then /pick)', '搜索 YouTube(再用 /pick 选)', 'YouTube を検索(/pick で選択)'),
             options=(Opt('query', _d('Keywords; "-n" for the next page', '关键词;填 "-n" 翻到下一页',
                                      'キーワード。「-n」で次のページ'), required=True),)),
        Spec('yt_play', 'yplay', sources.cmd_yt_play, group='sources', joins_voice=True,
             desc=_d('Queue the first YouTube result', '添加 YouTube 搜索的第一个结果', 'YouTube 検索の最初の結果を追加'),
             options=(opt_query(),)),
        Spec('play_bilibili', 'bili', streaming.cmd_play_bilibili, group='sources', joins_voice=True,
             desc=_d('Queue a Bilibili video (URL or BV id)', '添加 B 站视频(链接或 BV 号)',
                     'bilibili の動画を追加(URL または BV 番号)'),
             options=(Opt('video', _d('URL or BV id', '链接或 BV 号', 'URL または BV 番号'), required=True),)),
        Spec('play_spotify', 'spotify', streaming.cmd_play_spotify, group='sources', joins_voice=True,
             desc=_d('Queue from a Spotify link, or search Spotify', '添加 Spotify 链接,或按关键词搜索 Spotify',
                     'Spotify のリンクを追加、またはキーワード検索'),
             options=(opt_query(),)),
        Spec('play_live', 'live', streaming.cmd_play_live, group='sources', joins_voice=True,
             desc=_d('Queue a live stream (URL or keywords)', '添加直播(链接或关键词)', 'ライブ配信を追加(URL またはキーワード)'),
             options=(opt_query(),)),
        Spec('play_radio', 'radio', sources.cmd_play_radio, group='sources', joins_voice=True,
             desc=_d('Queue a radio stream; no argument lists the presets', '添加电台;不填参数列出预设电台',
                     'ラジオを追加。引数なしでプリセット一覧'),
             options=(Opt('station', _d('Preset name or stream URL', '预设名或流地址', 'プリセット名またはストリーム URL'),
                          autocomplete='radio'),)),
        Spec('rb_query', 'rbquery', sources.cmd_rb_query, group='sources',
             desc=_d('Search radio-browser.info', '在 radio-browser.info 搜索电台', 'radio-browser.info でラジオ局を検索'),
             options=(Opt('keyword', _d('Station name', '电台名', '局名'), required=True),)),
        Spec('rb_play', 'rbplay', sources.cmd_rb_play, group='sources', joins_voice=True,
             desc=_d('Queue a radio-browser.info station by id', '按 ID 添加 radio-browser.info 电台',
                     'radio-browser.info の局を ID で追加'),
             options=(Opt('id', _d('Station id from /rbquery', '/rbquery 结果里的 ID', '/rbquery の ID'), required=True),)),

        # ---- 本地曲库 ----
        Spec('play_file', 'file', sources.cmd_play_file, group='library', joins_voice=True,
             desc=_d('Queue a file or folder from the music library', '添加曲库里的文件或文件夹',
                     'ライブラリのファイル/フォルダを追加'),
             options=(Opt('path', _d('Path, folder, or part of the path', '路径、文件夹或路径里的关键词',
                                     'パス・フォルダ・パスの一部'), required=True, autocomplete='file'),)),
        Spec('play_file_match', 'filematch', sources.cmd_play_file_match, group='library', joins_voice=True,
             desc=_d('Queue every file whose name contains the text', '添加文件名包含该文字的所有文件',
                     'ファイル名に文字列を含む全ファイルを追加'),
             options=(Opt('pattern', _d('Text to look for (case-insensitive)', '要找的文字(不区分大小写)',
                                        '検索文字列(大文字小文字を区別しない)'), required=True),)),
        Spec('list_file', 'listfile', sources.cmd_list_file, group='library',
             desc=_d('List files in the music library', '列出曲库文件', 'ライブラリのファイル一覧'),
             options=(Opt('pattern', _d('Only paths containing this text', '只列出路径包含该文字的',
                                        'この文字列を含むパスのみ'),),)),
        Spec('search', 'search', library.cmd_search_library, group='library',
             desc=_d('Search the music library (then /pick)', '搜索曲库(再用 /pick 选)', 'ライブラリを検索(/pick で選択)'),
             options=(Opt('keywords', _d('Keywords separated by spaces', '关键词,空格分隔', 'キーワード(スペース区切り)'),
                          required=True),)),
        Spec('play_tag', 'tag', library.cmd_play_tags, group='library', joins_voice=True,
             desc=_d('Queue every song with these tags', '添加带这些标签的所有歌曲', 'このタグを持つ全曲を追加'),
             options=(tags_opt,)),
        Spec('find_tagged', 'findtagged', library.cmd_find_tagged, group='library',
             desc=_d('Find songs with these tags (then /pick)', '查找带这些标签的歌曲(再用 /pick 选)',
                     'このタグを持つ曲を検索(/pick で選択)'),
             options=(tags_opt,)),
        Spec('add_tag', 'addtag', library.cmd_add_tag, group='library',
             desc=_d('Tag a song in the queue (current song by default)', '给队列里的歌加标签(默认当前这首)',
                     'キューの曲にタグを付ける(既定は再生中の曲)'),
             options=(Opt('index', _d('Queue number, or * for every song', '队列序号,* 表示全部', 'キュー番号、* で全曲'),
                          autocomplete='queue'), tags_opt)),
        Spec('remove_tag', 'untag', library.cmd_remove_tag, group='library',
             desc=_d('Remove tags from a song in the queue (* removes all)', '删除队列里歌曲的标签(* 删除全部)',
                     'キューの曲からタグを削除(* で全部)'),
             options=(Opt('index', _d('Queue number, or * for every song', '队列序号,* 表示全部', 'キュー番号、* で全曲'),
                          autocomplete='queue'),
                      Opt('tags', _d('Tags separated by ",", or * for all', '标签(用 "," 分隔),* 表示全部',
                                     'タグ(「,」区切り)、* で全部'), required=True, autocomplete='tag'))),
        Spec('delete_from_library', 'delete', library.cmd_delete_from_library, group='library',
             desc=_d('Delete items of the last search results from the library', '把上次搜索结果里的条目从曲库删除',
                     '直前の検索結果の項目をライブラリから削除'),
             options=(Opt('indexes', _d('Numbers separated by spaces', '序号,空格分隔', '番号(スペース区切り)'),
                          required=True),)),

        # ---- 个人歌单 ----
        Spec('bind', 'bind', personal.cmd_bind, group='personal', ephemeral=True, outside_channel=True,
             desc=_d('Link your Discord account to the web UI', '把 Discord 账号绑定到网页', 'Discord アカウントを Web UI と連携'),
             options=(Opt('code', _d('6-digit code from the web UI (avatar → Link Discord)',
                                     '网页上生成的 6 位码(头像 → 绑定 Discord)',
                                     'Web UI で発行した 6 桁のコード(アバター → Discord 連携)'), required=True),)),
        Spec('unbind', 'unbind', personal.cmd_unbind, group='personal', ephemeral=True, outside_channel=True,
             desc=_d('Unlink your Discord account from the web UI', '解除 Discord 账号与网页的绑定',
                     'Discord アカウントと Web UI の連携を解除')),
        Spec('my_playlist', 'mylist', personal.cmd_my_playlist, group='personal', joins_voice=True,
             desc=_d('List your playlists, or queue one', '列出我的歌单,或把一个歌单加入队列',
                     '自分のプレイリスト一覧/キューに追加'),
             options=(Opt('playlist', _d('Name or number', '歌单名或序号', '名前または番号'), autocomplete='playlist'),
                      Opt('shuffle', _d('Shuffle before queueing', '打乱后加入', 'シャッフルして追加'), kind='bool'))),
        Spec('favorite', 'fav', personal.cmd_favorite, group='personal',
             desc=_d('Add the current song to a playlist (Favorites by default)', '把当前歌曲加入歌单(默认「我的收藏」)',
                     '再生中の曲をプレイリストに追加(既定はお気に入り)'),
             options=(Opt('playlist', _d('Playlist name', '歌单名', 'プレイリスト名'), autocomplete='playlist'),)),

        # ---- 网页 ----
        Spec('requests_webinterface_access', 'web', web.cmd_web_access, group='other', ephemeral=True,
             outside_channel=True,
             desc=_d('Get the web interface address', '获取网页界面地址', 'Web インターフェースのアドレスを表示')),
        Spec('change_user_password', 'password', web.cmd_user_password, group='other', ephemeral=True,
             outside_channel=True,
             desc=_d('Set your web interface password (password auth only)', '设置网页登录密码(仅密码认证模式)',
                     'Web のパスワードを設定(パスワード認証時のみ)'),
             options=(Opt('password', _d('New password', '新密码', '新しいパスワード'), required=True),)),
        Spec('help', 'help', admin.cmd_help, group='other', ephemeral=True, outside_channel=True,
             desc=_d('Show all commands', '显示所有命令', 'コマンド一覧')),
        Spec('version', 'version', admin.cmd_version, group='other', ephemeral=True, outside_channel=True,
             desc=_d('Show the bot version', '显示版本', 'バージョンを表示')),

        # ---- 管理员 ----
        Spec('max_volume', 'maxvolume', volume.cmd_max_volume, group='admin', admin=True,
             desc=_d('Show or set the maximum volume', '查看或设置最大音量', '最大音量を表示・設定'),
             options=(Opt('percent', _d('0–100', '0–100', '0–100'), kind='int', min=0, max=100),)),
        Spec('user_ban', 'userban', admin.cmd_user_ban, group='admin', admin=True, ephemeral=True,
             outside_channel=True,
             desc=_d('Ban a user from using the bot; no argument lists bans', '禁止某人使用 bot;不填列出已封禁',
                     'ユーザーの利用を禁止。引数なしで一覧'),
             options=(Opt('user', _d('User', '用户', 'ユーザー'), kind='user'),)),
        Spec('user_unban', 'userunban', admin.cmd_user_unban, group='admin', admin=True, ephemeral=True,
             outside_channel=True,
             desc=_d('Lift a user ban', '解除封禁', '利用禁止を解除'),
             options=(Opt('user', _d('User', '用户', 'ユーザー'), kind='user', required=True),)),
        Spec('url_ban', 'urlban', admin.cmd_url_ban, group='admin', admin=True,
             desc=_d('Ban a URL (the current song by default) and remove it from the library',
                     '封禁链接(默认当前歌曲)并从曲库删除', 'URL を禁止(既定は再生中の曲)し、ライブラリから削除'),
             options=(opt_url(required=False),)),
        Spec('url_unban', 'urlunban', admin.cmd_url_unban, group='admin', admin=True,
             desc=_d('Unban a URL', '解封链接', 'URL の禁止を解除'), options=(opt_url(),)),
        Spec('url_ban_list', 'urlbanlist', admin.cmd_url_ban_list, group='admin', admin=True, ephemeral=True,
             desc=_d('List banned URLs', '列出被封禁的链接', '禁止 URL の一覧')),
        Spec('url_whitelist', 'urlwhitelist', admin.cmd_url_whitelist, group='admin', admin=True,
             desc=_d('Whitelist a URL', '把链接加入白名单', 'URL をホワイトリストに追加'), options=(opt_url(),)),
        Spec('url_unwhitelist', 'urlunwhitelist', admin.cmd_url_unwhitelist, group='admin', admin=True,
             desc=_d('Remove a URL from the whitelist', '把链接移出白名单', 'URL をホワイトリストから削除'),
             options=(opt_url(),)),
        Spec('url_whitelist_list', 'urlwhitelistlist', admin.cmd_url_whitelist_list, group='admin', admin=True,
             ephemeral=True,
             desc=_d('List whitelisted URLs', '列出白名单', 'ホワイトリストの一覧')),
        Spec('rescan', 'rescan', library.cmd_refresh_cache, group='admin', admin=True,
             desc=_d('Rescan the local music folder', '重新扫描本地音乐文件夹', 'ローカル音楽フォルダを再スキャン')),
        Spec('drop_database', 'dropdatabase', library.cmd_drop_database, group='admin', admin=True, ephemeral=True,
             desc=_d('Wipe all settings and the music library', '清空所有设置和曲库', '全設定とライブラリを消去')),
        Spec('add_webinterface_user', 'webuseradd', web.cmd_web_user_add, group='admin', admin=True, ephemeral=True,
             desc=_d('Allow a user to log in to the web UI (password auth)', '允许某人登录网页(密码认证模式)',
                     'Web UI へのログインを許可(パスワード認証)'),
             options=(Opt('name', _d('Display name', '显示名', '表示名'), required=True),)),
        Spec('remove_webinterface_user', 'webuserdel', web.cmd_web_user_remove, group='admin', admin=True,
             ephemeral=True,
             desc=_d('Revoke web UI access (password auth)', '取消某人的网页登录权限(密码认证模式)',
                     'Web UI へのアクセスを取り消す(パスワード認証)'),
             options=(Opt('name', _d('Display name', '显示名', '表示名'), required=True),)),
        Spec('list_webinterface_user', 'webuserlist', web.cmd_web_user_list, group='admin', admin=True,
             ephemeral=True,
             desc=_d('List users allowed to use the web UI (password auth)', '列出可以登录网页的人(密码认证模式)',
                     'Web UI を使えるユーザーの一覧(パスワード認証)')),
        Spec('update', 'update', admin.cmd_update, group='admin', admin=True, ephemeral=True,
             desc=_d('Upgrade yt-dlp and spotdl (restart to apply)', '升级 yt-dlp 和 spotdl(重启后生效)',
                     'yt-dlp と spotdl を更新(再起動で反映)')),
        Spec('kill', 'kill', admin.cmd_kill, group='admin', admin=True, ephemeral=True, outside_channel=True,
             desc=_d('Shut the bot down', '关闭 bot', 'ボットを終了')),
    ]


def configured_specs(config=None):
    """套用 [commands] 段的改名,并校验名字。返回 [(slash 名, Spec)]。"""
    out = []
    seen = set()
    for spec in specs():
        name = spec.name
        if config is not None and config.has_option('commands', spec.key):
            raw = (config.get('commands', spec.key) or '').split(',')[0].strip().lower()
            if raw:
                name = raw
        if not NAME_RE.match(name):
            raise ValueError(f"[commands] {spec.key} = {name!r} is not a valid slash command name "
                             "(1-32 characters: lowercase letters, digits, '-' or '_')")
        if name in seen:
            raise ValueError(f"[commands] slash command name {name!r} is used twice")
        seen.add(name)
        out.append((name, spec))
    return out


def text_for(desc, language):
    """按 bot 的语言(en_US / zh_CN / ja_JP)取说明文字,缺了就用英文。"""
    locale = LANG_TO_LOCALE.get(language, 'en')
    return desc.get(locale) or desc['en']


GROUP_TITLES = {
    'control': _d('Playback', '播放控制', '再生'),
    'queue': _d('Queue', '队列', 'キュー'),
    'sources': _d('Add music', '点歌', '曲の追加'),
    'library': _d('Music library', '本地曲库', 'ライブラリ'),
    'personal': _d('Personal playlists', '个人歌单', 'マイプレイリスト'),
    'other': _d('Other', '其他', 'その他'),
    'admin': _d('Admin', '管理员', '管理者'),
}


def help_lines(language, include_admin=False, config=None):
    """/help 的内容(HTML,交给 DiscordLink 转 Markdown)。按分组列出命令和参数。"""
    import html
    groups = {}
    for name, spec in configured_specs(config):
        if spec.admin and not include_admin:
            continue
        groups.setdefault(spec.group, []).append((name, spec))
    lines = []
    for group in GROUP_TITLES:
        if group not in groups:
            continue
        lines.append(f"<b>{html.escape(text_for(GROUP_TITLES[group], language))}</b>")
        for name, spec in groups[group]:
            args = ' '.join((f"{o.name}" if o.required else f"[{o.name}]") for o in spec.options)
            args = f" <i>{html.escape(args)}</i>" if args else ''
            lines.append(f"<code>/{name}</code>{args} — {html.escape(text_for(spec.desc, language))}")
    return lines
