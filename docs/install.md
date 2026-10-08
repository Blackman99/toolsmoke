# Install

toolsmoke is a single pure-Python package with **zero runtime dependencies**. Python 3.9+.

## Run without installing (recommended)

```bash
uvx --from git+https://github.com/Blackman99/toolsmoke toolsmoke --demo broken
```

Pin a version with `@v0.1.1`:

```bash
uvx --from git+https://github.com/Blackman99/toolsmoke@v0.1.1 toolsmoke --help
```

## Install as a command

=== "pipx"

    ```bash
    pipx install git+https://github.com/Blackman99/toolsmoke
    ```

=== "uv tool"

    ```bash
    uv tool install git+https://github.com/Blackman99/toolsmoke
    ```

=== "release wheel"

    ```bash
    pipx install https://github.com/Blackman99/toolsmoke/releases/download/v0.1.1/toolsmoke-0.1.1-py3-none-any.whl
    ```

=== "pip"

    ```bash
    python -m pip install git+https://github.com/Blackman99/toolsmoke
    ```

This installs two commands:

| Command | What it does |
|---|---|
| `toolsmoke` | Runs the probes against an endpoint |
| `toolsmoke-mock` | A local OpenAI/Anthropic-compatible mock server with good and broken modes (for testing and demos) |

## Verify

```bash
toolsmoke --version
toolsmoke --demo good     # every probe should pass
toolsmoke --demo broken   # a server with common real-world bugs
```

!!! note "PyPI"
    v0.1 is distributed through GitHub (source and release wheels). A PyPI package is planned, see the [roadmap](https://github.com/Blackman99/toolsmoke/blob/main/ROADMAP.md).

## From source

```bash
git clone https://github.com/Blackman99/toolsmoke && cd toolsmoke
pip install -e ".[dev]" && pytest -q
```
