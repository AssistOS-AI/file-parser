// Independent reproduction of the C12 cancellation-result gap at local-llms 70047bd.
// Small disposable fixtures only; no GPU, no network. Imports the recovery clone's source read-only.
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

const SRC = process.env.LOCAL_LLMS_SRC || '/Users/danielsava/work/local-llm-recovery-20260928/local-llms/local-llm/src';
const { loadSeedCatalog, validateModel } = await import(path.join(SRC, 'controller/catalog.mjs'));
const { createController } = await import(path.join(SRC, 'controller/deployments.mjs'));
const { downloadArtifact, verifyArtifact } = await import(path.join(SRC, 'controller/downloader.mjs'));

const SIZE = 256 * 1024 + 7;
const PAYLOAD = crypto.randomBytes(SIZE);
const sha256 = (b) => crypto.createHash('sha256').update(b).digest('hex');
const ARTIFACT = Object.freeze({ repo: 'org/model-GGUF', file: 'model-Q8_0.gguf', revision: 'main', commit: 'c'.repeat(40), size: SIZE, sha256: sha256(PAYLOAD) });
const GIB = 1024 ** 3;

function fixture(t, { freeDisk = 300 * GIB, subdirs = 0 } = {}) {
    const base = fs.mkdtempSync(path.join(os.tmpdir(), 'c12-cancel-gap-'));
    t.after(() => fs.rmSync(base, { recursive: true, force: true }));
    const dataDir = path.join(base, 'data');
    const shared = path.join(base, 'shared', 'models');
    fs.mkdirSync(shared, { recursive: true });
    for (let i = 0; i < subdirs; i += 1) fs.mkdirSync(path.join(shared, `d${i}`));
    const requests = [];
    const fetchImpl = async (url, options = {}) => {
        requests.push(String(url));
        return new Response(PAYLOAD, { status: 200, headers: { 'content-length': String(SIZE) } });
    };
    const GPT = loadSeedCatalog().find((m) => m.id === 'gpt-oss-20b');
    const tiny = validateModel({ ...GPT, id: 'tiny', displayName: 'Tiny', sources: { gguf: { type: 'huggingface', ...ARTIFACT } } }, { seed: true });
    const launches = [];
    const controller = createController({
        dataDir, env: { PATH: '/usr/bin' }, seedCatalog: [tiny], sharedModelsRoot: shared,
        snapshot: async () => ({
            gpu: { available: true, name: 'Test GPU', totalBytes: 24 * GIB, usedBytes: 0, freeBytes: 24 * GIB, processes: [] },
            memory: { totalBytes: 64 * GIB, availableBytes: 60 * GIB },
            disk: { freeBytes: freeDisk, totalBytes: 500 * GIB }, cpus: 8,
        }),
        download: (o) => downloadArtifact({ ...o, fetchImpl, baseUrl: 'http://hf.invalid', sleep: async () => {}, chunkBytes: 64 * 1024 }),
        verify: verifyArtifact, fileExists: () => true,
        detectRunner: (r) => ({ installed: r.supported, version: r.pinnedVersion, reason: null }),
        startRunner: ({ log }) => {
            let exit; const exited = new Promise((r) => { exit = r; });
            const h = { pid: 4242, exited, running: true, async stop() { h.running = false; exit({ code: 0, signal: 'SIGTERM', error: null }); return exited; } };
            log.append('stdout', 'load_tensors: offloaded 25/25 layers to GPU'); launches.push(h); return h;
        },
        fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({}) }), pollMs: 2, stopGraceMs: 50,
    });
    t.after(async () => { await controller.stop().catch(() => {}); });
    return { shared, controller, launches, requests };
}

