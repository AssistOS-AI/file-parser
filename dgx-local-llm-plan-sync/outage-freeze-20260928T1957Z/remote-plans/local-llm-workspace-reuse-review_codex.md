Reviewer: codex-gpt-6
Date: 2026-09-28
Scope: targeted C12 workspace-model reuse review; plan and implementation, read-only
Plan: /home/research/work/plans/local-llm-multiarch-plan.md
Plan SHA256: 714b391ffb76237fcb7db79d13051c0c7869e0cd9714770c98be992391bb6be4
Plan modified: 2026-09-28 19:56:51.300109126 +0200
Implementation: /home/research/dev/local-llms, branch local-llm-multiarch
Reviewed HEAD: d3c6a94aa12ea100ac936248f40f9c6fe3a51b95
C12 baseline: 8af8ae8e7c324dfdf48d12ff5333d5be8c8468dc
Worktree: clean at the start and on repeated checks through report preparation
C12 binary diff SHA256: 08577763e16d6a2df74abe4c804908274dc4bb4d17106159200b27ae9ac34d3c

## Verdict

C12 has the right intended scope and works for an ordinary, stable GGUF file in the shared directory, but **this implementation is not ready for acceptance**. I confirmed six major defects involving verification, symlinks, fresh HF snapshots, disk admission, resumable partials and copy handling, plus two minor reporting/accounting defects. The existing targeted tests all pass because they primarily exercise downloader-level happy paths, rather than the complete controller and multi-file lifecycle. Fix R1–R6 before relying on this for candidate acceptance. No backward-compatibility requirement was applied.

I reviewed the actual development checkout, its CLAUDE.md/AGENTS.md, DS006, the specification matrix, current DS002 and related lifecycle/security code, C12 and §9 decisions 6–7, and the implementation log. The C12 change was already committed and clean when I began. I tested a 1.1 MB `git archive` snapshot of that exact commit at `/tmp/c12-review-ywenp317`; none of the developer's source files were edited. The plan hash and HEAD stayed unchanged during the review.

**Host isolation:** no GPU use, builds, package/model downloads, container operations, or access to real model contents. The reproduction payload is 262,151 bytes. All test-created model-shaped files lived in disposable `/tmp/c12-fixture-*` directories and were removed by their fixtures. Existing downloaded models were neither read nor deleted.

## Confirmed findings

### R1 — Major: bytes changed during verification can be recorded as permanently trusted

**Evidence:** [downloader.mjs:399](/home/research/dev/local-llms/local-llm/src/controller/downloader.mjs:399), publication at 404–410, `recordStat` at 416–420, and the reuse fast path at 825–834.

The hash is calculated first, but the trusted device/inode/size/mtime/ctime is sampled later. There is no before/after identity check around hashing, and no association with a held descriptor for the file that was actually hashed. A shared writer can alter bytes already read by the hash; the code then records the **changed** file's metadata alongside the **old** successful digest. Future runs see matching metadata and skip hashing indefinitely.

**Reproduction:** put the pinned 262,151-byte fixture in the shared directory. In the existing `onProgress` test seam, after the final hashing chunk, overwrite its first byte without changing its size. This simulates a writer running between the hash and final publication. Adoption returns `status: complete`, the actual file's SHA256 is wrong, and a second call returns complete with `reverified` absent and zero downloads. This is more than the unavoidable instant between a final check and opening a model: the corrupted state becomes the persistent trusted baseline.

**Impact:** the asserted pinned identity can be false on this and every later Run, defeating C12's reason for revalidation.

**Remediation:** bind verification to a regular-file descriptor and verify stable identity/size/timestamps before and after reading. Reject or retry on changes; do not stamp an arbitrary later path state as the state just hashed. Account explicitly for the ctime change caused by the implementation's own rename. Apply the same rule to revalidation and downloaded-file finalization, since all use `recordStat`. Add the deterministic during-hash and publication-window races to tests. For protection against writers after verification, also resolve the trust/snapshot question under “Design boundaries” below.

### R2 — Major: symlinks can bypass confinement and defeat subsequent revalidation

