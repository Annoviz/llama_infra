# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Agent instructions

All routing rules, global conventions, architecture notes, developer commands, and subagent definitions are in [AGENTS.md](AGENTS.md). This file is the single source of truth — do not duplicate content here.

## Mode constraints

- When the user asks to plan, or when the system is set to plan mode, you are STRICTLY PROHIBITED from modifying files or running edit tools.
- You must output your execution strategies strictly as text descriptions in the terminal console. Do not proceed to implementation until explicitly told "Go ahead".
