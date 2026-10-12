import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { pipeline } from 'node:stream/promises';
import { createGzip, gunzipSync } from 'node:zlib';
import assert from 'node:assert/strict';

const workspace = '/Users/danielsava/work/file-parser';
const names = ['full_budget_prepare_2026-10-04_codex', 'vllm_stage2_2026-10-04_codex', 'live-apparatus-vllm-20261003-170239_postcleanup_claude'];
const roots = names.map(name => `evidence/hwl/${name}`);
const allowlist = roots.flatMap(root => ['AssistOSExplorer', 'container-image-builds', 'local-llms', 'ploinky', 'deps/achillesAgentLib', 'deps/mcp-sdk'].map(name => `${root}/${name}`));
allowlist.push('container-image-builds/sources/ploinky');
allowlist.push(`${roots[0]}/proposal_codex/candidate-4425e2a3f5dbbcf5b22e7942dfe2fd84`, `${roots[1]}/proposal_codex/candidate-5c4b9581f2a1494715f83ac729b52860`, `${roots[2]}/evidence/candidate-752291a0db0906c0e701a38c7a611872`);
allowlist.push(`${roots[0]}/proposal_codex/candidate_4425e2a3f5dbbcf5b22e7942dfe2fd84_codex.tar`, `${roots[1]}/proposal_codex/candidate_5c4b9581f2a1494715f83ac729b52860_codex.tar`, `${roots[2]}/evidence/candidate-752291a0db0906c0e701a38c7a611872.tar`);
const output = path.join(workspace, 'evidence/hwl/source-retention-2026-10-11');
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
const fileSha = file => sha(fs.readFileSync(file));
const json = value => JSON.stringify(value, null, 2) + '\n';
const run = (bin, args, options = {}) => execFileSync(bin, args, { encoding: 'utf8', maxBuffer: 40 * 1024 * 1024, env: { ...process.env, COPYFILE_DISABLE: '1', GIT_OPTIONAL_LOCKS: '0' }, ...options }).trim();
const git = (directory, args) => run('/usr/bin/git', ['--no-optional-locks', '-C', directory, ...args]);
const excluded = relative => allowlist.some(target => relative === target || relative.startsWith(target + '/'));

function targetPath(relative) {
  assert(allowlist.includes(relative), 'Target is not in the exact allowlist');
  const absolute = path.join(workspace, relative);
  assert.equal(fs.realpathSync(absolute), absolute, 'Symlink or noncanonical target');
  const stat = fs.lstatSync(absolute);
  assert(!stat.isSymbolicLink() && (stat.isDirectory() || stat.isFile()));
  assert.equal(stat.uid, process.getuid(), 'Target owner changed');
  return absolute;
}

function inventory(directory, excludeTargets = false) {
  const entries = [];
  function walk(absolute, relative) {
    if (absolute.includes('/.ploinky/repos')) throw new Error('Protected managed checkout');
    if (excludeTargets && excluded(path.relative(workspace, absolute))) return;
    const stat = fs.lstatSync(absolute);
    const entry = { path: relative, mode: stat.mode & 0o7777 };
    if (stat.isSymbolicLink()) entries.push({ ...entry, type: 'symlink', target: fs.readlinkSync(absolute) });
    else if (stat.isFile()) entries.push({ ...entry, type: 'file', bytes: stat.size, sha256: fileSha(absolute) });
    else if (stat.isDirectory()) {
      entries.push({ ...entry, type: 'directory' });
      for (const name of fs.readdirSync(absolute).sort()) {
        if (name === '.git') {
          assert.equal(relative, '.', 'Unexpected nested Git metadata');
          continue;
        }
        walk(path.join(absolute, name), relative === '.' ? name : relative + '/' + name);
      }
    } else throw new Error('Unsupported filesystem entry: ' + absolute);
  }
  walk(directory, '.');
  return entries;
}

