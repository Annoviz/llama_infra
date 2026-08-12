# Rule: No Inline Comments in .env Values Used by Make

Make's `-include .env` imports the entire line after `=` as the variable value, including inline comments.

## Why

`VLLM_VERSION=0.25.0              # PyPI: vllm` caused Docker to try building with version `0.25.0              ` — trailing spaces from the comment text became part of the image tag. Wasted a config validation cycle.

## How to Apply

- Use separate `#` lines for comments in `.env`, not inline.
- If adding new `.env` vars, verify with `make -p | grep VARNAME` or `echo $VAR` from Makefile.
- Existing project convention: no inline comments on value-bearing lines.
