Reviewer: codex-gpt-6
Date: 2026-09-28
Scope: independent C12 recheck against the revised private-copy contract
Repository: /home/research/dev/local-llms, branch local-llm-multiarch
Tested HEAD: d68c70fe097e932ac6593d0e690f124583e8a52d
Previous reviewed HEAD: d3c6a94aa12ea100ac936248f40f9c6fe3a51b95
Worktree: clean at initial and final source checks
Revision diff SHA256: 64a8d52ca346a4ced4acdbcac4509a83affff7d8a059d1d6e8ce87d8db93b48e
Plan: /home/research/work/plans/local-llm-multiarch-plan.md
Plan SHA256: 738778a029ef7dc88b384126e29bb07e3be2bb175f1cb0e391512eaa42d11e8d
Plan modified: 2026-09-28 20:20:28.470578426 +0200
Original review preserved: local-llm-workspace-reuse-review_codex.md, SHA256 accaf77bca9f304272bd1ee494a32c0aa1ad240c63e3c2415a0e1cfb91c3c4a9

## Verdict

**Substantial improvement, but C12 still needs fixes before acceptance.** I independently confirmed **310/310 repository tests passing**, with `--test-concurrency=1`. The revised design correctly isolates untrusted shared files through private copies and provides a working low-disk, canonical in-place adoption path. The original eight findings are **four resolved and four partially resolved** under that new contract. Additional small fixtures reproduced four major remaining defects and one minor cancellation gap, detailed below. None of the findings demands restoring hard links from `/shared` or backward compatibility.

The repository and plan remained at the recorded versions throughout the recheck. I read the revised C12 and §9 R1–R8 mapping, applicable guidance and updated DS002/DS003, reviewed the real diff, and tested a source-only snapshot of the immutable commit. No source, spec, plan, original report, container or real model file was changed. No model/GPU/build work was performed. Fixture files were at most 262,151 bytes, except the repository suite's existing small fixtures; tests used mocked runners and transfers.

## R1–R8 disposition

| Finding | Disposition | Verified improvement and remaining gap |
| --- | --- | --- |
| **R1: mutation recorded as trusted** | **Partial** | `hashBound` now reads an opened regular-file descriptor and compares before/after `fstat`; private copies hash the bytes written and reject changed shared sources. Tests 2/2b and my pathname-replacement/private-copy checks pass. **Ordinary download finalization still records a stat sampled after the streamed digest, and can persistently trust changed bytes: F4.** |
| **R2: symlinks and confinement** | **Partial** | Canonical-file links and links in ancestors below a fixed root are rejected. Descriptor/path matching prevents the original inner-directory swap. **The shared root itself can be swapped and then re-resolved as a new allowed root: F1. A file-to-FIFO race blocks before regular-file validation: F2.** |
| **R3: fresh HF snapshot ENOENT** | **Partial** | Fresh snapshots copied from `/shared` now create their final and state directories; repository case 1 genuinely starts without the final directory. **A new snapshot already placed at its canonical path still fails because in-place adoption does not create its separate state directory: F3.** |
| **R4: download-sized disk admission** | **Resolved under the revised contract** | Actual controller preview and Run accept a correct canonical file with less free disk than its size, use `bytesNeeded: 0` and transfer zero network bytes. Shared candidates require full private-copy space and low-space copies are rejected before reads. That is intentional, not the previous shared-hard-link behavior. A size-only acquisition plan is provisional; corrupt unrecorded own files are subsequently hashed, rejected and subjected to fallback space checks. |
| **R5: destroying resumable partials** | **Resolved** | Unique `.copy-*` staging preserves the existing `.partial` and identity until publication. Repository case 4 proves the 131,072-byte Range resume after wrong candidates and after a copy-read error or abort; the cases actually retain and inspect the original partial. |
| **R6: copy space/cancellation/errors** | **Partial** | Space preflight, chunked copying, explicit I/O errors, staging cleanup and ordinary copy/hash aborts are implemented. Controller Stop/Cancel/drain are exercised while copies are active. **Opening a candidate that became a FIFO cannot be cancelled (F2), and the controller does not pass cancellation to its initial acquisition walk (F5).** |
| **R7: provenance/progress** | **Resolved for the original defect** | One `{file,source,method,bytes}` shape now reaches fetch results, records, deployment results and logs. HF results aggregate it; no `from`/`source` mismatch remains. Copying and initial hashing have explicit progress phases. My equal-sized mixed split fixture returns in-place/copy/download provenance correctly. See the minor final-recheck progress observation below. |
| **R8: freed bytes** | **Resolved** | `freedBytes` groups device/inode and counts the inode only if the removed set contains all links. Case 11 reproduces both the last-two-links case (count once) and an external surviving link (count zero). DS002 now correctly defines logical bytes rather than exact physical disk reclamation. |

