# coding=utf-8
"""按服务器(guild)分开的数据:设置、队列、封禁 / 白名单规则。

表由 database.DatabaseMigration(settings 库 v3)建好;这里是这些表的全部查询,以后换 PostgreSQL
只需要另写一个同样接口的类。全局的东西(Web 令牌、用户、权限、缓存钉选……)仍在 var.db。

规则(access_rule)分两级:scope '' 是全局,否则是服务器 ID;检查时两级任一命中就算。
"""

import json
import logging
import sqlite3
import time
from contextlib import closing

log = logging.getLogger("bot")

RULE_KINDS = ('user_ban', 'url_ban', 'url_whitelist')
GLOBAL = ''

# 旧版不分服务器的设置(botamusique 表的 section/option)-> guild_settings 的 key
LEGACY_SETTINGS = {
    ('bot', 'volume'): 'volume',
    ('bot', 'max_volume'): 'max_volume',
    ('playlist', 'playback_mode'): 'playback_mode',
    ('discord', 'panel_message'): 'panel_message',
    ('channel', 'default'): 'channel.default',
    ('channel', 'follow'): 'channel.follow',
    ('channel', 'follow_user'): 'channel.follow_user',
    ('channel', 'return_home'): 'channel.return_home',
    ('channel', 'idle_pause_minutes'): 'channel.idle_pause_minutes',
    ('channel', 'idle_resume'): 'channel.idle_resume',
}
LEGACY_MARKER = ('migration', 'legacy_guild')


