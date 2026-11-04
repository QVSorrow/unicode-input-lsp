# unicode-input-lsp

A small stdio Language Server Protocol (LSP) server that offers Unicode completions from an abbreviation table. It accepts any `languageId`; configure it only for languages where the table is useful. It is a completion source, not an input rewriter: the editor must show and accept a completion.

## Install

### pipx

Current pipx requires Python 3.10 or newer. Install from GitHub with [pipx](https://pipx.pypa.io/):

```sh
pipx install 'git+https://github.com/QVSorrow/unicode-input-lsp.git'
```

### uv

Requires Python 3.9 or newer. Install from GitHub with [uv](https://docs.astral.sh/uv/):

```sh
uv tool install 'git+https://github.com/QVSorrow/unicode-input-lsp.git'
```

### Nix

With Nix flakes enabled, install the package in your profile:

```sh
nix profile install github:QVSorrow/unicode-input-lsp#unicode-input-lsp
```

pipx and uv install the `unicode-input-lsp` command in an isolated Python environment. The Nix package includes its Python runtime. The command runs the persistent stdio LSP server. It does not provide a help screen or a one-shot conversion mode.

## Run locally

With Nix and flakes enabled:

```sh
nix run .
```

This starts the persistent LSP server, which reads and writes JSON-RPC on standard input and output. It is not a command-line help or one-shot conversion tool. To build the package instead:

```sh
nix build .#unicode-input-lsp
```

To run the tests without Nix:

```sh
python3 -m unittest discover -s tests -v
```

To run or build the GitHub flake, use `nix run github:QVSorrow/unicode-input-lsp` or `nix build github:QVSorrow/unicode-input-lsp`.

## Helix

Add this server alongside (not instead of) the language server already configured for each language. For example:

```toml
[language-server.unicode-input-lsp]
command = "unicode-input-lsp"

[[language]]
name = "lean"
language-servers = ["lean", "unicode-input-lsp"]
```

Install `unicode-input-lsp` so that command is on `PATH`. Keep your existing server name and add `unicode-input-lsp` to its language's `language-servers` list. Configure other languages in the same way. Helix decides which language IDs use the server; the server itself does not restrict them.

## Behavior and limits

- Matching is case-sensitive. Completions come from the left of the cursor. Existing right-hand text does not remove candidates; each candidate's edit replaces only its longest compatible right-hand key prefix, leaving the rest unchanged.
- The server supports snippets when the client advertises snippet support. It does not parse syntax, so it can offer items in comments and strings.
- It uses full-document sync and UTF-16 positions. It does not perform VS Code-style automatic input rewriting.
- The table comes from Lean's Unicode input mappings. Initial-slash mappings, diagnostics, and broad editor behavior are not claimed here.

The abbreviation data has its own Apache-2.0 license and provenance; see [the data notes](docs/data-provenance.md) and [data license](src/unicode_input_lsp/data/LICENSE). The server is licensed under Apache-2.0; see [LICENSE](LICENSE).
