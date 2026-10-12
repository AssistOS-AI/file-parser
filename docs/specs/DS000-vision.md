---
title: DS000-vision
summary: Defines file-parser document conversion and its ownership boundary.
---

## Introduction

file-parser gives MCP callers readable document content.

## Core Content

The product must accept a single readable document and expose its extracted content as Markdown. The implementation belongs to `file-parser-agent/`; sibling repositories have independent responsibilities. Optional LLM extraction is a separate helper and is not part of the `process_documents` invocation path.
