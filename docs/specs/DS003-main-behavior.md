---
title: DS003-main-behavior
summary: Defines conversion from one caller-selected document to Markdown.
---

## Introduction

A caller uses [process_documents](wiki.html#definition-process-documents) to read a document without implementing each file format.

## Core Content

### Document conversion

The caller submits a `file` path and optional type hint. The tool normalizes the supported input wrappers, resolves and reads the document, and passes the loaded record to the Markdown formatter. It writes document metadata, text previews, and available sampled table rows to stdout. Warnings remain on stderr. The observable result is Markdown, not structured JSON or an LLM response. Filesystem access follows the caller's runtime permissions; path resolution alone is not isolation.