class GuildStore:
    def __init__(self, db_path):
        self.db_path = db_path

    def _conn(self):
        # 每次调用开一个连接(和 SettingsDatabase 一样),不跨线程共享;with 块即一个事务
        return closing(sqlite3.connect(self.db_path, timeout=10))

    # ---- 设置 -----------------------------------------------------------

    def get(self, guild_id, key, default=None):
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM guild_settings WHERE guild_id=? AND key=?",
                               (str(guild_id), key)).fetchone()
        return default if row is None or row[0] is None else row[0]

    def set(self, guild_id, key, value):
        with self._conn() as conn, conn:
            conn.execute("INSERT OR REPLACE INTO guild_settings (guild_id, key, value) VALUES (?, ?, ?)",
                         (str(guild_id), key, None if value is None else str(value)))

    def delete(self, guild_id, key):
        with self._conn() as conn, conn:
            conn.execute("DELETE FROM guild_settings WHERE guild_id=? AND key=?", (str(guild_id), key))

    def guilds_with(self, key):
        """所有设置了 key 的服务器:{guild_id: value}(启动时找重启前在语音里的服务器)。"""
        with self._conn() as conn:
            rows = conn.execute("SELECT guild_id, value FROM guild_settings WHERE key=? AND value IS NOT NULL "
                                "AND value != ''", (key,)).fetchall()
        return {gid: value for gid, value in rows}

    # ---- 队列 -----------------------------------------------------------

    def save_queue(self, guild_id, current_index, entries):
        """entries: [{'id', 'user', 'group'?}],整个替换。"""
        guild_id = str(guild_id)
        rows = []
        for position, entry in enumerate(entries):
            group = entry.get('group')
            rows.append((guild_id, position, entry['id'], entry.get('user') or '',
                         json.dumps(group, ensure_ascii=False) if group else None))
        with self._conn() as conn, conn:
            conn.execute("DELETE FROM guild_queue WHERE guild_id=?", (guild_id,))
            conn.executemany("INSERT INTO guild_queue (guild_id, position, item_id, user, grp) "
                             "VALUES (?, ?, ?, ?, ?)", rows)
            conn.execute("INSERT OR REPLACE INTO guild_queue_state (guild_id, current_index) VALUES (?, ?)",
                         (guild_id, int(current_index)))

    def load_queue(self, guild_id):
        """-> (current_index, entries);没存过是 (-1, [])。"""
        guild_id = str(guild_id)
        with self._conn() as conn:
            state = conn.execute("SELECT current_index FROM guild_queue_state WHERE guild_id=?",
                                 (guild_id,)).fetchone()
            rows = conn.execute("SELECT item_id, user, grp FROM guild_queue WHERE guild_id=? "
                                "ORDER BY position", (guild_id,)).fetchall()
        entries = []
        for item_id, user, grp in rows:
            entry = {'id': item_id, 'user': user}
            if grp:
                try:
                    entry['group'] = json.loads(grp)
                except ValueError:
                    pass
            entries.append(entry)
        return (state[0] if state else -1), entries

    # ---- 封禁 / 白名单 -----------------------------------------------------

    def add_rule(self, scope, kind, value, created_by='', note=''):
        if kind not in RULE_KINDS:
            raise ValueError(kind)
        with self._conn() as conn, conn:
            conn.execute("INSERT OR REPLACE INTO access_rule (scope, kind, value, note, created_by, created_at) "
                         "VALUES (?, ?, ?, ?, ?, ?)",
                         (str(scope), kind, str(value), note or '', str(created_by or ''), time.time()))

    def remove_rule(self, scope, kind, value):
        """-> 是否真的删掉了一条。"""
        with self._conn() as conn, conn:
            cur = conn.execute("DELETE FROM access_rule WHERE scope=? AND kind=? AND value=?",
                               (str(scope), kind, str(value)))
            return cur.rowcount > 0

    def has_rule(self, kind, value, guild_id=None, include_global=True):
        """全局有,或者 guild_id 这个服务器有。guild_id 为空只看全局;include_global=False 只看这个服务器。"""
        if include_global:
            scopes = (GLOBAL, str(guild_id)) if guild_id else (GLOBAL,)
        elif guild_id:
            scopes = (str(guild_id),)
        else:
            return False
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT 1 FROM access_rule WHERE kind=? AND value=? "
                f"AND scope IN ({','.join('?' * len(scopes))}) LIMIT 1",
                (kind, str(value)) + scopes).fetchone()
        return row is not None

    def list_rules(self, kind, scope=GLOBAL):
        """某一级的规则(按添加时间):[{'value', 'note', 'created_by', 'created_at'}]。"""
        with self._conn() as conn:
            rows = conn.execute("SELECT value, note, created_by, created_at FROM access_rule "
                                "WHERE kind=? AND scope=? ORDER BY created_at, value",
                                (kind, str(scope))).fetchall()
        return [{'value': v, 'note': n, 'created_by': c, 'created_at': t} for v, n, c, t in rows]

    # ---- 全部清空 ---------------------------------------------------------

    TABLES = ('guild_settings', 'guild_queue', 'guild_queue_state', 'access_rule')

    def clear_all(self):
        """/dropdatabase:删掉所有服务器的设置、队列和规则(表结构保留)。"""
        with self._conn() as conn, conn:
            for table in self.TABLES:
                conn.execute(f"DELETE FROM {table}")

    # ---- 旧数据 -----------------------------------------------------------

    def legacy_guild(self):
        """接收了旧版设置的服务器 ID;还没迁移过是 None。"""
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM botamusique WHERE section=? AND option=?",
                               LEGACY_MARKER).fetchone()
        return row[0] if row else None

    def adopt_legacy(self, guild_id):
        """把旧版不分服务器的设置复制给 guild_id(只做一次,标记在 botamusique 的 migration 段)。

        设置和队列 -> 这个服务器;封禁 / 白名单 -> 全局规则。旧行不删,换回旧镜像还能用。
        已经有的新数据不覆盖。返回这次是否做了迁移。
        """
        guild_id = str(guild_id)
        with self._conn() as conn, conn:
            if conn.execute("SELECT 1 FROM botamusique WHERE section=? AND option=?",
                            LEGACY_MARKER).fetchone():
                return False
            legacy = {(s, o): v for s, o, v in conn.execute(
                "SELECT section, option, value FROM botamusique")}

            for (section, option), key in LEGACY_SETTINGS.items():
                value = legacy.get((section, option))
                if value is not None:
                    conn.execute("INSERT OR IGNORE INTO guild_settings (guild_id, key, value) VALUES (?, ?, ?)",
                                 (guild_id, key, str(value)))

            self._adopt_legacy_queue(conn, guild_id, legacy)

            now = time.time()
            for (section, option), value in legacy.items():
                if section in RULE_KINDS:
                    note = value if section == 'user_ban' and value else ''
                    conn.execute("INSERT OR IGNORE INTO access_rule "
                                 "(scope, kind, value, note, created_by, created_at) VALUES (?, ?, ?, ?, '', ?)",
                                 (GLOBAL, section, option, note, now))

            conn.execute("INSERT OR REPLACE INTO botamusique (section, option, value) VALUES (?, ?, ?)",
                         LEGACY_MARKER + (guild_id,))
        log.info("store: adopted the pre-multi-guild settings into guild %s", guild_id)
        return True

    @staticmethod
    def _adopt_legacy_queue(conn, guild_id, legacy):
        if conn.execute("SELECT 1 FROM guild_queue_state WHERE guild_id=?", (guild_id,)).fetchone():
            return
        try:
            current_index = int(legacy.get(('playlist', 'current_index'), -1))
        except (TypeError, ValueError):
            current_index = -1
        items = []
        for (section, option), value in legacy.items():
            if section != 'playlist_item':
                continue
            try:
                record = json.loads(value)
                items.append((int(option), record))
            except (TypeError, ValueError):
                continue
        items.sort(key=lambda pair: pair[0])
        for position, (_, record) in enumerate(items):
            if not isinstance(record, dict) or not record.get('id'):
                continue
            group = record.get('group')
            conn.execute("INSERT INTO guild_queue (guild_id, position, item_id, user, grp) VALUES (?, ?, ?, ?, ?)",
                         (guild_id, position, record['id'], record.get('user') or '',
                          json.dumps(group, ensure_ascii=False) if group else None))
        conn.execute("INSERT INTO guild_queue_state (guild_id, current_index) VALUES (?, ?)",
                     (guild_id, current_index))
