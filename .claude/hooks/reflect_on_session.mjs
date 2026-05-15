#!/usr/bin/env node
// Stop hook: if the session edited multiple files inside the workspace, emit a
// soft reminder that CLAUDE.md may need updating while context is fresh.
//
// Scans the transcript for Edit/Write tool calls under ~/work/file-parser.
// Threshold: 3+ writes triggers the nudge. Never blocks.

import { readFileSync, existsSync } from 'node:fs'

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
const transcriptPath = evt?.transcript_path
if (!transcriptPath || !existsSync(transcriptPath)) process.exit(0)

let txt
try { txt = readFileSync(transcriptPath, 'utf8') } catch { process.exit(0) }

const editedFiles = new Set()
for (const line of txt.split('\n')) {
    if (!line.trim()) continue
    let obj
    try { obj = JSON.parse(line) } catch { continue }
    const blocks = obj?.message?.content
    if (!Array.isArray(blocks)) continue
    for (const b of blocks) {
        if (b?.type !== 'tool_use') continue
        if (!['Edit', 'Write', 'MultiEdit'].includes(b?.name)) continue
        const fp = b?.input?.file_path
        if (typeof fp === 'string' && fp.startsWith(WORKSPACE)) editedFiles.add(fp)
    }
}

if (editedFiles.size < 3) process.exit(0)

const sample = Array.from(editedFiles).slice(0, 5)
const msg = [
    'Workspace-reflection nudge:',
    `  This session edited ${editedFiles.size} files under ${WORKSPACE}.`,
    '  Before exiting, consider whether any CLAUDE.md needs updating to reflect new conventions, gotchas, or invariants you discovered.',
    '  Touched (sample):',
    ...sample.map((f) => `    - ${f.replace(WORKSPACE + '/', '')}`),
]
console.log(msg.join('\n'))
process.exit(0)