## Remaining findings

### F1 — Major: swapping `/shared/models` itself defeats the root-confinement check

**Where:** [workspaceReuse.mjs:62](/home/research/dev/local-llms/local-llm/src/controller/workspaceReuse.mjs:62), especially `realpath(root)` at 67; `walkShared` root check and open at 389–393 and 359; `openBound` at 86–110.

The root is checked as a directory before walking, but `boundPath` resolves that mutable pathname again when opening each candidate. If a shared writer replaces the root with a symlink between those operations, the outside target becomes the expected root. `/proc/self/fd` then agrees with that newly resolved outside path, so the check accepts it. The current regression swaps an inner subdirectory, which is caught; it never swaps the root being resolved.

**Reproduction and output:** the isolated `opendir` seam renames the checked shared root, replaces it with a symlink to a sibling fixture directory, and continues the real walk/open/copy logic. The sibling holds a correct pinned fixture.

```text
method=copy, resolved source=/tmp/c12-recheck-fixture-.../outside/m.gguf
CONFIRMED shared root swapped to symlink is accepted outside original root
```

There are zero mocked HTTP requests. This does not bypass the digest, but it **does** bypass the promised lookup boundary using only a directory writable under `/shared`. It is not an operator changing trusted `/data`.

**Fix:** anchor each untrusted root's resolved path and directory identity before lookup and retain that boundary through adoption. Do not allow a later `realpath(root)` to redefine it. Reject a substituted/symlinked root and fail closed if its identity cannot be established. If configured links are supported for trusted store roots, distinguish that policy from the untrusted `/shared/models` root. Add the root-swap reproduction alongside the inner-ancestor test.

### F2 — Major: a regular candidate replaced by a FIFO blocks before type validation and ignores abort

**Where:** [workspaceReuse.mjs:97](/home/research/dev/local-llms/local-llm/src/controller/workspaceReuse.mjs:97), then type validation at 104–107; [downloader.mjs:498](/home/research/dev/local-llms/local-llm/src/controller/downloader.mjs:498).

`openBound` opens with `O_RDONLY | O_NOFOLLOW` and only afterwards checks whether the descriptor is a regular file. `O_NOFOLLOW` prevents a final symlink; it does not make an ordinary FIFO open nonblocking. A writer in `/shared` can replace an enumerated regular file with a FIFO just before open. The awaited open never reaches `fstat`, the copy loop, or its cancellation checks.

**Reproduction:** a small child process runs the real `downloadArtifact` path. Its filesystem seam changes the discovered 32-byte regular candidate into a FIFO immediately before the real `open`. It requests abort 20 ms later. The child does not settle and is killed by the fixture's parent at its 600 ms deadline:

```text
FIFO swapped before open
Abort requested
CONFIRMED FIFO open still pending after abort; fixture child killed at 600 ms
```

Only that fixture-owned child was killed; no unrelated process was touched. No large or slow disk operation was used.

**Impact:** untrusted shared input can hang Run and subsequent Stop/Cancel/drain awaiting that job. Entry count and copy chunk limits do not bound this operation.

**Fix:** prevent opening special files in a way that can block before validation. For Linux, consider a nonblocking/no-follow descriptor opening strategy followed by `fstat` rejection before any read, while retaining descriptor/root binding. Keep cancellation checks around candidate opens and test FIFO/device/non-regular replacement. A pre-open `lstat` alone reintroduces a race and is insufficient.

### F3 — Major: first-time canonical in-place HF adoption still fails to create its metadata directory

