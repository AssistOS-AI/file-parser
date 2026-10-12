---
title: DS001-coding-style
summary: Defines the ESM source layout, dependencies, and parser checks.
---

## Introduction

The parser uses Node.js ECMAScript modules.

## Core Content

Source modules use `.mjs` files beneath `file-parser-agent/src/`. The tool entry point composes loading and Markdown formatting; filesystem utilities and stdin parsing remain separate modules. Existing document libraries are declared in `file-parser-agent/package.json`. New dependencies require an explicit justification and must not be added as part of documentation changes.

Unit tests belong to `tests/unit/` and subprocess tests to `tests/integration/`. The package test command is `node --test tests/**/*.test.mjs`. Tests must preserve real output assertions and must not be described as deployment acceptance evidence.