function gitIdentity(directory) {
  if (!fs.existsSync(path.join(directory, '.git'))) return null;
  assert(fs.lstatSync(path.join(directory, '.git')).isDirectory(), 'Linked Git worktree');
  const status = git(directory, ['status', '--porcelain=v1', '--untracked-files=all']);
  assert.equal(status, '', 'Dirty snapshot must not be deleted');
  assert.equal(git(directory, ['rev-parse', '--absolute-git-dir']), directory + '/.git');
  const worktrees = git(directory, ['worktree', 'list', '--porcelain']);
  assert.equal((worktrees.match(/^worktree /gm) ?? []).length, 1, 'Additional worktree');
  const head = git(directory, ['rev-parse', 'HEAD']);
  const commit = execFileSync('/usr/bin/git', ['--no-optional-locks', '-C', directory, 'cat-file', 'commit', head], { encoding: 'utf8', env: { ...process.env, GIT_OPTIONAL_LOCKS: '0' } });
  assert.equal(run('/usr/bin/git', ['hash-object', '-t', 'commit', '--stdin'], { input: commit }), head);
  return { head, tree: git(directory, ['rev-parse', 'HEAD^{tree}']), commit, refs: git(directory, ['show-ref']), status, worktrees };
}

function fingerprint(absolute) {
  const s = fs.lstatSync(absolute);
  return { dev: s.dev, ino: s.ino, uid: s.uid, mode: s.mode & 0o7777, type: s.isDirectory() ? 'directory' : 'file' };
}

function activityGate() {
  const absoluteTargets = allowlist.map(p => path.join(workspace, p));
  const inside = p => absoluteTargets.some(t => p === t || p.startsWith(t + '/'));
  const lsof = run('/usr/sbin/lsof', ['-nP', '-Fpn']);
  assert(!lsof.split('\n').some(line => line.startsWith('n') && inside(line.slice(1))), 'Open target files');
  const ps = run('/bin/ps', ['-axo', 'pid=,command=']);
  assert(!ps.split('\n').some(line => absoluteTargets.some(t => line.includes(t))), 'Process references target');
  const inbound = [];
  function walk(directory) {
    if (inside(directory)) return;
    for (const e of fs.readdirSync(directory, { withFileTypes: true })) {
      const full = path.join(directory, e.name);
      if (inside(full) || full.includes('/.ploinky/repos')) continue;
      if (e.isSymbolicLink()) {
        if (inside(path.resolve(directory, fs.readlinkSync(full)))) inbound.push(full);
      } else if (e.name === '.git') {
        if (e.isDirectory()) {
          const alt = path.join(full, 'objects/info/alternates');
          if (fs.existsSync(alt)) for (const line of fs.readFileSync(alt, 'utf8').trim().split('\n').filter(Boolean)) {
            if (inside(path.resolve(full, 'objects', line))) inbound.push(alt);
          }
        } else if (e.isFile()) {
          const data = fs.readFileSync(full, 'utf8').trim();
          if (data.startsWith('gitdir: ') && inside(path.resolve(directory, data.slice(8)))) inbound.push(full);
        }
      } else if (e.isDirectory()) walk(full);
    }
  }
  walk(workspace);
  assert.deepEqual(inbound, [], 'Surviving symlink or Git alternate consumer');
  return { checkedAt: new Date().toISOString(), openFiles: 0, processReferences: 0, inboundDependencies: 0 };
}

function validateArchiveMembers(file) {
  for (const member of run('/usr/bin/tar', ['-tzf', file]).split('\n')) {
    assert(member === '.' || member === './' || member.startsWith('./'));
    assert(!member.split('/').includes('..') && !member.startsWith('/'));
  }
}

function compareRetained(expected) {
  for (const root of roots) assert.deepEqual(inventory(path.join(workspace, root), true), expected[root], 'Retained evidence changed: ' + root);
}
const sizeKiB = paths => paths.reduce((sum, p) => sum + Number(run('/usr/bin/du', ['-sk', p]).split(/\s/)[0]), 0);
const measuredPaths = () => [...roots.map(p => path.join(workspace, p)), ...(fs.existsSync(path.join(workspace, 'container-image-builds/sources/ploinky')) ? [path.join(workspace, 'container-image-builds/sources/ploinky')] : []), ...(fs.existsSync(output) ? [output] : [])];

