# coding=utf-8
"""HTML(命令层 / 语言包)→ Discord Markdown。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.discord_format import html_to_markdown as md, split_message  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_inline_styles_and_escaping():
    assert md('<b>a_b *c*</b> (<i>x</i>)') == '**a\\_b \\*c\\*** (*x*)'
    assert md('plain *text*') == 'plain \\*text\\*'
    assert md('<b> </b>x') == 'x'                      # 空的强调不留 "****"
    assert md('<b><b>nested</b></b>') == '**nested**'
    assert md('<b>bold </b>next') == '**bold** next'    # 标记不能紧贴空白


def test_links():
    assert md('<a href="https://youtu.be/x"><b>Song</b></a>') == '[**Song**](<https://youtu.be/x>)'
    # 文字就是链接本身:只放链接,下划线不转义
    assert md('<a href="https://x.com/a_b?t=1">https://x.com/a_b?t=1</a>') == '<https://x.com/a_b?t=1>'
    assert md('see https://x.com/a_b ok') == 'see https://x.com/a_b ok'
    assert md('<a href="javascript:alert(1)">x</a>') == 'x'


def test_blocks_lists_tables():
    assert md('a<br>b<br />c') == 'a\nb\nc'
    assert md('<ul><li>one</li><li>two</li></ul>') == '- one\n- two'
    assert md('<ol><li>one</li><li>two</li></ol>') == '1. one\n2. two'
    assert md('<table><tr><th>ID</th><th>Name</th></tr><tr><td>1</td><td>Jazz</td></tr></table>') == \
        '**ID** | **Name**\n1 | Jazz'
    assert md('<h3>Commands</h3>x') == '### Commands\nx'
    assert md('#tag at start') == '\\#tag at start'
    assert md('<img src="data:image/png;base64,xxx"/>Title') == 'Title'
    assert md('A &amp; B &lt;3') == 'A & B <3'


def test_mention_syntax_is_not_live():
    # 歌名里的 @everyone 之类:发送时 allowed_mentions 已关掉,这里至少不能变成别的格式
    assert md('@everyone <b>hi</b>') == '@everyone **hi**'


def test_every_language_string_converts():
    for lang in ('en_US', 'zh_CN', 'ja_JP'):
        with open(os.path.join(ROOT, 'lang', f'{lang}.json'), encoding='utf-8') as f:
            strings = json.load(f)['cli']
        for key, value in strings.items():
            out = md(value)
            assert '<b>' not in out and '<i>' not in out and '<br' not in out, (lang, key, out)


def test_split_message():
    assert split_message('') == []
    assert split_message('short') == ['short']
    text = '\n'.join(['x' * 100] * 50)
    parts = split_message(text, limit=1000)
    assert all(len(p) <= 1000 for p in parts)
    assert '\n'.join(parts) == text
    assert [len(p) for p in split_message('y' * 2500, limit=1000)] == [1000, 1000, 500]
    code = '```\n' + '\n'.join(['line'] * 400) + '\n```'
    for part in split_message(code, limit=500):
        assert part.count('```') % 2 == 0
