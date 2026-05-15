#!/usr/bin/env node
// SessionStart hook: warn if the workspace's Claude config hasn't been reviewed
// in >90 days. Reads the marker file `.claude/last-claude-review.txt`. If the
// marker is missing or the date is >90 days old, prints a reminder.
//
// Never blocks. Cheap (single file read).

import { existsSync, readFileSync } from 'node:fs'

const MARKER = '/Users/danielsava/work/file-parser/.claude/last-claude-review.txt'
const MAX_AGE_DAYS = 90

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

// Only fire if the session is starting inside the workspace.
if (!cwd.startsWith('/Users/danielsava/work/file-parser')) process.exit(0)

if (!existsSync(MARKER)) {
    console.log([
        'Claude Code maintenance reminder:',
        '  Marker file missing: /Users/danielsava/work/file-parser/.claude/last-claude-review.txt',
        '  Run the quarterly review (see .claude/MAINTENANCE.md) and reset the marker.',
    ].join('\n'))
    process.exit(0)
}

let raw
try { raw = readFileSync(MARKER, 'utf8').trim() } catch { process.exit(0) }
const last = new Date(raw)
if (isNaN(last.getTime())) {
    console.log(`Claude Code maintenance reminder: invalid date in ${MARKER}: "${raw}". Fix or rerun review.`)
    process.exit(0)
}

const ageDays = Math.floor((Date.now() - last.getTime()) / (1000 * 60 * 60 * 24))
if (ageDays < MAX_AGE_DAYS) process.exit(0)

console.log([
    'Claude Code maintenance reminder:',
    `  Last config review: ${raw} (${ageDays} days ago).`,
    `  ${ageDays - MAX_AGE_DAYS} days overdue.`,
    '  Run the quarterly checklist at .claude/MAINTENANCE.md, then:',
    "  echo $(date +%Y-%m-%d) > ~/work/file-parser/.claude/last-claude-review.txt",
].join('\n'))
process.exit(0)
