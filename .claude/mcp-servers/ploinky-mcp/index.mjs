#!/usr/bin/env node
// ploinky-mcp — MCP stdio server for the file-parser workspace.
//
// Exposes:
//   - ploinky_status         (proxies `ploinky status`)
//   - ploinky_logs           (proxies `ploinky logs <agent>`)
//   - agent_manifest         (reads <agent>/manifest.json)
//   - ds_spec_lookup         (finds DS-NNN spec files anywhere in the workspace)
//   - skill_by_name          (locates SKILL.md / cskill.md / oskill.md / etc.)
//
// Runs only when invoked from inside the workspace; no-ops outside.

import { spawn } from 'node:child_process'
import { readFile, readdir } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { join, basename } from 'node:path'
import { glob } from 'node:fs/promises'

import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import {
    CallToolRequestSchema,
    ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js'

const WORKSPACE = '/Users/danielsava/work/file-parser'

// ---- helpers ----------------------------------------------------------------

function runShell(cmd, args, { cwd = WORKSPACE, timeoutMs = 15000 } = {}) {
    return new Promise((res) => {
        const child = spawn(cmd, args, { cwd, env: process.env })
        let stdout = ''
        let stderr = ''
        const t = setTimeout(() => {
            child.kill('SIGKILL')
            res({ ok: false, code: -1, stdout, stderr: stderr + `\n[timeout after ${timeoutMs}ms]` })
        }, timeoutMs)
        child.stdout.on('data', (b) => (stdout += b.toString()))
        child.stderr.on('data', (b) => (stderr += b.toString()))
        child.on('close', (code) => {
            clearTimeout(t)
            res({ ok: code === 0, code, stdout, stderr })
        })
        child.on('error', (err) => {
            clearTimeout(t)
            res({ ok: false, code: -1, stdout, stderr: String(err) })
        })
    })
}

async function findFiles(pattern, { excludeDirs = ['node_modules', '.git', '.history', 'dist', 'build'] } = {}) {
    const out = []
    for await (const p of glob(pattern, { cwd: WORKSPACE })) {
        if (excludeDirs.some((d) => p.split('/').includes(d))) continue
        out.push(join(WORKSPACE, p))
    }
    return out
}

// Manual recursive walker that DOES descend into hidden (`.dotted`) directories.
// node:fs/promises glob skips dotted entries by default, which would hide every
// skill (they live under .claude/ or .agents/). Use this for any search that
// needs to find files under hidden directories.
const SKIP_DIRS = new Set(['node_modules', '.git', '.history', 'dist', 'build', 'coverage'])

async function walkForDirNamed(targetName, root = WORKSPACE) {
    const hits = []
    async function recurse(dir) {
        let entries
        try { entries = await readdir(dir, { withFileTypes: true }) } catch { return }
        for (const e of entries) {
            if (!e.isDirectory()) continue
            if (SKIP_DIRS.has(e.name)) continue
            const full = join(dir, e.name)
            if (e.name === targetName) hits.push(full)
            await recurse(full)
        }
    }
    await recurse(root)
    return hits
}

// ---- tool handlers ----------------------------------------------------------

async function toolPloinkyStatus() {
    const r = await runShell('ploinky', ['status'])
    if (!r.ok) {
        return {
            isError: true,
            content: [{ type: 'text', text: `ploinky status failed (code ${r.code}):\n${r.stderr || r.stdout}` }],
        }
    }
    return { content: [{ type: 'text', text: r.stdout }] }
}

async function toolPloinkyLogs({ mode = 'last', count = 50, container, tail_container }) {
    // mode='tail'  → `ploinky logs tail` (router log; full file).
    // mode='last'  → `ploinky logs last <count>` (router log; last N lines).
    // mode='container' → `podman logs --tail <count> <container>` (per-agent
    //                    container logs). Find the container name via
    //                    `ploinky_status`.
    if (mode === 'tail') {
        const r = await runShell('ploinky', ['logs', 'tail'])
        if (!r.ok) {
            return { isError: true, content: [{ type: 'text', text: `ploinky logs tail failed (code ${r.code}):\n${r.stderr || r.stdout}` }] }
        }
        return { content: [{ type: 'text', text: r.stdout }] }
    }
    if (mode === 'last') {
        const r = await runShell('ploinky', ['logs', 'last', String(count)])
        if (!r.ok) {
            return { isError: true, content: [{ type: 'text', text: `ploinky logs last ${count} failed (code ${r.code}):\n${r.stderr || r.stdout}` }] }
        }
        return { content: [{ type: 'text', text: r.stdout }] }
    }
    if (mode === 'container') {
        const target = container || tail_container
        if (!target) {
            return { isError: true, content: [{ type: 'text', text: 'mode=container requires container=<podman container name or id>' }] }
        }
        const r = await runShell('podman', ['logs', '--tail', String(count), target])
        if (!r.ok) {
            return { isError: true, content: [{ type: 'text', text: `podman logs ${target} failed (code ${r.code}):\n${r.stderr || r.stdout}` }] }
        }
        // podman writes to stderr too; concatenate for the caller.
        return { content: [{ type: 'text', text: (r.stdout + (r.stderr ? '\n--- stderr ---\n' + r.stderr : '')) }] }
    }
    return { isError: true, content: [{ type: 'text', text: `unknown mode=${mode}. Expected one of: tail, last, container.` }] }
}

async function toolAgentManifest({ agent_path }) {
    if (!agent_path) {
        return { isError: true, content: [{ type: 'text', text: 'agent_path is required' }] }
    }
    // Accept absolute or workspace-relative.
    const abs = agent_path.startsWith('/') ? agent_path : join(WORKSPACE, agent_path)
    const manifest = join(abs, 'manifest.json')
    if (!existsSync(manifest)) {
        return { isError: true, content: [{ type: 'text', text: `No manifest.json at ${manifest}` }] }
    }
    try {
        const raw = await readFile(manifest, 'utf8')
        const parsed = JSON.parse(raw)
        return { content: [{ type: 'text', text: JSON.stringify(parsed, null, 2) }] }
    } catch (err) {
        return { isError: true, content: [{ type: 'text', text: `Failed to read/parse ${manifest}: ${err.message}` }] }
    }
}

async function toolDsSpecLookup({ spec_id, query }) {
    // spec_id like "DS005" or "DS06". query is free-text substring on filename or content.
    let pattern
    if (spec_id) {
        pattern = `**/docs/specs/${spec_id}*.md`
    } else if (query) {
        pattern = `**/docs/specs/**/*.md`
    } else {
        return { isError: true, content: [{ type: 'text', text: 'spec_id or query is required' }] }
    }
    let matches = await findFiles(pattern)
    if (query && !spec_id) {
        const q = query.toLowerCase()
        const filtered = []
        for (const m of matches) {
            try {
                const t = (await readFile(m, 'utf8')).toLowerCase()
                if (t.includes(q) || basename(m).toLowerCase().includes(q)) filtered.push(m)
            } catch { /* skip unreadable */ }
        }
        matches = filtered
    }
    if (!matches.length) {
        return { content: [{ type: 'text', text: `No DS specs found for ${spec_id || query}` }] }
    }
    return { content: [{ type: 'text', text: matches.map((m) => `- ${m}`).join('\n') }] }
}

async function toolSkillByName({ name, type }) {
    if (!name) {
        return { isError: true, content: [{ type: 'text', text: 'name is required' }] }
    }
    // type filter: which descriptor file(s) count as a "skill" of that type.
    const filenameMap = {
        cskill: ['cskill.md'],
        oskill: ['oskill.md'],
        mskill: ['mskill.md'],
        tskill: ['tskill.md'],
        dcgskill: ['dcgskill.md'],
        skill: ['skill.md'],
        SKILL: ['SKILL.md'],
    }
    const wantedNames = type
        ? filenameMap[type] || []
        : Object.values(filenameMap).flat()

    // Walk descends into dotted dirs (skills live under .claude/ and .agents/).
    const skillDirs = await walkForDirNamed(name)
    const out = []
    for (const dir of skillDirs) {
        for (const fn of wantedNames) {
            const candidate = join(dir, fn)
            if (existsSync(candidate)) out.push(candidate)
        }
    }
    if (!out.length) {
        return { content: [{ type: 'text', text: `No skill found matching name=${name} type=${type || 'any'}` }] }
    }
    return { content: [{ type: 'text', text: out.map((m) => `- ${m}`).join('\n') }] }
}

// ---- server -----------------------------------------------------------------

const server = new Server(
    { name: 'ploinky-mcp', version: '0.1.0' },
    { capabilities: { tools: {} } },
)

const TOOLS = [
    {
        name: 'ploinky_status',
        description: 'Run `ploinky status` from the file-parser workspace and return its output.',
        inputSchema: { type: 'object', properties: {}, additionalProperties: false },
    },
    {
        name: 'ploinky_logs',
        description: 'Retrieve Ploinky router or per-agent container logs. mode=tail proxies `ploinky logs tail`; mode=last proxies `ploinky logs last <count>`; mode=container proxies `podman logs --tail <count> <container>` for a specific agent container (container name comes from ploinky_status output).',
        inputSchema: {
            type: 'object',
            properties: {
                mode: { type: 'string', enum: ['tail', 'last', 'container'], description: 'tail = full router log; last = last N router lines; container = podman logs for an agent container.' },
                count: { type: 'number', description: 'Number of lines (used by mode=last and mode=container). Default 50.' },
                container: { type: 'string', description: 'Podman container name or id. Required when mode=container.' },
            },
            additionalProperties: false,
        },
    },
    {
        name: 'agent_manifest',
        description: 'Read and parse an agent\'s manifest.json. Pass agent_path absolute or workspace-relative (e.g., AssistOSExplorer/explorer).',
        inputSchema: {
            type: 'object',
            properties: { agent_path: { type: 'string' } },
            required: ['agent_path'],
            additionalProperties: false,
        },
    },
    {
        name: 'ds_spec_lookup',
        description: 'Find DS-NNN design-spec files. Pass spec_id (e.g., "DS005") for direct lookup, or query for substring match across spec content/filenames.',
        inputSchema: {
            type: 'object',
            properties: {
                spec_id: { type: 'string', description: 'DS identifier like DS005 or DS06.' },
                query: { type: 'string', description: 'Free-text substring search across spec content and names.' },
            },
            additionalProperties: false,
        },
    },
    {
        name: 'skill_by_name',
        description: 'Locate skill definition files (cskill.md / oskill.md / mskill.md / tskill.md / dcgskill.md / skill.md / SKILL.md) by name.',
        inputSchema: {
            type: 'object',
            properties: {
                name: { type: 'string', description: 'Skill folder name (e.g., article_build).' },
                type: { type: 'string', enum: ['cskill', 'oskill', 'mskill', 'tskill', 'dcgskill', 'skill', 'SKILL'], description: 'Restrict to a specific subsystem type.' },
            },
            required: ['name'],
            additionalProperties: false,
        },
    },
]

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }))

server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const { name, arguments: args = {} } = req.params
    switch (name) {
        case 'ploinky_status': return toolPloinkyStatus()
        case 'ploinky_logs': return toolPloinkyLogs(args)
        case 'agent_manifest': return toolAgentManifest(args)
        case 'ds_spec_lookup': return toolDsSpecLookup(args)
        case 'skill_by_name': return toolSkillByName(args)
        default:
            return { isError: true, content: [{ type: 'text', text: `Unknown tool: ${name}` }] }
    }
})

const transport = new StdioServerTransport()
await server.connect(transport)
