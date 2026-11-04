"""A small stdio LSP server. stdout is reserved for JSON-RPC."""
import json
import sys

from completion import complete

MAX_MESSAGE = 16 * 1024 * 1024


def read_message(stream):
    headers = {}
    total = 0
    while True:
        line = stream.readline(8193)
        total += len(line)
        if not line:
            if total == 0:
                return None
            raise ValueError("EOF in headers")
        if total > 65536 or len(line) > 8192 or not line.endswith(b"\r\n"):
            raise ValueError("invalid headers")
        if line == b"\r\n":
            break
        try:
            name, value = line[:-2].decode("ascii").split(":", 1)
        except (UnicodeError, ValueError):
            raise ValueError("invalid header")
        name = name.strip().lower()
        if name in headers:
            raise ValueError("duplicate header")
        headers[name] = value.strip()
    length = headers.get("content-length", "")
    if not length.isascii() or not length.isdecimal() or int(length) > MAX_MESSAGE:
        raise ValueError("invalid Content-Length")
    length = int(length)
    body = stream.read(length)
    if len(body) != length:
        raise ValueError("EOF in body")
    return body


def send(stream, message):
    data = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stream.write(b"Content-Length: " + str(len(data)).encode("ascii") + b"\r\n\r\n" + data)
    stream.flush()


class Server:
    def __init__(self):
        self.state = "new"
        self.documents = {}
        self.snippets = False

    def dispatch(self, method, params):
        if method == "initialize":
            if self.state != "new":
                raise ValueError("already initialized")
            self.snippets = bool(params.get("capabilities", {}).get("textDocument", {}).get("completion", {}).get("completionItem", {}).get("snippetSupport", False))
            self.state = "running"
            return {"capabilities": {"positionEncoding": "utf-16", "textDocumentSync": {"openClose": True, "change": 1}, "completionProvider": {"triggerCharacters": ["\\", "{"]}}, "serverInfo": {"name": "unicode-input-lsp"}}
        if method == "exit":
            return None
        if self.state != "running":
            raise RuntimeError("server not initialized or shut down")
        if method == "shutdown":
            self.state = "shutdown"
            return None
        if method == "textDocument/didOpen":
            doc = params["textDocument"]
            text = doc["text"]
            if not isinstance(text, str):
                raise ValueError("document text must be a string")
            text.encode("utf-8")
            self.documents[doc["uri"]] = text
        elif method == "textDocument/didChange":
            uri = params["textDocument"]["uri"]
            if uri in self.documents:
                changes = params["contentChanges"]
                if not changes or any("range" in change for change in changes):
                    raise ValueError("expected full document changes")
                text = changes[-1]["text"]
                if not isinstance(text, str):
                    raise ValueError("document text must be a string")
                text.encode("utf-8")
                self.documents[uri] = text
        elif method == "textDocument/didClose":
            self.documents.pop(params["textDocument"]["uri"], None)
        elif method == "textDocument/completion":
            text = self.documents.get(params["textDocument"]["uri"])
            return {"isIncomplete": True, "items": complete(text, params["position"], self.snippets) if text is not None else []}
        else:
            raise LookupError("method not found")
        return None


def run(inp, out):
    server = Server()
    while True:
        try:
            body = read_message(inp)
        except ValueError as exc:
            print("transport error: " + str(exc), file=sys.stderr)
            return 1
        if body is None:
            return 0 if server.state == "shutdown" else 1
        try:
            request = json.loads(body.decode("utf-8"))
        except (UnicodeError, ValueError):
            send(out, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
            continue
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str) or ("id" in request and (not isinstance(request["id"], (str, int)) or isinstance(request["id"], bool))):
            send(out, {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}})
            continue
        method = request["method"]
        has_id = "id" in request
        if method == "exit" and not has_id:
            return 0 if server.state == "shutdown" else 1
        try:
            params = request.get("params", {})
            if not isinstance(params, dict):
                raise ValueError("params must be an object")
            result = server.dispatch(method, params)
            if has_id:
                send(out, {"jsonrpc": "2.0", "id": request["id"], "result": result})
        except (ValueError, KeyError, TypeError, AttributeError, RuntimeError, LookupError) as exc:
            if has_id:
                code = -32601 if isinstance(exc, LookupError) and not isinstance(exc, KeyError) else (-32002 if isinstance(exc, RuntimeError) else -32602)
                send(out, {"jsonrpc": "2.0", "id": request["id"], "error": {"code": code, "message": str(exc)}})
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.stdin.buffer, sys.stdout.buffer))