**Evidence:** [downloader.mjs:292](/home/research/dev/local-llms/local-llm/src/controller/downloader.mjs:292) uses `stat`, following symlinks; 315–317 records `lstat` values without requiring a regular file; 823–834 hashes through the path and then caches those values. Shared traversal at 339–351 trusts directory entries across later pathname operations.

Two isolated reproductions confirm distinct paths through this problem:

1. Adopt a correct file, replace the agent-store pathname with a symlink to a correct file outside the allowed model roots, then run again. It is rehashed and accepted while remaining a symlink. Modify the target, retaining its length. The next call trusts the **unchanged symlink's** stat and returns corrupted bytes without revalidation.
2. Return a directory entry from `readdir`, then replace that directory with a symlink before recursion. The walker follows it, adopts a correctly hashed file outside the shared root and reports success. The current test with symlinks already present before enumeration does not cover this.

**Impact:** the plan's “regular files only; no symlinks; nothing outside those roots” rule is not implemented for the agent store or concurrent traversal. Even benign link substitution can disable the intended changed-file check.

**Remediation:** require regular files throughout both lookup paths. Open and validate candidates without following links and keep verification/adoption bound to that opened object. Protect resolution of ancestor directories as well as the final component; checking only `lstat` of the leaf is insufficient. Do not use a symlink inode's stat to authenticate its target. Add own-store symlinks, ancestor swaps and copy-fallback swaps to the negative tests.

### R3 — Major: adopting the first file of a new HF snapshot fails with ENOENT

**Evidence:** [downloader.mjs:380](/home/research/dev/local-llms/local-llm/src/controller/downloader.mjs:380) creates only the partial's parent; rename at 409 targets `paths.file`. [snapshotFilePaths:993](/home/research/dev/local-llms/local-llm/src/controller/downloader.mjs:993) deliberately places partials under `hf/.state/<repo>/<commit>` and final files under `hf/<repo>/<commit>`. Creation of the latter at 848 occurs only after the adoption branch has returned.

**Reproduction:** use an empty HF store and place a correct pinned `config.json` fixture in the shared directory. Call `downloadSnapshotFile` with `adoptFrom`. Hash verification succeeds, then rename fails:

```text
ENOENT: rename '.../hf/.state/org/model/<commit>/config.json.partial'
            -> '.../hf/org/model/<commit>/config.json'
```

**Impact:** the stated snapshot reuse feature fails on its natural first-use case, despite a fully available matching file. A snapshot whose final directory already exists happens to avoid the failure.

**Remediation:** securely create both destination and staging parents before adoption, without weakening R2's confinement checks. Test a complete fresh snapshot with both git-oid metadata files and SHA256/LFS weights, a partially present snapshot, and mixed adopted/downloaded files. Do not pre-create the final directory in the principal acceptance test.

### R4 — Major: Run requires full download space before discovering reusable hard links

**Evidence:** [deployments.mjs:1039](/home/research/dev/local-llms/local-llm/src/controller/deployments.mjs:1039) computes remaining bytes from `weightsState` and refuses admission at 1044–1045; shared discovery is reached only in the later `store.fetch`. Preview and overview make the same assumption at 419–426 and 472–485. The store's state functions inspect only canonical local paths, not shared candidates.

**Reproduction:** put a matching fixture in the shared directory on the same mount as the store. Give the real controller otherwise ample GPU/RAM and a disk snapshot with half the fixture size free. The actual `controller.run` returns `admission_insufficient_now`; the download/adoption function is called zero times. A hard link plus small bookkeeping would fit, but the feature is never attempted.

**Impact:** reuse is refused in precisely the low-disk situation where avoiding a second model allocation matters. The UI can refuse Run before the user can obtain the benefit. Successful direct `downloadArtifact` tests miss this integration failure.

**Remediation:** plan artifact acquisition before making the disk part of admission final: distinguish already-owned files, verified linkable candidates, files requiring copies, and missing bytes requiring downloads. Keep normal hardware/memory refusal before expensive acquisition. Revalidate candidates before use and check space for the actual copy/download/staging requirement, not blindly zero or the entire model. Make Run and its previews agree, and add a real-controller low-disk reuse test. See the mount caveat below: do not assume every shared candidate is linkable.

### R5 — Major: trying a wrong shared candidate destroys an existing resumable download