**Where:** [downloader.mjs:469](/home/research/dev/local-llms/local-llm/src/controller/downloader.mjs:469), record write at 470; `snapshotFilePaths` assigns metadata to the separate `.state` tree. `useOwnFile` is called before any directory-creation branch at 875.

A retained HF snapshot may have all model files at `<data>/models/hf/<owner>/<repo>/<commit>/...` while `<data>/models/hf/.state/...` does not exist. Hashing the correct canonical file succeeds, but writing its adoption record fails. The shared-copy path uses `publishVerified` and creates that directory; the in-place path does not.

**Reproduction/output:** pre-place a SHA256-pinned `config.json` at its canonical snapshot path, with no state directory or record, and call the real `downloadSnapshotFile`:

```text
ENOENT: open '.../models/hf/.state/org/model/<commit>/config.json.json.tmp-...'
CONFIRMED fresh canonical HF in-place adoption cannot create its record directory
```

The fixture makes zero HTTP requests and does not create a verified record. This is the newly required zero-copy feature for snapshots, not a compatibility request. Both SHA256 and git-oid records use the same missing directory path.

**Fix:** securely create the metadata parent under the store root before writing a successful in-place record, preserving all ancestor checks. Add a canonical, unrecorded HF snapshot fixture without pre-created `.state`; include a mixed snapshot with one in-place, one copied and one downloaded file. Current case 1 tests fresh **copies**, and cases 6/7 test in-place **GGUF**, leaving this combination uncovered.

### F4 — Major: ordinary downloads still stamp changed bytes as the verified baseline

**Where:** [downloader.mjs:613](/home/research/dev/local-llms/local-llm/src/controller/downloader.mjs:613) writes and hashes incoming chunks; the written object's stat is sampled later at 796–798; `finalize` passes that stat to publication at 776–787. The unchanged-stat fast path is 447–448.

R1 is fixed for in-place hashing and shared copying. However, a download's digest is built from incoming buffers, then its trusted stat is taken after writing has finished. An accidental writer can alter an already-written byte before this stat sample; the digest remains the original transfer digest and the new stat becomes the trusted baseline. The new final prelaunch check skips hashing because that baseline matches.

**Reproduction:** after the final `downloading` progress chunk, overwrite one byte of the disposable `.partial` without changing length. This happens **before** completion/final verification, not after a final successful check. Then call the real `verifyArtifact`:

```text
download=complete; bytes mismatch=true; final verify rehashed=false
CONFIRMED download path can still cache bytes changed during transfer as verified
```

**Scope:** this involves an accidental change to the operator-trusted store. It is not presented as protection against a malicious operator, nor a demand for immutable timestamps. The defect is that the new code's verification record falsely says that the changed object was the one hashed, and later checks perpetuate the error. The revised contract explicitly promises detection during verification; only operator changes **after** the last check are excluded.

**Fix:** bind the published downloaded bytes to a stable verification result, not just the streamed digest plus a later stat. One simple correct option is a descriptor-bound stable hash of the final partial before publication; any faster alternative needs a demonstrated invariant that detects in-transfer changes. Preserve resumability and cancellation. Add this transfer-path race as well as the existing in-place/copy mutation tests. Apply equivalent stability reasoning to a resumed prefix.

### F5 — Minor: Stop cannot cancel acquisition planning, even after the current directory read finishes

**Where:** [deployments.mjs:391](/home/research/dev/local-llms/local-llm/src/controller/deployments.mjs:391) calls `store.plan(source,{index})` without a signal; Run executes it inside the serialized command queue before creating its job. Stop queues behind Run at 1123–1125. The store accepts `signal`, but receives none here (`weightStores.mjs:102–105`).

**Reproduction:** a small shared tree contains 20 empty subdirectories. Hold the first `opendir` at a test gate, call actual controller Stop, then release the read. Planning still opens **all 21 directories** before Stop can settle. This distinguishes the issue from merely waiting for one already-pending filesystem syscall:

```text
Stop requested before first entry, but planning still opens 21 directories before Stop settles
CONFIRMED Stop cannot abort the acquisition-planning directory walk
```

**Impact:** the new bounded streaming walk is cancellable at its helper API, but not during real controller admission planning. On a large/slow shared tree, Stop is delayed and planning continues needlessly. The 20,000-entry cap limits the number of operations, so this is a responsiveness gap rather than an unbounded CPU loop. Current case 13 passes a signal directly to the downloader and does not exercise this phase.