async function prepare() {
  assert(!fs.existsSync(output), 'Retention destination already exists');
  const activity = activityGate();
  const beforeKiB = sizeKiB(measuredPaths());
  const retained = Object.fromEntries(roots.map(root => [root, inventory(path.join(workspace, root), true)]));
  fs.mkdirSync(path.join(output, 'archives'), { recursive: true, mode: 0o700 });
  fs.mkdirSync(path.join(output, 'trees'), { mode: 0o700 });
  const entries = [], artifacts = new Map();
  for (const relative of allowlist) {
    const absolute = targetPath(relative), identity = fingerprint(absolute);
    const entry = { path: relative, identity, git: identity.type === 'directory' ? gitIdentity(absolute) : null, beforeKiB: sizeKiB([absolute]) };
    if (identity.type === 'directory') {
      const tree = inventory(absolute), contentSha = sha(json(tree));
      entry.contentSha256 = contentSha;
      entry.treeManifest = `trees/${contentSha}.json`;
      entry.archive = `archives/${contentSha}.tar.gz`;
      const archive = path.join(output, entry.archive);
      if (!fs.existsSync(archive)) {
        fs.writeFileSync(path.join(output, entry.treeManifest), json(tree), { flag: 'wx', mode: 0o600 });
        run('/usr/bin/tar', ['--exclude=./.git', '-czf', archive, '-C', absolute, '.']);
        validateArchiveMembers(archive);
        const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'snapshot-restore-'));
        try {
          run('/usr/bin/tar', ['-xzpf', archive, '-C', temporary]);
          assert.deepEqual(inventory(temporary), tree, 'Archive source restoration mismatch');
        } finally { fs.rmSync(temporary, { recursive: true }); }
        artifacts.set(entry.archive, { path: entry.archive, sha256: fileSha(archive), bytes: fs.statSync(archive).size });
      }
      assert.equal(sha(json(inventory(absolute))), contentSha, 'Source changed during archive');
    } else {
      entry.originalSha256 = fileSha(absolute);
      entry.originalBytes = fs.statSync(absolute).size;
      entry.archive = `archives/${entry.originalSha256}.payload.gz`;
      const archive = path.join(output, entry.archive);
      if (!fs.existsSync(archive)) {
        await pipeline(fs.createReadStream(absolute), createGzip({ level: 9 }), fs.createWriteStream(archive, { flags: 'wx', mode: 0o600 }));
        const bytes = gunzipSync(fs.readFileSync(archive));
        assert.equal(bytes.length, entry.originalBytes);
        assert.equal(sha(bytes), entry.originalSha256, 'Payload compression changed original bytes');
        artifacts.set(entry.archive, { path: entry.archive, sha256: fileSha(archive), bytes: fs.statSync(archive).size });
      }
    }
    entries.push(entry);
    console.log(JSON.stringify({ archived: relative, archive: entry.archive }));
  }
  compareRetained(retained);
  const record = { schema: 1, createdAt: new Date().toISOString(), workspace, preservation: 'Exact source bytes, file modes, symlinks, empty directories and original payload TAR bytes. Git history and clone metadata are intentionally omitted; HEAD/tree/commit/refs recorded. No source changes or task-result rewriting.', activity, beforeKiB, entries, artifacts: [...artifacts.values()], retained };
  fs.writeFileSync(path.join(output, 'manifest.json'), json(record), { flag: 'wx', mode: 0o600 });
  fs.writeFileSync(path.join(output, 'README.md'), `# Source snapshot retention\n\nThe selected old snapshots were compacted on 2026-10-11 at the user's request. All logs, test results, manifests, receipts, configurations, scripts and historical hashes stay in their original directories. Only the exact paths listed in manifest.json are eligible for removal.\n\nThe archives retain exact source file bytes, modes, symlinks and empty directories, and original candidate TAR payload bytes. Each unique tree was extracted in an isolated temporary directory and compared with its per-file manifest before removal. Git HEAD, tree, raw commit object and refs are recorded; obsolete clone metadata and Git history are not archived. Canonical repositories are unchanged. File timestamps are in the first archived copy, but are not part of tree deduplication; extended filesystem attributes are not retained.\n\n## Restore a source tree\n\nFind its entry in manifest.json. Verify the archive SHA256 against the artifacts list. Create an empty directory at the entry's original workspace-relative path, then run /usr/bin/tar -xzpf ARCHIVE -C EMPTY_DIRECTORY. This restores source data without Git metadata. To obtain a Git checkout, separately clone the canonical repository and check out the recorded HEAD, then compare the source tree.\n\n## Restore a candidate TAR\n\nFind its payload.gz mapping. Run gzip -dc ARCHIVE > ORIGINAL_TAR_PATH using an absent output path. Verify SHA256 and size against originalSha256 and originalBytes. Its bytes match the historical manifest pins exactly; recorded hashes have not been rewritten.\n\nThe old files contain historical absolute paths, including links to retired /private/tmp scratch. Source restoration preserves those links as recorded. Before executing a restored copy, repair dependency links only in that separate restored copy and repeat applicable runtime checks. Old authorization artifacts are historical evidence, not renewed authorization to deploy or run tests.\n\nThe local container-image-builds/sources/ploinky build input must be restored or checked out at the selected build SHA before a local image build. GitHub workflows perform their own source checkout.\n\nmanifest.json maps every removed original path to its recovery archive; deletion-receipt.json records actual removals and observed allocated-space reduction.\n`, { flag: 'wx' });
  console.log(JSON.stringify({ prepared: entries.length, uniqueArchives: artifacts.size, manifestSha256: fileSha(path.join(output, 'manifest.json')), beforeKiB, retentionKiB: sizeKiB([output]) }));
}

