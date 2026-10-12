import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {execFileSync,spawnSync} from 'node:child_process';
const workspace='/Users/danielsava/work/file-parser';
const retention=path.join(workspace,'evidence/hwl/source-retention-2026-10-11');
const helper='/tmp/file-parser-snapshot-cleanup.mjs';
const helperSha='9a62099314e65e4369a4f9fb85478e154957723901973f6f2f2c0f6f03fffcc2';
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
const fileHash=p=>digest(fs.readFileSync(p));
const manifestFile=path.join(retention,'manifest.json');
const manifestSha=fileHash(manifestFile), manifest=JSON.parse(fs.readFileSync(manifestFile));
const scratch=fs.mkdtempSync('/tmp/independent-recovery-');
const receipt='/tmp/snapshot-recovery-verification.json';
const checks=[];
const env={...process.env,COPYFILE_DISABLE:'1',GIT_OPTIONAL_LOCKS:'0'};
const run=(command,args,opts={})=>execFileSync(command,args,{encoding:'utf8',env,maxBuffer:100*1024*1024,...opts});
const emit=(check,observed)=>{checks.push({check,result:'PASS',observed});console.log(JSON.stringify({check,...observed}));};
const roots=['full_budget_prepare_2026-10-04_codex','vllm_stage2_2026-10-04_codex','live-apparatus-vllm-20261003-170239_postcleanup_claude'].map(n=>'evidence/hwl/'+n);
const expected=roots.flatMap(r=>['AssistOSExplorer','container-image-builds','local-llms','ploinky','deps/achillesAgentLib','deps/mcp-sdk'].map(n=>r+'/'+n));
expected.push('container-image-builds/sources/ploinky',roots[0]+'/proposal_codex/candidate-4425e2a3f5dbbcf5b22e7942dfe2fd84',roots[1]+'/proposal_codex/candidate-5c4b9581f2a1494715f83ac729b52860',roots[2]+'/evidence/candidate-752291a0db0906c0e701a38c7a611872',roots[0]+'/proposal_codex/candidate_4425e2a3f5dbbcf5b22e7942dfe2fd84_codex.tar',roots[1]+'/proposal_codex/candidate_5c4b9581f2a1494715f83ac729b52860_codex.tar',roots[2]+'/evidence/candidate-752291a0db0906c0e701a38c7a611872.tar');
function validateTarget(s){
 assert.equal(typeof s,'string'); assert(s && !path.isAbsolute(s));assert(!s.split('/').some(c=>c==='..'||c==='.'||c===''));
 assert(expected.includes(s),'Target outside independent exact allowlist');
 const full=path.resolve(workspace,s);assert.equal(fs.realpathSync(full),full);assert(!fs.lstatSync(full).isSymbolicLink());return full;
}
function scan(root,{omitGit=false,exclude=[]}={}){
 const rows=[];const stack=['.'];
 while(stack.length){const rel=stack.pop(),full=path.join(root,rel);if(exclude.includes(full))continue;
 const stat=fs.lstatSync(full);const row={path:rel,mode:stat.mode&0o7777};
 if(stat.isSymbolicLink())Object.assign(row,{type:'symlink',target:fs.readlinkSync(full)});
 else if(stat.isFile())Object.assign(row,{type:'file',bytes:stat.size,sha256:fileHash(full)});
 else {assert(stat.isDirectory());Object.assign(row,{type:'directory'});const names=fs.readdirSync(full).sort().reverse();for(const name of names){if(omitGit&&rel==='.'&&name==='.git')continue;assert(!(name==='.git'&&rel!=='.'));stack.push(rel==='.'?name:rel+'/'+name);}}
 rows.push(row);
 }return rows;
}
const equalTree=(a,b)=>assert.deepEqual(a,b,'Independent filesystem inventory mismatch');
let failure=null;
try{
 assert.equal(fileHash(helper),helperSha);assert.equal(manifest.workspace,workspace);assert.deepEqual(manifest.entries.map(e=>e.path),expected);assert.equal(expected.length,25);
 for(const e of manifest.entries){const stat=fs.lstatSync(validateTarget(e.path));assert.equal(stat.ino,e.identity.ino);assert.equal(stat.dev,e.identity.dev);assert.equal(stat.uid,e.identity.uid);assert.equal(stat.mode&0o7777,e.identity.mode);}
 emit('immutable candidate and target identities',{manifestSha256:manifestSha,helperSha256:helperSha,targets:25});
 const artifactNames=manifest.artifacts.map(a=>a.path);assert.equal(new Set(artifactNames).size,artifactNames.length);assert.deepEqual([...new Set(manifest.entries.map(e=>e.archive))].sort(),artifactNames.toSorted());
 for(const a of manifest.artifacts){assert(/^archives\/[0-9a-f]{64}\.(tar|payload)\.gz$/.test(a.path));const p=path.join(retention,a.path);assert.equal(fileHash(p),a.sha256);assert.equal(fs.statSync(p).size,a.bytes);run('/usr/bin/gzip',['-t',p]);}
 emit('all artifact hashes sizes gzip integrity',{artifacts:manifest.artifacts.length});
 const restored=new Map();let dirs=0,files=0,symlinks=0,emptyDirs=0,gitRepos=0;
 for(const e of manifest.entries.filter(e=>e.treeManifest)){
  assert(/^trees\/[0-9a-f]{64}\.json$/.test(e.treeManifest));const treeFile=path.join(retention,e.treeManifest);assert.equal(fileHash(treeFile),e.contentSha256);const expectedTree=JSON.parse(fs.readFileSync(treeFile));
  if(!restored.has(e.archive)){
   const archive=path.join(retention,e.archive);const members=run('/usr/bin/tar',['-tzf',archive]).trimEnd().split('\n');for(const m of members){assert(m==='.'||m.startsWith('./'));assert(!m.split('/').includes('..'));assert(!m.split('/').includes('.git'));}
   const dest=path.join(scratch,'restore-'+restored.size);fs.mkdirSync(dest);run('/usr/bin/tar',['-xzpf',archive,'-C',dest]);const actual=scan(dest);equalTree(actual,expectedTree);restored.set(e.archive,actual);
   files+=actual.filter(r=>r.type==='file').length;symlinks+=actual.filter(r=>r.type==='symlink').length;emptyDirs+=actual.filter(r=>r.type==='directory'&&fs.readdirSync(path.join(dest,r.path)).length===0).length;
  }
  equalTree(restored.get(e.archive),expectedTree);equalTree(scan(path.join(workspace,e.path),{omitGit:true}),expectedTree);dirs++;
  if(e.git){const git=args=>run('/usr/bin/git',['--no-optional-locks','-C',path.join(workspace,e.path),...args]);assert.equal(git(['rev-parse','HEAD']).trim(),e.git.head);assert.equal(git(['rev-parse','HEAD^{tree}']).trim(),e.git.tree);assert.equal(git(['cat-file','commit',e.git.head]),e.git.commit);assert.equal(git(['show-ref']).trim(),e.git.refs);assert.equal(git(['status','--porcelain=v1','--untracked-files=all']).trim(),e.git.status);const commitBytes=Buffer.from(e.git.commit);const id=crypto.createHash('sha1').update(Buffer.from('commit '+commitBytes.length+'\0')).update(commitBytes).digest('hex');assert.equal(id,e.git.head);gitRepos++;}
 }
 emit('every source archive extracted and compared to manifests and originals',{uniqueSourceArchives:restored.size,originalDirectories:dirs,files,symlinks,emptyDirectories:emptyDirs,gitIdentities:gitRepos});
 let payloads=0;for(const e of manifest.entries.filter(e=>e.originalSha256)){const restoredFile=path.join(scratch,'payload-'+payloads+'.tar');const fd=fs.openSync(restoredFile,'wx');try{execFileSync('/usr/bin/gzip',['-dc',path.join(retention,e.archive)],{env,stdio:['ignore',fd,'pipe']});}finally{fs.closeSync(fd);}assert.equal(fileHash(restoredFile),e.originalSha256);assert.equal(fs.statSync(restoredFile).size,e.originalBytes);assert.equal(fileHash(path.join(workspace,e.path)),e.originalSha256);assert.equal(fs.statSync(path.join(workspace,e.path)).size,e.originalBytes);payloads++;}
 emit('decompressed TAR payloads byte exact',{payloads});
 let retainedEntries=0,actualExecutionEntries=0;const exclusions=expected.map(p=>path.join(workspace,p));for(const r of roots){const actual=scan(path.join(workspace,r),{exclude:exclusions});equalTree(actual,manifest.retained[r]);retainedEntries+=actual.length;actualExecutionEntries+=actual.filter(e=>e.path==='actual_execution_codex'||e.path.startsWith('actual_execution_codex/')).length;}
 const calibration=path.join(workspace,roots[2],'evidence/apparatus-vllm-run_llm-l3-calibration_claude.json');assert.equal(fileHash(calibration),'d0d7ea83f9ff2ac7ab4eb6474915c991e345f57acddd1416bb80152809cec8f2');
 emit('full retained evidence unchanged',{retainedEntries,actualExecutionEntries,calibrationSha256:fileHash(calibration)});
 const originalArchive=manifest.artifacts[0];const corrupt=fs.readFileSync(path.join(retention,originalArchive.path));corrupt[corrupt.length-8]^=1;const badFile=path.join(scratch,'corrupt.gz');fs.writeFileSync(badFile,corrupt);const bad=spawnSync('/usr/bin/gzip',['-t',badFile],{encoding:'utf8'});assert.notEqual(bad.status,0);assert.equal(bad.signal,null);emit('adversarial corrupted gzip rejected',{exitCode:bad.status,stderr:bad.stderr.trim().replaceAll(scratch,'<scratch>')});
 const actualTree=restored.values().next().value;const damagedTree=structuredClone(actualTree);damagedTree.find(e=>e.type==='file').sha256='0'.repeat(64);assert.throws(()=>equalTree(actualTree,damagedTree),/Independent filesystem inventory mismatch/);const missingEmpty=structuredClone(actualTree);missingEmpty[0].mode^=0o100;assert.throws(()=>equalTree(actualTree,missingEmpty),/Independent filesystem inventory mismatch/);emit('adversarial manifest byte and mode mismatch rejected',{rejected:2});
 const badPaths=['','/','../file-parser',expected[0]+'/..',expected[0]+'/extra','ploinky',expected[0]+'/',roots[0]+'/actual_execution_codex'];for(const target of badPaths)assert.throws(()=>validateTarget(target));emit('adversarial unsafe target rejected independently',{rejected:badPaths.length});
 assert.equal(fileHash(manifestFile),manifestSha);assert.equal(fileHash(helper),helperSha);for(const a of manifest.artifacts)assert.equal(fileHash(path.join(retention,a.path)),a.sha256);
 for(const r of roots)equalTree(scan(path.join(workspace,r),{exclude:exclusions}),manifest.retained[r]);
 emit('final candidate and retained evidence unchanged',{manifestSha256:manifestSha,originalTargetsStillPresent:expected.filter(p=>fs.existsSync(path.join(workspace,p))).length});
}catch(error){failure={message:error.message,stack:error.stack};console.error(error.stack);}
finally{
 assert(scratch.startsWith('/tmp/independent-recovery-')&&path.dirname(scratch)==='/tmp');assert.equal(fs.realpathSync(scratch),'/private'+scratch);fs.rmSync(scratch,{recursive:true,force:false});
 const record={checkedAt:new Date().toISOString(),command:'node /tmp/verify-snapshot-recovery.mjs',scriptSha256:fileHash('/tmp/verify-snapshot-recovery.mjs'),manifestSha256:manifestSha,helperSha256:helperSha,workspace,environment:{platform:process.platform,node:process.version,tar:run('/usr/bin/tar',['--version']).trim()},scope:'Independent source-only recovery before deletion; Git history intentionally omitted; no cleanup helper execution, product test, live or deployment claims.',checks,failure,scratchRemoved:!fs.existsSync(scratch),verdict:failure?'FAIL':'PASS'};
 fs.writeFileSync(receipt,JSON.stringify(record,null,2)+'\n');console.log(JSON.stringify({receipt,verdict:record.verdict,scratchRemoved:record.scratchRemoved}));
}
if(failure)process.exitCode=1;