**Fix:** make planning part of an explicitly cancellable operation that Stop/Cancel/drain can signal before waiting behind the Run queue; pass that signal through acquisition and shared lookup. Keep the memory/GPU admission ordering. Add a real-controller planning cancellation test that checks no further directory traversal after the current operation returns.

## Tests, evidence and coverage limits

An immutable source-only `git archive` of `d68c70f` was extracted to `/tmp/c12-recheck-5qmxlyfq` (1,187,840 bytes; archive SHA256 `d6947473739ca60a6ed61289117d6df617137c1d346c3331edf52e1cda2c18a4`). All execution used that snapshot, not the working checkout.

### Repository suite

Command, run once:

```sh
node --test --test-concurrency=1 'local-llm/tests/*.test.mjs'
```

Exact summary:

```text
tests 310
suites 7
pass 310
fail 0
cancelled 0
skipped 0
todo 0
duration_ms 15610.563672
```

I read the 15 C12 tests. They meaningfully cover the principal revised contracts: copied files have different inodes; shared-source and in-place mutations fail/retry; regular symlinks and inner-ancestor swaps are refused; partial offsets survive faults; a real controller rejects undersized copy budgets and accepts in-place low-disk Run; Stop/Cancel/drain settle during bounded copies; provenance is asserted; inode accounting has external-link controls. The suite is not merely changing expectations to call the old implementation correct.

However, the claimed 14-case coverage is not exhaustive:

- Root substitution is absent; only an inner subdirectory is swapped.
- Fresh shared-copy HF and in-place GGUF are covered separately; canonical in-place HF is missing.
- Mutations cover in-place hashing and shared copying, not incoming download finalization.
- The split mixed-source test intentionally uses distinct sizes. That is a useful positive case, but not sufficient coverage of equal-sized decoys/shards.
- Case 14 calls `verifyArtifact` directly; it does not prove controller placement of the last check. I tested that placement separately.
- Controller cancellation covers a running copy, and direct hashing is covered, but initial planning and blocking special-file opens are absent.
- Final prelaunch rehash happens after the controller sets `starting`. `updateProgress` only changes phase when the current phase is already a transfer phase, so that final hash remains displayed as starting. This is a minor display limitation; cancellation accepts starting and the integrity check does run.

### Independent fixture checks

I ran two preserved small scripts, sequentially:

```sh
node /tmp/c12-recheck-5qmxlyfq/probes_codex.mjs
node /tmp/c12-recheck-5qmxlyfq/fifo_probe_codex.mjs
```

The final general script has ten cases: four remaining defects (F1, F3, F4, F5) and six positive desired-behavior checks. The FIFO script independently confirms F2. General-script iterations were rerun only as cases were added; the completed repository suite was not repeated.

Positive checks beyond the repository assertions:

| Check | Observed result |
| --- | --- |
| Correct canonical GGUF with low free disk, through preview and actual controller Run | Preview `ok`, `bytesNeeded=0`, Run reaches ready, zero mocked network requests. |
| Corrupt same-sized **unrecorded** canonical file, with zero copy/download space | Refused with `INSUFFICIENT_SPACE`, no verified metadata, original fixture retained. With space available, it is downloaded/replaced and final digest matches. |
| Shared source modified after successful copy | Private store inode differs and its digest stays correct; verify succeeds. |
| Shared source pathname replaced during copying | Stable-object checks reject the changed candidate; fallback download yields correct bytes. |
| Three **equal-sized**, mixed-source split shards, including a same-name wrong-digest decoy and bad downloaded final shard | First attempt is refused with `SHA256_MISMATCH`, set remains partial. Corrected retry completes with in-place/copy/download provenance; every shard's digest is independently checked. |
| Real controller artifact changed after fetch and before runner start | Final check changes deployment to error; fake runner launches remain zero. |

All network transfer functions and inference runners were mocked. Scripts and reproduction outputs are preserved in this report's appendices so the evidence does not depend on `/tmp` retention. Some assertions intentionally confirm a defect; convert those to the desired rejection/success/cancellation behavior for repository regressions.

## Timing and the measurement lock

