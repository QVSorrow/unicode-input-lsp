import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
from unicode_input_lsp.completion import TABLE, complete, snippet, units


def frame(obj):
    data = json.dumps(obj, ensure_ascii=False).encode()
    return b"Content-Length: %d\r\n\r\n" % len(data) + data


def request(method, params=None, id=None):
    result = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if id is not None:
        result["id"] = id
    return result


def run(messages):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    proc = subprocess.run([sys.executable, "-m", "unicode_input_lsp.server"], input=messages,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd="/", env=env, timeout=30)
    data = proc.stdout
    results = []
    while data:
        header, data = data.split(b"\r\n\r\n", 1)
        size = int(header.split(b":", 1)[1])
        results.append(json.loads(data[:size]))
        data = data[size:]
    return proc, results


class LogicTests(unittest.TestCase):
    def test_table_exact_and_every_alias(self):
        self.assertEqual(len(TABLE), 1865)
        self.assertEqual(hashlib.sha256((SRC / 'unicode_input_lsp/data/abbreviations.json').read_bytes()).hexdigest(), 'fa5e317d4d481c8bf12d6438e489376931c18438dd0a68af3683a4cb9e92b5b0')
        for key, value in TABLE.items():
            with self.subTest(key=key):
                items = complete('\\' + key, {'line': 0, 'character': units('\\' + key)})
                self.assertEqual(items[0]['label'], '\\' + key)
                self.assertEqual(items[0]['textEdit']['newText'], value.replace('$CURSOR', ''))
                self.assertEqual(items[0]['textEdit']['range']['start']['character'], 0)
        self.assertEqual(len(complete('\\', {'line': 0, 'character': 1})), 1865)

    def test_utf16_mid_cursor_crlf(self):
        items = complete('😀 \\alpha!\r\nfoo', {'line': 0, 'character': 6})
        alpha = next(i for i in items if i['label'] == '\\alpha')
        self.assertEqual(alpha['textEdit']['range'], {'start': {'line': 0, 'character': 3}, 'end': {'line': 0, 'character': 9}})
        self.assertEqual(complete('😀', {'line': 0, 'character': 2}), [])
        with self.assertRaises(ValueError):
            complete('😀', {'line': 0, 'character': 1})

    def test_right_context_does_not_filter_candidates(self):
        line = 'some (value : \\)'
        cursor = units('some (value : \\')
        items = complete(line, {'line': 0, 'character': cursor})
        self.assertEqual(len(items), 1865)
        self.assertEqual({item['label'] for item in items}, {item['label'] for item in complete('some (value : \\', {'line': 0, 'character': cursor})})
        alpha = next(item for item in items if item['label'] == '\\alpha')
        self.assertEqual(alpha['textEdit']['range'], {'start': {'line': 0, 'character': 14}, 'end': {'line': 0, 'character': 15}})
        self.assertEqual(alpha['textEdit']['newText'], 'α')
        self.assertEqual(line[:14] + alpha['textEdit']['newText'] + line[15:], 'some (value : α)')

    def test_typed_right_suffix_is_candidate_specific(self):
        for suffix, label in [(')', '\\))'), ('b', '\\)b')]:
            line = '\\)' + suffix
            items = complete(line, {'line': 0, 'character': 2})
            chosen = next(item for item in items if item['label'] == label)
            self.assertEqual(chosen['textEdit']['range']['end']['character'], 2 + len(suffix))

    def test_partial_right_suffix_keeps_candidate_and_exact_range(self):
        line = '\\alphX)'
        alpha = next(item for item in complete(line, {'line': 0, 'character': 3})
                     if item['label'] == '\\alpha')
        self.assertEqual(alpha['textEdit']['range'], {'start': {'line': 0, 'character': 0},
                                                       'end': {'line': 0, 'character': 5}})
        self.assertEqual(line[:0] + alpha['textEdit']['newText'] + line[5:], 'αX)')

        line = '\\))X'
        punctuation = next(item for item in complete(line, {'line': 0, 'character': 2})
                           if item['label'] == '\\))')
        self.assertEqual(punctuation['textEdit']['range'], {'start': {'line': 0, 'character': 0},
                                                             'end': {'line': 0, 'character': 3}})
        self.assertEqual(punctuation['textEdit']['newText'], '⸩')
        self.assertEqual(line[:0] + punctuation['textEdit']['newText'] + line[3:], '⸩X')
        self.assertEqual(len(complete('\\!', {'line': 0, 'character': 1})), 1865)
        self.assertEqual(len(complete('\\\\', {'line': 0, 'character': 1})), 1865)

    def test_snippet_and_plain(self):
        self.assertEqual(snippet('a$CURSOR}\\$b'), 'a$0\\}\\\\\\$b')
        a = complete('\\{}', {'line': 0, 'character': 3}, True)[0]
        self.assertEqual(a['textEdit']['newText'], '{$0\\}')
        self.assertEqual(complete('\\{}', {'line': 0, 'character': 3})[0]['textEdit']['newText'], '{}')


