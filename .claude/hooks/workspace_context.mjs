#!/usr/bin/env node
// SessionStart hook: emit workspace-aware context based on cwd.
//
// Detects which subrepo the session is starting in and prints a short
// orientation block as additional system context. Designed to be cheap (no
// disk I/O) and silent if cwd is outside file-parser.

const WORKSPACE = '/Users/danielsava/work/file-parser'

async function readEvent() {
    return new Promise((resolve) => {
        let buf = ''
        process.stdin.setEncoding('utf8')
        process.stdin.on('data', (c) => (buf += c))
        process.stdin.on('end', () => {
            try { resolve(JSON.parse(buf)) } catch { resolve(null) }
        })
        setTimeout(() => resolve(null), 200)
    })
}

const evt = await readEvent()
const cwd = evt?.cwd || process.cwd()

if (!cwd.startsWith(WORKSPACE)) process.exit(0)

const rel = cwd.slice(WORKSPACE.length + 1) || ''
const top = rel.split('/')[0] || ''

const profiles = {
    '': {
        title: 'file-parser multi-repo workspace root',
        test: 'No workspace-wide test runner; cd into the relevant subrepo (ploinky/, AssistOSExplorer/, proxies/, etc.) and run that subrepo\'s test command.',
        invariants: [
            'Each top-level dir is its own repo or subproject; edits stay scoped to one subrepo.',
            'Request-time LLM inference goes through achillesAgentLib (ploinky/node_modules/achillesAgentLib).',
            'Commit policy: no AI/coding-agent attribution (no Co-Authored-By, no "Generated with…").',
        ],
        spec: '~/work/file-parser/CLAUDE.md (workspace map)',
    },
    ploinky: {
        title: 'Ploinky runtime/CLI/router',
        test: 'tests/smoke/test_all.sh (smokes) + tests/fast/test_all.sh (fast) + npm test (full)',
        invariants: [
            "Don't hardcode agent ids, backend tags, or agent-owned MCP tool names in framework code.",
            'Cross-agent behavior lives in manifests/plugins/config, not router/WebChat handlers.',
            'achillesAgentLib under node_modules/ is canonical source, not a transient dep.',
        ],
        spec: 'docs/specs/DS005-routing-and-web-surfaces.md, DS011-security-model.md',
    },
    AssistOSExplorer: {
        title: 'Ploinky Explorer + 17 coupled agents',
        test: 'Per-agent: explorer/dpuAgent/soplangAgent → npm test; gitAgent → node --test gitAgent/tests/unit/*.test.mjs',
        invariants: [
            'Request-time LLM goes through achillesAgentLib (ploinky/node_modules/achillesAgentLib).',
            'Do NOT deploy to skills.axiologic.dev unless explicitly asked.',
            '.ploinky/.secrets is encrypted; never edit as plaintext.',
        ],
        spec: 'docs/specs/DS06-ploinky-runtime-invariants.md + each agent\'s docs/specs/matrix.md',
    },
    proxies: {
        title: 'Soul Gateway (LLM gateway at soul.axiologic.dev)',
        test: 'soul-gateway tests under soul-gateway/tests/',
        invariants: [
            'Request-time LLM inference: through achillesAgentLib only.',
            'Soul Gateway lifecycle probes/model discovery: vendor HTTP OK.',
            'Production: admin@45.136.70.141, key ~/proxies_server_private_key.pem.',
        ],
        spec: 'soul-gateway/docs/specs/DS001-request-pipeline.md, DS002-provider-auth.md',
    },
    basic: {
        title: 'Sandbox/runner agents (alpine-bash, bwrap-runner, etc.)',
        test: 'Per-agent local tests; AGENTS.md is canonical.',
        invariants: ['Each runner agent is a containerized sandbox; treat untrusted input as hostile.'],
        spec: 'AGENTS.md',
    },
    coralFlow: {
        title: 'Coral agent workflow',
        test: 'tests/ directory',
        invariants: [],
        spec: 'README.md, coral-agent/',
    },
    'skill-manager-cli': {
        title: 'Standalone Achilles CLI checkout',
        test: 'tests/ at outer root',
        invariants: ['Built-in skills under achilles-cli/src/skills/.', 'LLM through LLMAgent, never direct vendor HTTP.'],
        spec: 'ARCHITECTURE.md',
    },
    'copilot-agents': {
        title: 'Achilles skills, OpenInterpreter, research relay',
        test: 'Per-subagent local tests',
        invariants: [],
        spec: 'AGENTS.md / CLAUDE.md',
    },
    'file-parser-agent': {
        title: 'Standalone MCP file-parser agent',
        test: 'npm test (tests/)',
        invariants: [],
        spec: 'manifest.json, mcp-config.json',
    },
    webassist: {
        title: 'Web assist app (webAdmin + webAssist)',
        test: 'Per-subapp',
        invariants: [],
        spec: 'webAdmin/CLAUDE.md, webAssist/CLAUDE.md',
    },
}

const profile = profiles[top]
if (!profile) process.exit(0)

const heading = top ? `Workspace context for ${top}/:` : 'Workspace context (file-parser root):'
const lines = [
    heading,
    `  Subrepo: ${profile.title}.`,
    `  Test command: ${profile.test}.`,
    `  Spec/canonical guide: ${profile.spec}.`,
]
if (profile.invariants.length) {
    lines.push('  Invariants:')
    for (const inv of profile.invariants) lines.push(`    - ${inv}`)
}
lines.push('  Reading order: parent CLAUDE.md → this subrepo\'s CLAUDE.md → docs/specs.')

console.log(lines.join('\n'))
process.exit(0)
