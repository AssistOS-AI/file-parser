#!/usr/bin/env node
// PreToolUse(Edit|Write|MultiEdit) hook: opportunistic JS convention reminder
// for workspace files.
//
// If the target file is inside ~/work/file-parser AND ends in .js/.mjs/.cjs,
// emit a soft reminder via the documented hookSpecificOutput.additionalContext
// channel so Claude sees it in the system reminder attached to the tool call.
// Exits 0 always (never blocks).
//
// Why guidance vs. enforcement: there is no single lint command at workspace
// root (each subrepo has its own). Running per-subrepo lint here would be too
// slow and brittle. Keep the rule visible; defer enforcement to per-subrepo
// CI.

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
const tool = evt?.tool_name
const fp = evt?.tool_input?.file_path

if (!['Edit', 'Write', 'MultiEdit'].includes(tool)) process.exit(0)
if (typeof fp !== 'string' || !fp.startsWith(WORKSPACE)) process.exit(0)

const ext = fp.match(/\.(mjs|cjs|js)$/)?.[1]
if (!ext) process.exit(0)

const rel = fp.slice(WORKSPACE.length + 1)
const top = rel.split('/')[0]
const reminders = []
reminders.push('Workspace JS convention reminder:')
reminders.push('  - 4-space JS indent, ESM (`import`/`export`), trailing commas multi-line.')
reminders.push('  - camelCase filenames, beside related logic.')
reminders.push('  - LLM access via achillesAgentLib (ploinky/node_modules/achillesAgentLib), never direct vendor HTTP.')
if (top === 'ploinky') {
    reminders.push('  - ploinky framework: no agent-specific ids/tags/MCP tool names in router/WebChat.')
}
if (top === 'AssistOSExplorer') {
    reminders.push('  - AssistOSExplorer: paths from agentRoot/data dir; long-lived state durable outside process memory.')
}
reminders.push('  - Commit policy: no AI/coding-agent attribution (see root CLAUDE.md).')

const payload = {
    hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        additionalContext: reminders.join('\n'),
    },
}
process.stdout.write(JSON.stringify(payload))
process.exit(0)