class ProtocolTests(unittest.TestCase):
    def test_change_completion_before_delimiter_in_any_language(self):
        uri = 'file:///test.py'
        text_before = 'some (value : \\)'
        cursor = units('some (value : \\')
        msgs = [request('initialize', {}, 1), request('initialized'),
                request('textDocument/didOpen', {'textDocument': {'uri': uri, 'languageId': 'python', 'text': text_before}}),
                request('textDocument/didChange', {'textDocument': {'uri': uri}, 'contentChanges': [{'text': text_before}]}),
                request('textDocument/completion', {'textDocument': {'uri': uri}, 'position': {'line': 0, 'character': cursor}}, 2),
                request('shutdown', id=3), request('exit')]
        proc, out = run(b''.join(map(frame, msgs)))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        items = out[1]['result']['items']
        self.assertEqual(len(items), 1865)
        alpha = next(item for item in items if item['label'] == '\\alpha')
        edit = alpha['textEdit']
        self.assertEqual(edit['range']['end']['character'], cursor)
        self.assertEqual(text_before[:14] + edit['newText'] + text_before[15:], 'some (value : α)')

    def test_brace_trigger_completes_inside_braces(self):
        uri = 'file:///test.python'
        context = {'triggerKind': 2, 'triggerCharacter': '{'}
        msgs = [request('initialize', {'capabilities': {'textDocument': {'completion': {'completionItem': {'snippetSupport': True}}}}}, 1),
                request('initialized'),
                request('textDocument/didOpen', {'textDocument': {'uri': uri, 'languageId': 'python', 'text': '\\{}'}}),
                request('textDocument/completion', {'textDocument': {'uri': uri}, 'position': {'line': 0, 'character': 2}, 'context': context}, 2),
                request('textDocument/didChange', {'textDocument': {'uri': uri}, 'contentChanges': [{'text': '{'}]}),
                request('textDocument/completion', {'textDocument': {'uri': uri}, 'position': {'line': 0, 'character': 1}, 'context': context}, 3),
                request('shutdown', id=4), request('exit')]
        proc, out = run(b''.join(map(frame, msgs)))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        capabilities = out[0]['result']['capabilities']
        self.assertEqual(capabilities['positionEncoding'], 'utf-16')
        self.assertEqual(capabilities['completionProvider']['triggerCharacters'], ['\\', '{'])
        self.assertTrue(out[1]['result']['isIncomplete'])
        items = out[1]['result']['items']
        self.assertEqual(len(items), 4)
        item = next(item for item in items if item['label'] == '\\{}')
        self.assertEqual(item['textEdit']['range'], {'start': {'line': 0, 'character': 0},
                                                      'end': {'line': 0, 'character': 3}})
        self.assertEqual(item['insertTextFormat'], 2)
        self.assertEqual(item['textEdit']['newText'], '{$0\\}')
        self.assertTrue(out[2]['result']['isIncomplete'])
        self.assertEqual(out[2]['result']['items'], [])

    def test_lifecycle_and_documents(self):
        uri = 'file:///test.lean'
        msgs = [request('initialize', {'capabilities': {'textDocument': {'completion': {'completionItem': {'snippetSupport': True}}}}}, 1),
                request('initialized'),
                request('textDocument/didOpen', {'textDocument': {'uri': uri, 'languageId': 'lean', 'text': '😀 \\{}'}}),
                request('textDocument/completion', {'textDocument': {'uri': uri}, 'position': {'line': 0, 'character': 6}}, 2),
                request('textDocument/didChange', {'textDocument': {'uri': uri}, 'contentChanges': [{'text': '\\alpha'}]}),
                request('textDocument/completion', {'textDocument': {'uri': uri}, 'position': {'line': 0, 'character': 6}}, 3),
                request('textDocument/didClose', {'textDocument': {'uri': uri}}),
                request('textDocument/completion', {'textDocument': {'uri': uri}, 'position': {'line': 0, 'character': 0}}, 4),
                request('textDocument/didOpen', {'textDocument': {'uri': uri, 'languageId': 'python', 'text': '\\alpha'}}),
                request('textDocument/completion', {'textDocument': {'uri': uri}, 'position': {'line': 0, 'character': 6}}, 5),
                request('textDocument/didChange', {'textDocument': {'uri': uri}, 'contentChanges': [{'text': '\\to'}]}),
                request('textDocument/completion', {'textDocument': {'uri': uri}, 'position': {'line': 0, 'character': 3}}, 6),
                request('textDocument/didClose', {'textDocument': {'uri': uri}}),
                request('textDocument/completion', {'textDocument': {'uri': uri}, 'position': {'line': 0, 'character': 3}}, 7),
                request('textDocument/didOpen', {'textDocument': {'uri': uri, 'languageId': 'custom-language', 'text': '\\{}'}}),
                request('textDocument/completion', {'textDocument': {'uri': uri}, 'position': {'line': 0, 'character': 3}}, 8),
                request('shutdown', id=9), request('exit')]
        proc, out = run(b''.join(map(frame, msgs)))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out[0]['result']['capabilities']['positionEncoding'], 'utf-16')
        self.assertEqual(out[0]['result']['serverInfo']['name'], 'unicode-input-lsp')
        self.assertEqual(out[1]['result']['items'][0]['textEdit']['newText'], '{$0\\}')
        self.assertEqual(out[2]['result']['items'][0]['label'], '\\alpha')
        self.assertEqual(out[3]['result']['items'], [])
        self.assertEqual(out[4]['result']['items'][0]['label'], '\\alpha')
        self.assertEqual(out[5]['result']['items'][0]['label'], '\\to')
        self.assertEqual(out[6]['result']['items'], [])
        self.assertEqual(out[7]['result']['items'][0]['label'], '\\{}')

    def test_errors_and_plain_capability(self):
        msgs = [request('textDocument/completion', {}, 1), request('initialize', {}, 2),
                request('unknown', {}, 3), request('textDocument/completion', {}, 4),
                request('textDocument/didOpen', {'textDocument': {'uri': 'x', 'languageId': 'lean', 'text': '\\{}'}}),
                request('textDocument/completion', {'textDocument': {'uri': 'x'}, 'position': {'line': 0, 'character': 3}}, 5),
                request('shutdown', id=6), request('exit')]
        malformed = b'Content-Length: 1\r\n\r\n{' + frame({'jsonrpc': '2.0', 'id': 99})
        proc, out = run(malformed + b''.join(map(frame, msgs)))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual([out[i]['error']['code'] for i in (0, 1, 2, 4, 5)], [-32700, -32600, -32002, -32601, -32602])
        self.assertEqual(out[6]['result']['items'][0]['textEdit']['newText'], '{}')
        self.assertEqual(out[6]['result']['items'][0]['insertTextFormat'], 1)

    def test_bad_transport_and_exit(self):
        for data in (b'Content-Length: nope\r\n\r\n', b'Content-Length: 4\r\n\r\n{}', b'Content-Length: 1\n\n{}'):
            proc, out = run(data)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(out, [])
            self.assertIn(b'transport error', proc.stderr)
        proc, _ = run(frame(request('exit')))
        self.assertNotEqual(proc.returncode, 0)


if __name__ == '__main__':
    unittest.main()