The coordinator introduced `/home/research/phase0/.memlock` **after all recheck test processes had finished**. No tests were repeated for that update. No test was run under a shared lock. Any future execution or reproduction must acquire the **exclusive** lock first, for example:

```sh
flock -x /home/research/phase0/.memlock node --test --test-concurrency=1 'local-llm/tests/*.test.mjs'
flock -x /home/research/phase0/.memlock node /tmp/c12-recheck-5qmxlyfq/probes_codex.mjs
flock -x /home/research/phase0/.memlock node /tmp/c12-recheck-5qmxlyfq/fifo_probe_codex.mjs
```

Earlier execution was not timestamp-instrumented per command. For correlating the host measurements, these are **conservative recoverable local-time bounds**, not invented exact start times (Europe/Rome, UTC+02):

- Snapshot creation: **2026-09-28 20:42:16.463**. The single full suite ran afterwards and finished before the general fixture script was created at **20:44:20.367**; its recorded duration was **15.611 seconds**.
- General-script iterations ran between **20:44:20.367 and 20:48:02 approximately**. The final version was written at **20:48:01.756**, then immediately executed; its tool result completed successfully. Five evolving-script invocations appear in this review's command transcript, each using only the small fixtures described above.
- FIFO fixture was created at **20:44:57.235** and executed immediately afterwards. Its own timeout was **600 ms**, after which it killed only its own child.
- At **20:48:19.529**, a read-only process check found no remaining recheck or full-suite test process. The matching `ps` output consisted only of that diagnostic shell and `rg`.

The final report writing and source/hash checks are read-only or small document writes and do not start tests. These tests can still contribute small CPU/filesystem/cache activity; I make no claim that their intervals were measurement-clean.

## Recommended next step

Fix F1–F4 and address F5's cancellation plumbing, add the uncovered combinations above, and rerun the targeted tests under the exclusive measurement lock. Preserve the agreed private-copy trust model and real model retention. Then recheck the exact fixes before using C12 as evidence for Spark acceptance. The reviewed commit's positive results can be retained as evidence for the unchanged paths; they do not settle the remaining failures.

## Appendix A — general reproduction/desired-behavior script

Save at the root of an isolated source snapshot of the recorded commit, then run it only while holding the exclusive measurement lock. It creates and removes only its own `c12-recheck-fixture-*` directories.