// Hold the first opendir of the shared root until released; count opens.
function gateOpendir(t, shared) {
    const original = fs.promises.opendir;
    const g = { opened: 0 };
    const gate = new Promise((r) => { g.release = r; });
    g.entered = new Promise((r) => { g.enter = r; });
    let held = false;
    fs.promises.opendir = async (dir, options) => {
        g.opened += 1;
        if (dir === shared && !held) { held = true; g.enter(); await gate; }
        return original(dir, options);
    };
    t.after(() => { fs.promises.opendir = original; });
    return g;
}

const run = (c, id) => c.controller.run({ requestId: id, modelId: 'tiny', runnerId: 'llama.cpp' }).then((v) => ({ ok: v }), (e) => ({ err: e }));
const show = (label, o) => console.log(label, o.err ? `ERROR ${o.err.code}: ${o.err.message}` : `OK ${JSON.stringify({ accepted: o.ok.accepted, phase: o.ok.deployment?.phase })}`);

for (const [name, freeDisk] of [['ample disk', 300 * GIB], ['disk below the model size', 1024]]) {
    test(`Stop during an EMPTY lookup (${name}): Run outcome`, async (t) => {
        const c = fixture(t, { freeDisk });
        const g = gateOpendir(t, c.shared);
        const running = run(c, `req-empty-stop-${freeDisk}`);
        await g.entered;
        const stopping = c.controller.stop();
        g.release();
        const outcome = await running; await stopping;
        show(`[empty/${name}/Stop] Run ->`, outcome);
        console.log(`[empty/${name}/Stop] launches=${c.launches.length} network=${c.requests.length} phase=${c.controller.state.deployment?.phase ?? 'none'}`);
        assert.equal(outcome.err?.code, 'cancelled', 'desired: a Run whose planning was stopped reports cancelled');
    });
}

test('Cancel during an EMPTY lookup: Run and Cancel outcomes', async (t) => {
    const c = fixture(t, { freeDisk: 1024 });
    const g = gateOpendir(t, c.shared);
    const running = run(c, 'req-empty-cancel');
    await g.entered;
    const cancelling = c.controller.cancelDownload().then((v) => ({ ok: v }), (e) => ({ err: e }));
    g.release();
    const outcome = await running; const cancel = await cancelling;
    show('[empty/Cancel] Run ->', outcome); show('[empty/Cancel] Cancel ->', cancel);
    assert.equal(outcome.err?.code, 'cancelled');
    assert.ok(!cancel.err, `desired: Cancel that stopped planning succeeds, got ${cancel.err?.code}`);
});

test('Cancel during a NONEMPTY lookup: Run and Cancel outcomes', async (t) => {
    const c = fixture(t, { subdirs: 20 });
    const g = gateOpendir(t, c.shared);
    const running = run(c, 'req-nonempty-cancel');
    await g.entered;
    const cancelling = c.controller.cancelDownload().then((v) => ({ ok: v }), (e) => ({ err: e }));
    g.release();
    const outcome = await running; const cancel = await cancelling;
    show('[nonempty/Cancel] Run ->', outcome); show('[nonempty/Cancel] Cancel ->', cancel);
    console.log(`[nonempty/Cancel] opendir calls=${g.opened} launches=${c.launches.length}`);
    assert.equal(outcome.err?.code, 'cancelled');
    assert.ok(!cancel.err, `desired: Cancel that stopped planning succeeds, got ${cancel.err?.code}`);
});

test('Positive control: Stop during a NONEMPTY lookup reports cancelled (existing test 21 shape)', async (t) => {
    const c = fixture(t, { subdirs: 20 });
    const g = gateOpendir(t, c.shared);
    const running = run(c, 'req-nonempty-stop');
    await g.entered;
    const stopping = c.controller.stop();
    g.release();
    const outcome = await running; await stopping;
    show('[nonempty/Stop] Run ->', outcome);
    assert.equal(outcome.err?.code, 'cancelled');
    assert.equal(g.opened, 1);
});

test('Positive control: Cancel with nothing running still reports not_downloading', async (t) => {
    const c = fixture(t);
    await assert.rejects(c.controller.cancelDownload(), (e) => e.code === 'not_downloading');
});