**Evidence:** [downloader.mjs:379](/home/research/dev/local-llms/local-llm/src/controller/downloader.mjs:379) calls `removePartial` before a candidate has been hashed; the candidate then occupies the normal `.partial` pathname. Hash mismatch at 400–402 removes it again, and fallback resumes from the now-empty store.

**Reproduction:** create a correct 131,072-byte prefix and matching identity sidecar for the 262,151-byte artifact. Place a same-sized, wrong-hash file in the shared directory. Invoke download. The first mocked HTTP request has **no Range header**: the valid prefix was deleted. A valid candidate whose adoption is cancelled can similarly displace valuable progress.

**Impact:** merely having an unrelated same-sized model in the shared directory causes an unnecessary full re-download, directly undermining the feature's purpose and existing resume contract. With real models this can discard gigabytes of valid progress.

**Remediation:** use an independent, unique adoption staging path. Retain the previous partial and its identity until a fully verified replacement is ready to publish. On a mismatch, copy/link failure or cancellation, discard only that candidate's staging file and resume the original prefix. Test the Range offset after all these outcomes.

### R6 — Major: copy fallback bypasses disk protection and cannot be promptly cancelled

**Evidence:** [downloader.mjs:382](/home/research/dev/local-llms/local-llm/src/controller/downloader.mjs:382) falls back from every link exception to one awaited `copyFile`; that call has no cancellation or progress mechanism, performs no free-space check, and swallows all copy errors. `assertFreeSpace` is only reached at 847 after adoption has failed. [deployments.mjs:979](/home/research/dev/local-llms/local-llm/src/controller/deployments.mjs:979) aborts and then awaits the same job, so Stop/Cancel cannot complete while copying is outstanding.

**Reproductions:**

- Force link to return EXDEV and inject a `statfs` result of zero available bytes. Adoption returns a successful copy and the space-check seam is called **zero times**. Only the tiny fixture was actually copied; this was not a disk-filling experiment.
- Hold the copy operation on a test promise, abort the signal, and observe that the operation remains unsettled. It ends with `ABORTED` only after the copy is released. No real slow/large file was needed.

**Impact:** a copy can consume the space that the download path would preserve and can hold controller Stop/Cancel/drain through a long I/O operation. A copy-space or permission failure is hidden as a candidate miss and may trigger an unnecessary network attempt.

**Remediation:** identify expected link-fallback errors, revalidate the source, and preflight the copy's actual space requirement and reserve. Copy in abortable bounded chunks (or use a managed, cancellable helper), report copying/verifying progress and clean only its own staging file. Propagate meaningful ENOSPC, cancellation and filesystem errors rather than silently treating them as a nonexistent model. Test these paths with injected faults; no large production model is needed.

### R7 — Minor: adoption provenance is missing or printed as undefined

**Evidence:** [downloader.mjs:411](/home/research/dev/local-llms/local-llm/src/controller/downloader.mjs:411) returns `{source, method}`; [weightStores.mjs:103](/home/research/dev/local-llms/local-llm/src/controller/weightStores.mjs:103) preserves that field; [deployments.mjs:869](/home/research/dev/local-llms/local-llm/src/controller/deployments.mjs:869) prints `entry.from`. The HF store ignores `result.adopted` entirely and returns no provenance at 267–287.

**Reproduction:** real GGUF store adoption formats the controller message as `adopted model.gguf from undefined (link, verified)`. Pre-create a snapshot directory to get past R3, successfully adopt its fixture and inspect the returned object: `bytesTransferred: 0`, `adopted: undefined`.

**Impact:** DS002's promise that the deployment log names every adopted file and method is false, and acceptance evidence cannot reliably show which workspace files were reused.

**Remediation:** use one provenance shape throughout, aggregate it for every snapshot file and split shard, and test the controller's actual log output, including mixed adoption/download. Make verification a visible phase during hashing; current adoption reports ordinary download progress until the final byte and never reports copy progress.

### R8 — Minor: snapshot deletion can report zero although it removes the inode's last links

**Evidence:** [weightStores.mjs:229](/home/research/dev/local-llms/local-llm/src/controller/weightStores.mjs:229) sums only files whose current `nlink <= 1`, **before** recursively removing the whole snapshot at 293–295.