```js
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import crypto from 'node:crypto'; import assert from 'node:assert/strict';
import {downloadArtifact, downloadSnapshotFile, snapshotPaths, artifactPaths, verifyArtifact, inspectArtifact, removeArtifact} from './local-llm/src/controller/downloader.mjs';
import {createWeightStores} from './local-llm/src/controller/weightStores.mjs';
import {createController} from './local-llm/src/controller/deployments.mjs';
import {validateModel} from './local-llm/src/controller/catalog.mjs';
const payload=Buffer.alloc(262151,65),hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const a={repo:'org/model',commit:'c'.repeat(40),file:'m.gguf',size:payload.length,sha256:hash(payload)};
function setup(){const base=fs.mkdtempSync(path.join(os.tmpdir(),'c12-recheck-fixture-')),data=path.join(base,'data'),root=path.join(data,'models','gguf'),shared=path.join(base,'shared','models');fs.mkdirSync(shared,{recursive:true});const requests=[];const fetchImpl=async(u,o)=>{requests.push(new Headers(o?.headers).get('range'));return new Response(payload,{headers:{'content-length':String(payload.length)}})};return {base,data,root,shared,requests,fetchImpl,paths:artifactPaths({root,artifact:a}),get(extra={}){return downloadArtifact({root,artifact:a,adoptFrom:[shared],fetchImpl,baseUrl:'http://mock.invalid',sleep:async()=>{},...extra})}};}
async function run(name,fn){const s=setup();try{await fn(s);console.log('CONFIRMED',name);}finally{fs.rmSync(s.base,{recursive:true,force:true})}}
await run('fresh canonical HF in-place adoption cannot create its record directory',async s=>{
 const root=path.join(s.data,'models','hf'),art={...a,file:'config.json'},p=snapshotPaths({root,repo:a.repo,commit:a.commit});fs.mkdirSync(p.dir,{recursive:true});fs.writeFileSync(path.join(p.dir,art.file),payload);
 let err;try{await downloadSnapshotFile({root,artifact:art,fetchImpl:s.fetchImpl})}catch(e){err=e}assert.equal(err?.code,'ENOENT');assert.match(err.message,/\.state/);assert.equal(s.requests.length,0);console.log('  '+err.message);
});
await run('shared root swapped to symlink is accepted outside original root',async s=>{
 const out=path.join(s.base,'outside');fs.mkdirSync(out);fs.writeFileSync(path.join(out,a.file),payload);let moved=false;
 const fsApi={...fs,promises:{...fs.promises,opendir:async(p,o)=>{if(p===s.shared&&!moved){moved=true;fs.renameSync(s.shared,s.shared+'-old');fs.symlinkSync(out,s.shared)}return fs.promises.opendir(p,o)}}};
 const result=await s.get({fsApi});assert.equal(result.provenance.method,'copy');assert.ok(fs.realpathSync(result.provenance.source).startsWith(out));assert.equal(s.requests.length,0);console.log('  method='+result.provenance.method+', resolved source='+fs.realpathSync(result.provenance.source));
});
await run('same-size bad canonical file fails closed with no disk; retained until replacement',async s=>{
 fs.mkdirSync(path.dirname(s.paths.file),{recursive:true});const wrong=Buffer.from(payload);wrong[0]=66;fs.writeFileSync(s.paths.file,wrong);
 await assert.rejects(s.get({adoptFrom:[],statfs:async()=>({bavail:0,bsize:4096})}),e=>e.code==='INSUFFICIENT_SPACE');assert.equal(fs.existsSync(s.paths.meta),false);assert.equal(hash(fs.readFileSync(s.paths.file)),hash(wrong));assert.equal(s.requests.length,0);
 const result=await s.get({adoptFrom:[]});assert.equal(result.provenance.method,'download');assert.equal(hash(fs.readFileSync(s.paths.file)),a.sha256);
});
await run('private copy remains correct after shared source is changed',async s=>{
 const source=path.join(s.shared,a.file);fs.writeFileSync(source,payload);await s.get();fs.writeFileSync(source,Buffer.alloc(payload.length,66));assert.notEqual(fs.statSync(source).ino,fs.statSync(s.paths.file).ino);assert.equal(hash(fs.readFileSync(s.paths.file)),a.sha256);await verifyArtifact({root:s.root,artifact:a});
});
await run('source pathname replacement during copying cannot substitute different bytes',async s=>{
 const source=path.join(s.shared,a.file);fs.writeFileSync(source,payload);let moved=false;
 const r=await s.get({chunkBytes:4096,progressIntervalMs:0,onProgress:p=>{if(!moved&&p.phase==='copying'){moved=true;fs.renameSync(source,source+'.old');fs.writeFileSync(source,Buffer.alloc(payload.length,66))}}});
 assert.equal(hash(fs.readFileSync(s.paths.file)),a.sha256);assert.ok(['copy','download'].includes(r.provenance.method));console.log('  result method='+r.provenance.method);
});
await run('download path can still cache bytes changed during transfer as verified',async s=>{
 let changed=false;
 const r=await s.get({adoptFrom:[],progressIntervalMs:0,onProgress:p=>{if(p.phase==='downloading'&&p.bytes===a.size&&!changed){changed=true;const fd=fs.openSync(s.paths.partial,'r+');fs.writeSync(fd,Buffer.from('B'),0,1,0);fs.closeSync(fd)}}});
 assert.equal(r.status,'complete');assert.notEqual(hash(fs.readFileSync(s.paths.file)),a.sha256);const check=await verifyArtifact({root:s.root,artifact:a});assert.equal(check.reverified,false);assert.equal(s.requests.length,1);console.log('  download=complete; bytes mismatch=true; final verify rehashed='+check.reverified);
});
await run('equal-size mixed split shards require each pinned digest',async s=>{
 const blobs=[Buffer.alloc(65536,65),Buffer.alloc(65536,66),Buffer.alloc(65536,67)],names=['m-00001-of-00003.gguf','m-00002-of-00003.gguf','m-00003-of-00003.gguf'];
 const source={type:'huggingface',repo:'org/split',commit:a.commit,file:names[0],size:3*65536,shards:names.map((file,i)=>({file,size:65536,sha256:hash(blobs[i])}))};
 const first=artifactPaths({root:s.root,artifact:{...source,shards:undefined,file:names[0],size:65536,sha256:hash(blobs[0])}});fs.mkdirSync(path.dirname(first.file),{recursive:true});fs.writeFileSync(first.file,blobs[0]);
 fs.writeFileSync(path.join(s.shared,names[1]),blobs[0]);fs.writeFileSync(path.join(s.shared,'valid-second.bin'),blobs[1]);
 let badThird=true;const fetched=[];const store=createWeightStores({dataDir:s.data,env:{},sharedModelsRoot:s.shared,inspect:inspectArtifact,remove:removeArtifact,download:opts=>downloadArtifact({...opts,chunkBytes:4096,fetchImpl:async u=>{const name=String(u).split('/').pop();fetched.push(name);const bytes=badThird?blobs[0]:blobs[2];return new Response(bytes,{headers:{'content-length':String(bytes.length)}})}})}).huggingface;
 await assert.rejects(store.fetch({artifact:source}),e=>e.code==='SHA256_MISMATCH');assert.equal((await store.state(source)).state,'partial');badThird=false;const r=await store.fetch({artifact:source});assert.equal((await store.state(source)).state,'complete');assert.deepEqual(r.provenance.map(x=>x.method),['in-place','copy','download']);
 for(let i=0;i<3;i++)assert.equal(hash(fs.readFileSync(path.join(path.dirname(first.file),names[i]))),hash(blobs[i]));console.log('  bad third shard => partial; corrected retry => complete; methods='+r.provenance.map(x=>x.method));
});
function controllerFor(s,extra={}){const G=1024**3,model=validateModel({id:'tiny',displayName:'Tiny',sources:{gguf:{...a,type:'huggingface'}}},{seed:true});return createController({dataDir:s.data,env:{PATH:'/usr/bin'},seedCatalog:[model],sharedModelsRoot:s.shared,fileExists:()=>true,detectRunner:r=>({installed:true,version:r.pinnedVersion}),verify:verifyArtifact,download:opts=>downloadArtifact({...opts,fetchImpl:s.fetchImpl,sleep:async()=>{},chunkBytes:4096}),snapshot:async()=>({gpu:{available:true,name:'Fixture GPU',totalBytes:100*G,freeBytes:100*G,memoryModel:'dedicated'},memory:{totalBytes:100*G,availableBytes:100*G},disk:{freeBytes:100*G,totalBytes:200*G}}),dropCache:()=>true,...extra});}
await run('controller final recheck refuses an artifact changed after fetch before launch',async s=>{
 let launches=0;const c=controllerFor(s,{dropCache:file=>{const fd=fs.openSync(file,'r+');fs.writeSync(fd,Buffer.from('B'),0,1,0);fs.closeSync(fd);return true},startRunner:()=>{launches++;throw Error('must not launch')}});
 await c.run({requestId:'recheck-final-0001',modelId:'tiny',runnerId:'llama.cpp'});for(let i=0;i<400&&c.state.deployment.phase!=='error';i++)await new Promise(r=>setTimeout(r,5));assert.equal(c.state.deployment.phase,'error');assert.match(c.state.deployment.error,/no longer the verified/);assert.equal(launches,0);await c.stop();console.log('  final check error; runner launches='+launches);
});
await run('Stop cannot abort the acquisition-planning directory walk',async s=>{
 for(let i=0;i<20;i++)fs.mkdirSync(path.join(s.shared,'d'+i));
 const original=fs.promises.opendir;let opened=0;let release,entered;const gate=new Promise(r=>release=r),start=new Promise(r=>entered=r);let held=false,stopped=false;
 fs.promises.opendir=async(p,o)=>{opened++;if(p===s.shared&&!held){held=true;entered();await gate}return original(p,o)};
 const c=controllerFor(s,{download:async()=>{throw Error('fixture stops before a real download')},startRunner:()=>{throw Error('unused')}});
 try{const running=c.run({requestId:'recheck-plan-stop',modelId:'tiny',runnerId:'llama.cpp'}).catch(e=>e);await start;const stopping=c.stop().then(r=>{stopped=true;return r});await new Promise(r=>setTimeout(r,30));assert.equal(stopped,false);release();await running;await stopping;assert.equal(opened,21);console.log('  Stop requested before first entry, but planning still opens '+opened+' directories before Stop settles');}finally{release();fs.promises.opendir=original;await c.stop().catch(()=>{})}
});
await run('low-disk canonical adoption agrees across overview preview and actual Run',async s=>{
 fs.mkdirSync(path.dirname(s.paths.file),{recursive:true});fs.writeFileSync(s.paths.file,payload);let launched=0;const G=1024**3;
 const c=controllerFor(s,{snapshot:async()=>({gpu:{available:true,name:'Fixture',totalBytes:100*G,freeBytes:100*G,memoryModel:'dedicated'},memory:{totalBytes:100*G,availableBytes:100*G},disk:{freeBytes:payload.length/2,totalBytes:100*G}}),fetchImpl:async()=>({ok:true,status:200,json:async()=>({})}),startRunner:()=>{launched++;let end;const exited=new Promise(r=>end=r);const h={pid:4321,running:true,exited,stop:async()=>{h.running=false;end({code:0});return exited}};return h}});
 const ov=await c.overview({preview:{modelId:'tiny',runnerId:'llama.cpp'}});assert.equal(ov.preview.admission.status,'ok');assert.equal(ov.preview.acquisition.bytesNeeded,0);const accepted=await c.run({requestId:'recheck-lowdisk-ok',modelId:'tiny',runnerId:'llama.cpp'});assert.equal(accepted.accepted,true);
 for(let i=0;i<400&&c.state.deployment.phase!=='ready';i++)await new Promise(r=>setTimeout(r,5));assert.equal(c.state.deployment.phase,'ready');assert.equal(s.requests.length,0);assert.equal(launched,1);await c.stop();console.log('  preview=ok, bytesNeeded=0, Run=ready, network requests=0');
});
```