function remove(expectedSha) {
  assert.match(expectedSha ?? '', /^[0-9a-f]{64}$/);
  const manifestPath = path.join(output, 'manifest.json');
  assert.equal(fileSha(manifestPath), expectedSha, 'Reviewed manifest changed');
  assert(!fs.existsSync(path.join(output, 'deletion-receipt.json')), 'Cleanup already completed');
  const record = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  assert.deepEqual(record.entries.map(e => e.path), allowlist);
  for (const artifact of record.artifacts) assert.equal(fileSha(path.join(output, artifact.path)), artifact.sha256, 'Recovery archive changed');
  compareRetained(record.retained);
  const activity = activityGate();
  for (const e of record.entries) {
    const absolute = targetPath(e.path);
    assert.deepEqual(fingerprint(absolute), e.identity, 'Target identity changed');
    if (e.identity.type === 'directory') {
      assert.equal(sha(json(inventory(absolute))), e.contentSha256, 'Target contents changed');
      assert.deepEqual(gitIdentity(absolute), e.git, 'Git identity changed');
    } else assert.equal(fileSha(absolute), e.originalSha256, 'Payload changed');
  }
  const removed = [];
  const receiptPath = path.join(output, 'deletion-receipt.json');
  for (const e of record.entries) {
    const absolute = targetPath(e.path);
    assert.deepEqual(fingerprint(absolute), e.identity);
    fs.rmSync(absolute, { recursive: e.identity.type === 'directory', force: false });
    removed.push(e.path);
    fs.writeFileSync(receiptPath, json({ state: 'in-progress', manifestSha256: expectedSha, activity, removed }));
  }
  compareRetained(record.retained);
  for (const artifact of record.artifacts) assert.equal(fileSha(path.join(output, artifact.path)), artifact.sha256);
  const afterKiB = sizeKiB(measuredPaths());
  const result = { state: 'complete', completedAt: new Date().toISOString(), manifestSha256: expectedSha, activity, removed, beforeKiB: record.beforeKiB, afterKiB, freedKiB: record.beforeKiB - afterKiB, retainedEvidenceUnchanged: true, archivesUnchanged: true };
  fs.writeFileSync(receiptPath, json(result));
  console.log(json(result));
}

if (process.argv[2] === 'prepare') await prepare();
else if (process.argv[2] === 'delete') remove(process.argv[3]);
else throw new Error('Use prepare or delete with the reviewed manifest SHA256');
