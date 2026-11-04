"""把 bot 内部用的 HTML 消息转成 Discord Markdown。

命令层和语言文件沿用了 Mumble 版的 HTML(<b>、<br>、<ul><li>、<a href>、<table> ……),
在这里统一转换,命令代码不用逐个改。图片(Mumble 里内嵌的 base64 缩略图)Discord
消息里放不了,直接丢掉。

只依赖标准库,单测不需要 discord.py。
"""

import html
import re
from html.parser import HTMLParser

#: Discord 单条消息的长度上限
MAX_LEN = 2000

_URL_RE = re.compile(r'(https?://[^\s<>()\[\]]+)')
# 需要转义的 Markdown 字符;'#'、'-' 只在行首有意义,在 _escape_line_starts 里单独处理
_MD_SPECIAL = re.compile(r'([\\*_~`|>\[\]])')

_INLINE = {
    'b': '**', 'strong': '**',
    'i': '*', 'em': '*',
    'u': '__',
    's': '~~', 'strike': '~~', 'del': '~~',
    'code': '`',
}
_BLOCK = {'p', 'div', 'table', 'ul', 'ol', 'blockquote', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
_HEADING = {'h1': '# ', 'h2': '## ', 'h3': '### ', 'h4': '### ', 'h5': '### ', 'h6': '### '}


def escape(text):
    """转义普通文本里的 Markdown 字符,URL 原样保留(否则链接里的 _ 会被破坏)。"""
    out = []
    pos = 0
    for m in _URL_RE.finditer(text):
        out.append(_MD_SPECIAL.sub(r'\\\1', text[pos:m.start()]))
        out.append(m.group(1))
        pos = m.end()
    out.append(_MD_SPECIAL.sub(r'\\\1', text[pos:]))
    return ''.join(out)


class _Converter(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.stack = []        # 打开的标签: (tag, out 里的位置, 附加数据)
        self.inline_depth = {}  # marker -> 嵌套层数(<b><b>x</b></b> 只输出一层 **)
        self.list_stack = []   # 每层列表: ['ul'|'ol', 下一个序号]
        self.pre = 0
        self.links = []        # 正在收集文字的 <a>: [href, out 起点]
        self.row_cells = None  # 当前 <tr> 里已有几个单元格

    # ---- 输出 ----

    def _emit(self, s):
        if s:
            self.out.append(s)

    def _newline(self, count=1):
        """确保输出以 count 个换行结尾(开头不加)。"""
        text = ''.join(self.out)
        if not text.strip():
            return
        stripped = text.rstrip(' ')
        have = len(stripped) - len(stripped.rstrip('\n'))
        if have >= count:
            self.out = [stripped]
            return
        self.out = [stripped + '\n' * (count - have)]

    # ---- 标签 ----

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'br':
            self._emit('\n')
            return
        if tag == 'img':
            return
        if tag == 'hr':
            self._newline()
            self._emit('───\n')
            return
        if tag in _INLINE:
            marker = _INLINE[tag]
            depth = self.inline_depth.get(marker, 0)
            self.inline_depth[marker] = depth + 1
            self.stack.append((tag, len(self.out), marker if depth == 0 else ''))
            if depth == 0:
                self._emit(marker)
            return
        if tag == 'a':
            self.links.append([attrs.get('href') or '', len(self.out)])
            self.stack.append((tag, len(self.out), None))
            return
        if tag in ('ul', 'ol'):
            self._newline()
            self.list_stack.append([tag, 1])
        elif tag == 'li':
            self._newline()
            indent = '  ' * max(0, len(self.list_stack) - 1)
            if self.list_stack and self.list_stack[-1][0] == 'ol':
                n = self.list_stack[-1][1]
                self.list_stack[-1][1] += 1
                self._emit(f'{indent}{n}. ')
            else:
                self._emit(f'{indent}- ')
        elif tag == 'tr':
            self._newline()
            self.row_cells = 0
        elif tag in ('td', 'th'):
            if self.row_cells:
                self._emit(' | ')
            self.row_cells = (self.row_cells or 0) + 1
            if tag == 'th':
                self._emit('**')
        elif tag in _HEADING:
            self._newline()
            self._emit(_HEADING[tag])
        elif tag == 'blockquote':
            self._newline()
            self._emit('> ')
        elif tag == 'pre':
            self._newline()
            self._emit('```\n')
            self.pre += 1
        elif tag in _BLOCK:
            self._newline()
        elif tag == 'sup':
            self._emit(' ')
        self.stack.append((tag, len(self.out), None))

    def handle_startendtag(self, tag, attrs):
        # <br /> 这种自闭合标签:只当开标签处理,否则 handle_endtag 会再输出一次换行
        self.handle_starttag(tag, attrs)
        if tag not in ('br', 'img', 'hr'):
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        # 找到最近的同名开标签(容忍没闭合的标签)
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                break
        else:
            if tag == 'br':
                self._emit('\n')
            return
        while len(self.stack) > i + 1:
            self._close(self.stack.pop())
        self._close(self.stack.pop())

    def _close(self, entry):
        tag, start, extra = entry
        if tag in _INLINE:
            marker = _INLINE[tag]
            self.inline_depth[marker] = max(0, self.inline_depth.get(marker, 1) - 1)
            if not extra:
                return
            inner = ''.join(self.out[start + 1:])
            if not inner.strip():
                # 空的 <b></b>:连标记一起去掉,免得留下 "****"
                del self.out[start:]
                self._emit(inner)
                return
            # Markdown 的强调标记不能紧贴空白:把首尾空白挪到标记外面
            lead = inner[:len(inner) - len(inner.lstrip())]
            trail = inner[len(inner.rstrip()):]
            self.out[start:] = [lead + marker + inner.strip() + marker + trail]
            return
        if tag == 'a':
            href, link_start = self.links.pop() if self.links else ('', start)
            label = ''.join(self.out[link_start:]).strip()
            del self.out[link_start:]
            if href and href.startswith(('http://', 'https://')):
                if not label or label.replace('\\', '') == href:
                    self._emit(f'<{href}>')
                else:
                    # [文字](<url>):尖括号让 Discord 不展开链接预览
                    self._emit(f'[{label}](<{href}>)')
            else:
                self._emit(label)
            return
        if tag in ('ul', 'ol'):
            if self.list_stack:
                self.list_stack.pop()
            self._newline()
        elif tag == 'li':
            self._newline()
        elif tag == 'th':
            self._emit('**')
        elif tag == 'tr':
            self.row_cells = None
            self._newline()
        elif tag == 'pre':
            self.pre = max(0, self.pre - 1)
            self._newline()
            self._emit('```')
            self._newline()
        elif tag == 'sup':
            self._emit(' ')
        elif tag in _BLOCK:
            self._newline()

    def handle_data(self, data):
        if self.pre:
            self._emit(data)
            return
        # HTML 里的换行 / 连续空白都等于一个空格
        data = re.sub(r'\s+', ' ', data)
        if not data:
            return
        text = ''.join(self.out)
        if data.startswith(' ') and (not text or text[-1] in ' \n'):
            data = data.lstrip(' ')
        data = escape(data)
        if data.startswith('#') and (not text or text.endswith('\n')):
            data = '\\' + data  # 行首的 # 会被 Discord 当成标题
        self._emit(data)

    def result(self):
        while self.stack:
            self._close(self.stack.pop())
        text = ''.join(self.out)
        text = '\n'.join(line.rstrip() for line in text.split('\n'))
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


def html_to_markdown(message):
    """bot 内部的 HTML 消息 → Discord Markdown。纯文本(不含标签)也会转义。"""
    if message is None:
        return ''
    message = str(message)
    if '<' not in message and '&' not in message:
        lines = [escape(line) for line in message.strip().split('\n')]
        return '\n'.join(('\\' + line) if line.startswith('#') else line for line in lines)
    parser = _Converter()
    try:
        parser.feed(message)
        parser.close()
        return parser.result()
    except Exception:
        # 解析器一般不会抛异常;万一抛了就粗暴地去标签,别让消息发不出去
        return escape(html.unescape(re.sub(r'<[^>]+>', '', message))).strip()


def split_message(text, limit=MAX_LEN):
    """按行切成不超过 limit 的若干段;单行超长时硬切。代码块被切开时补上闭合/开头标记。"""
    if len(text) <= limit:
        return [text] if text else []
    chunks = []
    current = ''
    for line in text.split('\n'):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ''
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = f'{current}\n{line}' if current else line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    # 代码块跨段:前一段补 ```,后一段开头补 ```
    fixed = []
    carry = False
    for chunk in chunks:
        if carry:
            chunk = '```\n' + chunk
        carry = chunk.count('```') % 2 == 1
        if carry:
            chunk = chunk + '\n```'
        fixed.append(chunk)
    return [c for c in fixed if c.strip()]