## Appendix B — bounded FIFO-race fixture

This starts one fixture-owned child and kills only that child at its deadline. The parent removes only the temporary directory it created. Run under the same exclusive lock.

```js
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import crypto from 'node:crypto';import {spawn,execFileSync} from 'node:child_process';import assert from 'node:assert/strict';
import {downloadArtifact} from './local-llm/src/controller/downloader.mjs';
if(process.argv[2]==='child'){
 const base=process.argv[3],shared=path.join(base,'shared'),src=path.join(shared,'m.gguf'),bytes=Buffer.alloc(32,65),signal=new AbortController();let swapped=false;
 const fsApi={...fs,promises:{...fs.promises,open:async(p,flags,mode)=>{if(p===src&&!swapped){swapped=true;fs.unlinkSync(src);execFileSync('mkfifo',[src]);process.stdout.write('FIFO swapped before open\n');setTimeout(()=>{signal.abort();process.stdout.write('Abort requested\n')},20)}return fs.promises.open(p,flags,mode)}}};
 await downloadArtifact({root:path.join(base,'data'),artifact:{repo:'o/m',file:'m.gguf',commit:'c'.repeat(40),size:32,sha256:crypto.createHash('sha256').update(bytes).digest('hex')},adoptFrom:[shared],fsApi,signal:signal.signal,fetchImpl:()=>{throw Error('network unused')}}).then(()=>console.log('SETTLED success'),e=>console.log('SETTLED '+e.code));
}else{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'c12-fifo-fixture-'));fs.mkdirSync(path.join(base,'shared'));fs.writeFileSync(path.join(base,'shared','m.gguf'),Buffer.alloc(32,65));
 const child=spawn(process.execPath,[import.meta.filename,'child',base],{stdio:['ignore','pipe','pipe']});let output='';child.stdout.on('data',x=>{output+=x});child.stderr.on('data',x=>{output+=x});
 await new Promise(r=>setTimeout(r,600));child.kill('SIGKILL');await new Promise(r=>child.on('exit',r));fs.rmSync(base,{recursive:true,force:true});
 console.log(output.trim());assert.match(output,/Abort requested/);assert.doesNotMatch(output,/SETTLED/);console.log('CONFIRMED FIFO open still pending after abort; fixture child killed at 600 ms');
}
```
