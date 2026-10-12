---
title: DS002-input-and-output
summary: Defines accepted input wrappers, path handling, Markdown output, and warnings.
---

## Introduction

The caller provides the file and runtime access to it.

## Core Content

The input must be a JSON object containing a nonempty `file` string, either directly or beneath `input`, `arguments`, or `args`. `type` and its direct-invocation alias `fileType` are optional format hints. Absolute paths remain absolute. Library callers can supply `options.workspaceRoot`; the loader otherwise uses `WORKSPACE_PATH`, then the process working directory. The command does not pass `options.workspaceRoot`, so its relative file input follows the environment-variable and working-directory fallback. The path resolver does not enforce containment.

The command must send Markdown to stdout and warnings to stderr. A missing file argument or an uncaught processing error must exit with status 1. Spreadsheet output contains sampled rows and total-row metadata; callers must not interpret a sample as a complete workbook export.