**Reproduction:** make two files inside one test snapshot hard links to the same 262,151-byte inode, with no external link. Delete that snapshot through its real store API. Both links are removed, yet `freedBytes` is zero. This topology can arise if identical pinned files were adopted from one shared inode and the operator later removed the shared pathname.

**Impact:** disk accounting understates freed content when all remaining links lie inside the deletion set. The new GGUF per-file removal does not have this particular pre-scan problem.

**Remediation:** count distinct `(device,inode)` identities and how many links the deletion set removes, or account during sequential unlinking. Do not count an inode while an external link remains. Decide whether `freedBytes` means logical content bytes or physical reclaimed blocks; the current use of `size` cannot promise exact physical space for sparse/reflinked files or files held open. Add both retained-external-link and last-internal-links tests.

## Design boundaries and plan/spec mismatches

These are not additional confirmed defects in the eight-item count:

- **Same filesystem is insufficient for a hard link in the container.** C12 says same filesystem → link. Linux returns EXDEV across different mounts even if they expose the same filesystem ([Linux link(2), EXDEV](https://man7.org/linux/man-pages/man2/link.2.html)). Ploinky separately binds the shared directory to `/shared`, while this agent declares its model store under `/data`. Therefore the normal deployed path may take the copy fallback even when a host-side operator could hard-link those same files. This is an inference from the mounts, not a container experiment. Correct the wording to “when link succeeds,” and measure link-versus-copy and peak disk in the authorized nested acceptance fixture. No Ploinky architectural change is needed merely to avoid a network download.
- **The model store is writable shared state, not immutable evidence.** R1 fixes a concrete verification bug, but stat polling cannot prevent an external write immediately after verification or while a runner reads an adopted hard link. Define whether writers are cooperative and must not alter in-use models. If the requirement is immutable bytes against concurrent writers, use an isolated verified copy/reflink or a stronger storage/snapshot mechanism; hard-linking and checking timestamps cannot provide that guarantee. Likewise, sidecar metadata stored under workspace-writable `/data` is a cache, not authentication against a writer who can also forge that metadata. Recheck the whole artifact at the last practical point before loading, especially after fetching multiple files or preparing an on-demand runner.
- **The implementation does not search the whole workspace or even every file in its own store.** It trusts only the canonical own-store path with matching verification sidecar; arbitrary-name discovery is limited to `/shared/models`. A fixture already placed at the exact canonical own-store path, with correct bytes but no sidecar, was downloaded again. DS002 explicitly narrows own-store reuse this way, so I report this as a scope/design limitation rather than a backward-compatibility defect. Consider hashing/adopting an unrecorded canonical file before downloading, and document that existing benchmark/download directories require an operator placement step. Do not move or delete the real measured files during that step without the owner's approval.
- **Snapshot digests differ from the plan's literal SHA256 wording.** C12 promises size+SHA256 for every snapshot file; DS002 and the code retain git-blob SHA1 for small Git-backed files. The fresh-snapshot fixture above used SHA256, so R3 is independent of this mismatch. Either explicitly allow the established pinned git-oid form in the plan or implement its literal SHA256 requirement. No migration requirement follows from that choice.
- **Lookup is bounded by entry count, not work or I/O volume.** Each shard/snapshot file walks the tree again and can hash many same-sized candidates. The scan has no signal checks, and each `readdir` materializes the whole directory before the 20,000-entry cap is applied. A large cache should use a cancellable streaming walk or an advisory size/hash index whose candidates are still verified. This is an unmeasured scaling concern, not a claim that this review observed a large-cache failure.
- **The owner's model-retention instruction remains in force.** Product tests may remove their disposable fixtures; engineering must keep the real downloaded models. None of these findings calls for deleting a real model or reclaiming disk as a workaround.

## Verification and missing tests

From the immutable snapshot I ran:

```sh
node --test local-llm/tests/shared-models.test.mjs \
  local-llm/tests/downloader.test.mjs \
  local-llm/tests/hf-snapshot.test.mjs \
  local-llm/tests/split-gguf.test.mjs \
  local-llm/tests/controller.test.mjs
```

**Result: 71 passed, 0 failed, 0 skipped.** The implementation log's full-suite `301/301` is a reported engineering result; I did not independently rerun the whole suite. The six new tests in `shared-models.test.mjs` use single GGUF files and do not cover a real controller Run, a fresh adopted HF snapshot, or split-file adoption. Their static symlink and between-call mutation fixtures do not cover R1/R2. The old-record test is permissible, but preserving old record behavior is not an acceptance requirement.

The additional isolated script below ran successfully and confirmed 12 observations: R1; both R2 paths; R3; R4; R5; both R6 paths; both R7 paths; R8; and the unrecorded-own-file design limitation. Test hooks only schedule races, simulate EXDEV/space and hold a copy; they do not alter the reviewed implementation. No GPU or network is used.

After fixes, add the above regression cases and an end-to-end **small fixture** matrix: complete, incomplete, corrupt and mixed-source split GGUF/HF snapshots; completion only after every required file verifies; partial preservation; Stop/Cancel/drain; actual provenance; and inode-aware deletion. Then the authorized Spark acceptance can prove model reuse with the already-retained pinned weights. Correct bytes and zero network transfer must be demonstrated independently from runner performance.

## Reproduction appendix

The preserved script is also at `/tmp/c12-review-ywenp317/reproduce_codex.mjs`. To reproduce against the exact commit in a separate small source copy:

```sh
snapshot_dir=$(mktemp -d /tmp/c12-review-repeat-XXXXXX)
git -C /home/research/dev/local-llms archive d3c6a94aa12ea100ac936248f40f9c6fe3a51b95 | tar -x -C "$snapshot_dir"
# Save the JavaScript below as "$snapshot_dir/reproduce_codex.mjs".
node "$snapshot_dir/reproduce_codex.mjs"
```

The script removes only directories it itself creates with the `c12-fixture-` prefix. It does not read existing model paths. Its assertions describe the observed defects, so a successful fix should make the corresponding assertion fail; convert them to desired-behavior regression assertions when adding repository tests.

```js
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {downloadArtifact,downloadSnapshotFile,artifactPaths,snapshotPaths,inspectArtifact,removeArtifact} from './local-llm/src/controller/downloader.mjs';
import {createWeightStores} from './local-llm/src/controller/weightStores.mjs';
import {validateModel} from './local-llm/src/controller/catalog.mjs';
import {createController} from './local-llm/src/controller/deployments.mjs';
const payload=Buffer.alloc(256*1024+7,65);
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const artifact={repo:'org/model',commit:'c'.repeat(40),file:'model.gguf',size:payload.length,sha256:hash(payload)};
function setup(){
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'c12-fixture-'));
 const root=path.join(base,'data','models','gguf'),shared=path.join(base,'shared');fs.mkdirSync(shared);
 const paths=artifactPaths({root,artifact});const calls=[];
 const get=(extra={})=>downloadArtifact({root,artifact,adoptFrom:[shared],baseUrl:'http://mock.invalid',fetchImpl:async(u,o)=>{calls.push(new Headers(o?.headers).get('range'));return new Response(payload,{headers:{'content-length':String(payload.length)}});},sleep:async()=>{},...extra});
 return {base,root,shared,paths,calls,get};
}
async function run(name,fn){const s=setup();try{await fn(s);console.log('CONFIRMED',name);}finally{fs.rmSync(s.base,{recursive:true,force:true});}}
await run('fresh HF snapshot adoption fails ENOENT',async s=>{
 const source=path.join(s.shared,'config.json');fs.writeFileSync(source,payload);
 let err;try{await downloadSnapshotFile({root:path.join(s.base,'hf'),artifact:{...artifact,file:'config.json'},adoptFrom:[s.shared],fetchImpl:()=>{throw Error('network must not be needed')}});}catch(e){err=e;}
 assert.equal(err?.code,'ENOENT');assert.match(err.message,/rename/);console.log('  ',err.message);
});
await run('write after final hash chunk is blessed by post-hash stat and reused indefinitely',async s=>{
 const source=path.join(s.shared,'ready.gguf');fs.writeFileSync(source,payload);let changed=false;
 const r=await s.get({progressIntervalMs:0,onProgress:p=>{if(p.bytes===artifact.size&&!changed){changed=true;const fd=fs.openSync(source,'r+');fs.writeSync(fd,Buffer.from('B'),0,1,0);fs.closeSync(fd);}}});
 assert.equal(r.status,'complete');assert.notEqual(hash(fs.readFileSync(s.paths.file)),artifact.sha256);
 const again=await s.get();assert.equal(again.reverified,undefined);assert.equal(s.calls.length,0);
 console.log('  first=complete, pinned hash mismatch=true, next reverified='+again.reverified+', downloads='+s.calls.length);
});
await run('canonical symlink is accepted and target edits bypass revalidation',async s=>{
 fs.writeFileSync(path.join(s.shared,'ready.gguf'),payload);await s.get();
 const outside=path.join(s.base,'outside.gguf');fs.writeFileSync(outside,payload);fs.unlinkSync(s.paths.file);fs.symlinkSync(outside,s.paths.file);
 const verified=await s.get();assert.equal(verified.reverified,true);assert.ok(fs.lstatSync(s.paths.file).isSymbolicLink());
 const fd=fs.openSync(outside,'r+');fs.writeSync(fd,Buffer.from('B'),0,1,0);fs.closeSync(fd);
 const again=await s.get();assert.equal(again.reverified,undefined);assert.notEqual(hash(fs.readFileSync(s.paths.file)),artifact.sha256);
 console.log('  symlink reverified=true; changed target trusted without rehash=true');
});
await run('wrong shared candidate destroys valid resumable partial',async s=>{
 fs.mkdirSync(path.dirname(s.paths.file),{recursive:true});fs.writeFileSync(s.paths.partial,payload.subarray(0,131072));fs.writeFileSync(s.paths.identity,JSON.stringify(artifact));
 const wrong=Buffer.from(payload);wrong[0]=66;fs.writeFileSync(path.join(s.shared,'wrong.gguf'),wrong);
 await s.get();assert.deepEqual(s.calls,[null]);console.log('  131072-byte valid partial existed; first HTTP Range='+s.calls[0]);
});
await run('copy fallback ignores free-space check',async s=>{
 fs.writeFileSync(path.join(s.shared,'ready.gguf'),payload);let checks=0;
 const fsApi={...fs,promises:{...fs.promises,link:async()=>{throw Object.assign(Error('EXDEV'),{code:'EXDEV'})}}};
 const r=await s.get({fsApi,statfs:async()=>{checks++;return {bavail:0,bsize:4096}}});
 assert.equal(r.adopted.method,'copy');assert.equal(checks,0);console.log('  result=complete copy, free-space checks='+checks);
});
await run('Run refuses reusable file on disk space before attempting adoption',async s=>{
 fs.writeFileSync(path.join(s.shared,'ready.gguf'),payload);let fetchCalls=0;
 const G=1024**3;const source={...artifact,type:'huggingface'};
 const controller=createController({dataDir:path.join(s.base,'data'),env:{PATH:'/usr/bin'},sharedModelsRoot:s.shared,seedCatalog:[validateModel({id:'tiny-model',displayName:'Tiny',sources:{gguf:source}},{seed:true})],fileExists:()=>true,detectRunner:r=>({installed:true,version:r.pinnedVersion}),snapshot:async()=>({gpu:{available:true,totalBytes:100*G,freeBytes:100*G,memoryModel:'dedicated'},memory:{totalBytes:100*G,availableBytes:100*G},disk:{freeBytes:artifact.size/2,totalBytes:100*G}}),download:async()=>{fetchCalls++;throw Error('should reach reuse');}});
 let err;try{await controller.run({requestId:'request-reuse-0001',modelId:'tiny-model',runnerId:'llama.cpp'});}catch(e){err=e;}
 assert.equal(err?.code,'admission_insufficient_now');assert.equal(fetchCalls,0);console.log('  ',err.code,err.message,'fetch calls='+fetchCalls);
});
await run('file already at canonical own-store path without sidecar is downloaded again',async s=>{
 fs.mkdirSync(path.dirname(s.paths.file),{recursive:true});fs.writeFileSync(s.paths.file,payload);await s.get();assert.equal(s.calls.length,1);console.log('  exact pinned canonical file existed, downloads='+s.calls.length);
});
await run('snapshot returns no adoption provenance even after successful reuse',async s=>{
 const root=path.join(s.base,'data','models','hf');const {dir}=snapshotPaths({root,repo:artifact.repo,commit:artifact.commit});fs.mkdirSync(dir,{recursive:true});
 fs.writeFileSync(path.join(s.shared,'one.bin'),payload);
 const store=createWeightStores({dataDir:path.join(s.base,'data'),env:{},sharedModelsRoot:s.shared})['hf-snapshot'];
 const source={type:'hf-snapshot',repo:artifact.repo,commit:artifact.commit,size:artifact.size,files:[{path:'model.safetensors',size:artifact.size,sha256:artifact.sha256}]};
 const r=await store.fetch({artifact:source});assert.equal(r.bytesTransferred,0);assert.equal(r.adopted,undefined);console.log('  transferred=0, adopted='+r.adopted);
});
await run('shared directory swapped to symlink is followed outside root',async s=>{
 const dir=path.join(s.shared,'sub');fs.mkdirSync(dir);const outside=path.join(s.base,'external');fs.mkdirSync(outside);fs.writeFileSync(path.join(outside,'ready.gguf'),payload);let swapped=false;
 const fsApi={...fs,promises:{...fs.promises,readdir:async(p,o)=>{const entries=await fs.promises.readdir(p,o);if(p===s.shared&&!swapped){swapped=true;fs.renameSync(dir,dir+'-old');fs.symlinkSync(outside,dir);}return entries;}}};
 const r=await s.get({fsApi});assert.equal(r.adopted.method,'link');assert.ok(fs.realpathSync(r.adopted.source).startsWith(outside+path.sep));assert.equal(s.calls.length,0);
 console.log('  adopted from outside shared root through renamed directory=true');
});
await run('aborting during copy does not settle until copy finishes',async s=>{
 fs.writeFileSync(path.join(s.shared,'ready.gguf'),payload);const ac=new AbortController();let release,entered;
 const gate=new Promise(r=>release=r),started=new Promise(r=>entered=r);
 const fsApi={...fs,promises:{...fs.promises,link:async()=>{throw Object.assign(Error('EXDEV'),{code:'EXDEV'})},copyFile:async(...a)=>{entered();await gate;return fs.promises.copyFile(...a)}}};
 let settled=false;const p=s.get({fsApi,signal:ac.signal}).then(r=>{settled=true;return r},e=>{settled=true;return e});
 await started;ac.abort();await new Promise(r=>setTimeout(r,25));assert.equal(settled,false);release();const result=await p;assert.equal(result.code,'ABORTED');
 console.log('  cancellation pending until injected copy completed; final='+result.code);
});
await run('snapshot deletion undercounts last inode with multiple in-snapshot hardlinks',async s=>{
 const source={type:'hf-snapshot',repo:artifact.repo,commit:artifact.commit,size:2*artifact.size,files:[{path:'model-a.safetensors',size:artifact.size,sha256:artifact.sha256},{path:'model-b.safetensors',size:artifact.size,sha256:artifact.sha256}]};
 const root=path.join(s.base,'data','models','hf');const {dir}=snapshotPaths({root,repo:source.repo,commit:source.commit});fs.mkdirSync(dir,{recursive:true});
 const first=path.join(dir,source.files[0].path),second=path.join(dir,source.files[1].path);fs.writeFileSync(first,payload);fs.linkSync(first,second);
 const store=createWeightStores({dataDir:path.join(s.base,'data'),env:{},sharedModelsRoot:s.shared})['hf-snapshot'];
 const freed=await store.remove(source);assert.equal(freed,0);assert.equal(fs.existsSync(dir),false);
 console.log('  removed last two links to '+artifact.size+'-byte regular inode, reported freedBytes='+freed);
});
await run('GGUF adoption provenance field does not match controller log',async s=>{
 const source=path.join(s.shared,'ready.gguf');fs.writeFileSync(source,payload);
 const store=createWeightStores({dataDir:path.join(s.base,'data'),env:{},sharedModelsRoot:s.shared,download:downloadArtifact,inspect:inspectArtifact,remove:removeArtifact}).huggingface;
 const r=await store.fetch({artifact:{...artifact,type:'huggingface'}});const entry=r.adopted[0];assert.equal(entry.source,source);assert.equal(entry.from,undefined);
 console.log(`  controller log: adopted ${entry.file} from ${entry.from} (${entry.method}, verified)`);
});
```
