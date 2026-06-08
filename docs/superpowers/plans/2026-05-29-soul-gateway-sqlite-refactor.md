# Soul Gateway SQLite Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `proxies/soul-gateway` to use an embedded SQLite database inside the Soul Gateway agent container, remove the Ploinky Postgres dependency, and publish a custom `assistos/soul-gateway` image that includes SQLite and the gateway code.

**Architecture:** Soul Gateway becomes a single Ploinky-managed agent with one container and one durable data volume. The runtime opens `SQLITE_PATH` under `/data`, initializes a fresh SQLite schema on startup, and keeps all provider configuration, API keys, sessions, audit logs, and credentials in the same agent boundary. The central `container-image-builds` repository publishes the image by checking out `PloinkyRepos/proxies`, baking `proxies/soul-gateway` into `/opt/soul-gateway`, and smoke-testing Node SQLite plus the `sqlite3` CLI.

**Tech Stack:** Node.js 24 ES modules, official `node:sqlite`, SQLite WAL mode, Ploinky manifest volumes, GitHub Actions Docker Buildx, Podman runtime deployment.

---

## Non-Negotiable Constraints

- Do not preserve old Postgres data.
- Do not build a Postgres-to-SQLite migration path.
- Do not create a separate SQLite Ploinky agent or dependency.
- Keep Soul Gateway public traffic behind `/services/soul-gateway/v1/` and management behind `/services/soul-gateway/management/`.
- Keep request-time LLM inference inside `achillesAgentLib`; this refactor is persistence and packaging only.
- Do not add generated-code attribution, tool-signature footers, or agent attribution to commits, docs, metadata, or PR text.
- Durable data must live under a manifest-declared `.ploinky/data/...` path, mounted into the Soul Gateway container as `/data`.

## Current-State Anchors

- `proxies/soul-gateway/manifest.json` uses `docker.io/assistos/ploinky-node:24-bookworm-tools` and declares `"enable": ["postgres"]`.
- `proxies/soul-gateway/startup.sh` constructs `DATABASE_URL` from `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, and `PGDATABASE`.
- `proxies/soul-gateway/src/bootstrap.mjs` imports `createPgPool`, calls `ensureSchema`, and runs Postgres migrations when `DATABASE_URL` exists.
- `proxies/soul-gateway/src/db/pool.mjs`, `src/db/migrator.mjs`, and `src/db/advisory-lock.mjs` are Postgres-specific.
- `proxies/soul-gateway/src/db/migrations/*.sql` use schemas, `uuid`, `bytea`, `jsonb`, `timestamptz`, `gen_random_uuid()`, partitions, Postgres casts, GIN indexes, and advisory locks.
- `proxies/.github/workflows/deploy-soul-gateway.yml` writes `PGPASSWORD`, configures PG vars, starts Postgres via Ploinky, and patches Postgres auth.
- `proxies/.github/workflows/soul-gateway-admin.yml` uses `psql` for status queries.
- `container-image-builds` already supports source-checkout images via `publish-bwrap-runner.yml` and `publish-livekit-server-agent.yml`.

## File Map

### `proxies/soul-gateway`

- Modify `manifest.json`: switch container image, remove Postgres dependency, remove PG env vars, add `SQLITE_PATH`, add `/data` volume.
- Modify `startup.sh`: stop building `DATABASE_URL`, run baked code from `/opt/soul-gateway`, set `DATA_DIR=/data`, `CREDENTIALS_DIR=/data/credentials`, `SQLITE_PATH=/data/soul-gateway.sqlite3`.
- Modify `install.sh`: generate encryption key under `/data/encryption.key`, keep browser runtime behavior, avoid runtime `npm ci` when image deps exist.
- Modify `package.json` and `package-lock.json`: remove `pg`; do not add native SQLite dependencies unless Node 24 `node:sqlite` is rejected during image smoke tests.
- Replace `src/db/pool.mjs` with `src/db/sqlite-db.mjs`: open SQLite, set PRAGMAs, expose async query facade, normalize rows, and close database.
- Replace `src/db/migrator.mjs` with fresh SQLite schema initialization or `src/db/schema.mjs`.
- Delete or stop using `src/db/advisory-lock.mjs`.
- Replace `src/db/migrations/*.sql` with one SQLite schema file, for example `src/db/schema/sqlite-current.sql`.
- Remove `src/db/import/*` and `npm run import:*` scripts, because old data is intentionally discarded.
- Modify every DAO under `src/db/dao/` to remove Postgres-only SQL and return normalized rows.
- Modify direct SQL outside DAOs in management, runtime providers, metrics, snapshot loading, spend cache, and session handling.
- Modify `src/bootstrap.mjs`, `src/shutdown.mjs`, and background scheduler guards to treat SQLite as the default persistent store.
- Modify tests under `src/test/unit/` and add SQLite integration tests under `src/test/integration/`.
- Update `docs/specs/DS006-database-schema.md`, `DS013-configuration-deployment.md`, `DS016-ploinky-agent-mode.md`, and `CLAUDE.md`.

### `proxies/.github/workflows`

- Modify `deploy-soul-gateway.yml`: remove all Postgres setup and verification.
- Modify `soul-gateway-admin.yml`: replace `psql` status query with SQLite or management API status.
- Review `destroy-soul-gateway.yml`: no Postgres-specific changes expected beyond wording if any gets added later.

### `container-image-builds`

- Create `images/soul-gateway/Dockerfile`.
- Create `.github/workflows/publish-soul-gateway-image.yml`.
- Modify `README.md`: add the new image row and manual publishing command.
- Modify `tests/image-definitions.test.mjs`: assert source checkout, image name, Dockerfile path, SQLite install, baked source, and smoke command patterns.

---

## Task 1: Add SQLite Image Definition

**Files:**
- Create: `container-image-builds/images/soul-gateway/Dockerfile`
- Create: `container-image-builds/.github/workflows/publish-soul-gateway-image.yml`
- Modify: `container-image-builds/README.md`
- Modify: `container-image-builds/tests/image-definitions.test.mjs`

- [x] **Step 1: Write image-definition tests**

Add a test block to `container-image-builds/tests/image-definitions.test.mjs`:

```js
test('soul-gateway workflow builds source checkout with SQLite and baked gateway code', () => {
    const workflow = read('.github/workflows/publish-soul-gateway-image.yml');
    const dockerfile = read('images/soul-gateway/Dockerfile');

    assert.match(workflow, /repository:\s*PloinkyRepos\/proxies/);
    assert.match(workflow, /path:\s*sources\/proxies/);
    assert.match(workflow, /git -C sources\/proxies rev-parse --short=12 HEAD/);
    assert.match(workflow, /context:\s*\.\/sources\/proxies\/soul-gateway/);
    assert.match(workflow, /file:\s*\.\/images\/soul-gateway\/Dockerfile/);
    assert.match(workflow, /IMAGE_NAME:\s*assistos\/soul-gateway/);
    assert.match(workflow, /docker\/build-push-action@v6/);
    assert.match(workflow, /node -e "import\('node:sqlite'\)/);
    assert.match(workflow, /sqlite3 --version/);

    assert.match(dockerfile, /^ARG BASE_IMAGE=docker\.io\/assistos\/ploinky-node:24-bookworm-tools$/m);
    assert.match(dockerfile, /\bsqlite3\b/);
    assert.match(dockerfile, /WORKDIR \/opt\/soul-gateway/);
    assert.match(dockerfile, /COPY package\.json package-lock\.json \.\//);
    assert.match(dockerfile, /RUN npm ci --omit=dev/);
    assert.match(dockerfile, /COPY src \/opt\/soul-gateway\/src/);
    assert.match(dockerfile, /COPY startup\.sh install\.sh cli\.sh \/\opt\/soul-gateway\//);
});
```

- [x] **Step 2: Run the image-definition tests and confirm failure**

Run:

```bash
cd /Users/danielsava/work/file-parser/container-image-builds
node --test tests/image-definitions.test.mjs
```

Expected: FAIL because the Soul Gateway Dockerfile and workflow do not exist.

- [x] **Step 3: Add `images/soul-gateway/Dockerfile`**

Use this baseline:

```dockerfile
ARG BASE_IMAGE=docker.io/assistos/ploinky-node:24-bookworm-tools
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive
ENV NODE_ENV=production
ENV SOUL_GATEWAY_IMAGE_APP_DIR=/opt/soul-gateway

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        sqlite3 \
        libsqlite3-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/soul-gateway

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY src /opt/soul-gateway/src
COPY startup.sh install.sh cli.sh /opt/soul-gateway/
COPY manifest.json /opt/soul-gateway/manifest.json

RUN chmod +x /opt/soul-gateway/startup.sh \
    /opt/soul-gateway/install.sh \
    /opt/soul-gateway/cli.sh \
    && node -e "import('node:sqlite').then(() => console.log('node:sqlite ok'))" \
    && sqlite3 --version

WORKDIR /opt/soul-gateway
```

- [x] **Step 4: Add `publish-soul-gateway-image.yml`**

Use the source-checkout workflow pattern:

```yaml
name: Publish Soul Gateway image

on:
  workflow_dispatch:
    inputs:
      source_ref:
        description: 'PloinkyRepos/proxies ref to build from'
        required: false
        default: 'main'
        type: string
      image_tag:
        description: 'Docker Hub tag to publish'
        required: false
        default: 'node24-sqlite'
        type: string

permissions:
  contents: read

concurrency:
  group: publish-soul-gateway-image
  cancel-in-progress: false

env:
  IMAGE_NAME: assistos/soul-gateway
  IMAGE_TAG: ${{ inputs.image_tag || 'node24-sqlite' }}

jobs:
  publish:
    name: Build and push Docker Hub image
    runs-on: ubuntu-latest
    steps:
      - name: Checkout image definitions
        uses: actions/checkout@v4

      - name: Checkout proxies source
        uses: actions/checkout@v4
        with:
          repository: PloinkyRepos/proxies
          ref: ${{ inputs.source_ref || 'main' }}
          path: sources/proxies
          token: ${{ secrets.SOURCE_REPO_TOKEN || github.token }}

      - name: Resolve source revision
        id: source
        run: echo "sha=$(git -C sources/proxies rev-parse --short=12 HEAD)" >> "$GITHUB_OUTPUT"

      - name: Smoke build local architecture
        run: |
          set -euo pipefail
          docker build \
            -f images/soul-gateway/Dockerfile \
            -t "$IMAGE_NAME:smoke" \
            sources/proxies/soul-gateway
          docker run --rm "$IMAGE_NAME:smoke" sh -lc 'node -e "import('\''node:sqlite'\'').then(() => console.log('\''node:sqlite ok'\''))" && sqlite3 --version && test -f /opt/soul-gateway/src/index.mjs'

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: assistos
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Build metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.IMAGE_NAME }}
          tags: |
            type=raw,value=${{ env.IMAGE_TAG }}
            type=raw,value=${{ env.IMAGE_TAG }}-${{ steps.source.outputs.sha }}

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: ./sources/proxies/soul-gateway
          file: ./images/soul-gateway/Dockerfile
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          provenance: false
```

- [x] **Step 5: Update README**

Add this row to the image table:

```markdown
| `assistos/soul-gateway:node24-sqlite` | `PloinkyRepos/proxies` | `soul-gateway` | `images/soul-gateway/Dockerfile` | `publish-soul-gateway-image.yml` |
```

Add this manual publishing command:

```bash
gh workflow run publish-soul-gateway-image.yml \
  --repo AssistOS-AI/container-image-builds \
  -f source_ref=main \
  -f image_tag=node24-sqlite
```

- [x] **Step 6: Verify tests pass**

Run:

```bash
cd /Users/danielsava/work/file-parser/container-image-builds
node --test tests/image-definitions.test.mjs
```

Expected: PASS.

---

## Task 2: Convert Manifest and Startup to Single-Agent SQLite Runtime

**Files:**
- Modify: `proxies/soul-gateway/manifest.json`
- Modify: `proxies/soul-gateway/startup.sh`
- Modify: `proxies/soul-gateway/install.sh`
- Modify: `proxies/soul-gateway/package.json`
- Modify: `proxies/soul-gateway/package-lock.json`

- [x] **Step 1: Remove Postgres dependency from manifest**

Change:

```json
"container": "docker.io/assistos/ploinky-node:24-bookworm-tools",
"agent": "bash /code/startup.sh",
"cli": "bash /code/cli.sh",
"enable": ["postgres"],
```

to:

```json
"container": "docker.io/assistos/soul-gateway:node24-sqlite",
"agent": "bash /opt/soul-gateway/startup.sh",
"cli": "bash /opt/soul-gateway/cli.sh",
```

Remove `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, and `PGDATABASE` env entries.

- [x] **Step 2: Add SQLite env and volume**

Add this env entry inside the default profile:

```json
"SQLITE_PATH": {
  "required": false,
  "default": "/data/soul-gateway.sqlite3",
  "description": "SQLite database path inside the Soul Gateway agent container"
}
```

Add a top-level volume declaration:

```json
"volumes": {
  ".ploinky/data/soul-gateway": "/data"
}
```

Keep `ports: []`, `SOUL_GATEWAY_API_KEY.sharedGeneratedSecret`, and all `httpServices` unchanged.

- [x] **Step 3: Rewrite startup path defaults**

In `startup.sh`, set:

```bash
IMAGE_APP_DIR="${SOUL_GATEWAY_IMAGE_APP_DIR:-/opt/soul-gateway}"
CODE_DIR="${CODE_DIR:-/code}"
APP_DIR="${APP_DIR:-/app}"
DATA_DIR="${DATA_DIR:-/data}"
CREDENTIALS_DIR="${CREDENTIALS_DIR:-$DATA_DIR/credentials}"
SQLITE_PATH="${SQLITE_PATH:-$DATA_DIR/soul-gateway.sqlite3}"
```

Remove the block that constructs `DATABASE_URL`. Add:

```bash
mkdir -p "$DATA_DIR" "$CREDENTIALS_DIR" "$APP_DIR"
export DATA_DIR
export CREDENTIALS_DIR
export SQLITE_PATH
export PORT="${PORT:-7000}"
export HOST="${HOST:-0.0.0.0}"

echo "SQLITE_PATH=$SQLITE_PATH"
echo "PORT=$PORT HOST=$HOST"
```

Keep source-copy behavior for development, but prefer baked image dependencies:

```bash
for candidate in "$IMAGE_APP_DIR/node_modules" /code/node_modules /Agent/node_modules; do
    if [ -d "$candidate" ]; then
        echo "Using prepared runtime dependencies from $candidate"
        rm -rf "$APP_DIR/node_modules"
        ln -s "$candidate" "$APP_DIR/node_modules"
        return
    fi
done
```

- [x] **Step 4: Update install key path**

In `install.sh`, use `/data` defaults and write the encryption key to `$DATA_DIR/encryption.key`, matching `ensureEncryptionKey`.

- [x] **Step 5: Remove `pg` package**

Run:

```bash
cd /Users/danielsava/work/file-parser/proxies/soul-gateway
npm uninstall pg
```

Expected: `package.json` no longer lists `pg`, and `package-lock.json` no longer lists `node_modules/pg` or `postgres-*` parser packages.

---

## Task 3: Add SQLite Database Facade and Fresh Schema

**Files:**
- Create: `proxies/soul-gateway/src/db/sqlite-db.mjs`
- Create: `proxies/soul-gateway/src/db/schema/sqlite-current.sql`
- Modify: `proxies/soul-gateway/src/bootstrap.mjs`
- Modify: `proxies/soul-gateway/src/shutdown.mjs`
- Delete or leave unused: `proxies/soul-gateway/src/db/advisory-lock.mjs`
- Replace or simplify: `proxies/soul-gateway/src/db/migrator.mjs`
- Replace or delete: `proxies/soul-gateway/src/db/pool.mjs`

- [x] **Step 1: Add a failing SQLite smoke test**

Create `proxies/soul-gateway/src/test/integration/sqlite-db.test.mjs`:

```js
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { openDatabase, initializeSchema } from '../../db/sqlite-db.mjs';

describe('sqlite database', () => {
    it('opens a fresh database, initializes schema, and returns pg-style rows', async () => {
        const dir = await mkdtemp(join(tmpdir(), 'soul-sqlite-'));
        try {
            const db = await openDatabase({ SQLITE_PATH: join(dir, 'gateway.sqlite3') });
            await initializeSchema(db);
            const result = await db.query('SELECT name FROM sqlite_master WHERE type = $1 ORDER BY name', ['table']);
            assert.ok(result.rows.some((row) => row.name === 'api_keys'));
            assert.ok(result.rows.some((row) => row.name === 'audit_logs'));
            await db.end();
        } finally {
            await rm(dir, { recursive: true, force: true });
        }
    });
});
```

- [x] **Step 2: Run the smoke test and confirm failure**

Run:

```bash
cd /Users/danielsava/work/file-parser/proxies/soul-gateway
node --experimental-test-module-mocks --test src/test/integration/sqlite-db.test.mjs
```

Expected: FAIL because `sqlite-db.mjs` does not exist.

- [x] **Step 3: Implement `sqlite-db.mjs`**

Use this shape:

```js
import { DatabaseSync } from 'node:sqlite';
import { mkdir, readFile } from 'node:fs/promises';
import { dirname } from 'node:path';

const JSON_COLUMNS = new Set([
    'metadata', 'settings', 'capabilities', 'tags', 'rate_limit_override',
    'budget_override', 'loop_override', 'response_filter_override',
    'retry_policy', 'default_settings', 'facts_json',
    'recent_fingerprints', 'recent_similarity', 'retry_trace',
    'middleware_trace', 'request_headers', 'request_payload',
    'response_payload', 'flags',
]);

const BOOLEAN_COLUMNS = new Set([
    'enabled', 'supports_streaming', 'supports_tools',
    'supports_messages_api', 'supports_responses_api', 'is_free',
    'case_sensitive', 'cache_hit', 'blocked', 'loop_detected',
    'truncated', 'slow', 'oversized', 'streaming', 'retryable',
    'cascaded', 'budget_exempt',
]);

const BLOB_COLUMNS = new Set([
    'key_hash', 'key_ciphertext', 'key_iv', 'key_auth_tag',
    'secret_ciphertext', 'secret_iv', 'secret_auth_tag',
]);

export async function openDatabase(env) {
    const sqlitePath = env.SQLITE_PATH || './data/soul-gateway.sqlite3';
    await mkdir(dirname(sqlitePath), { recursive: true });
    const raw = new DatabaseSync(sqlitePath, { timeout: 5000 });
    raw.exec('PRAGMA foreign_keys = ON');
    raw.exec('PRAGMA journal_mode = WAL');
    raw.exec('PRAGMA synchronous = NORMAL');
    raw.exec('PRAGMA busy_timeout = 5000');
    return new SqliteDb(raw);
}

export async function initializeSchema(db) {
    const schemaPath = new URL('./schema/sqlite-current.sql', import.meta.url);
    const sql = await readFile(schemaPath, 'utf8');
    await db.exec(sql);
}

export class SqliteDb {
    constructor(raw) {
        this.raw = raw;
    }

    async exec(sql) {
        this.raw.exec(sql);
    }

    async query(sql, params = []) {
        const translated = translatePlaceholders(sql);
        const stmt = this.raw.prepare(translated);
        const normalizedParams = params.map(toSqliteValue);
        const trimmed = sql.trim().toUpperCase();
        if (trimmed.startsWith('SELECT') || /\bRETURNING\b/i.test(sql)) {
            const rows = stmt.all(...normalizedParams).map(normalizeRow);
            return { rows, rowCount: rows.length };
        }
        const result = stmt.run(...normalizedParams);
        return { rows: [], rowCount: result.changes ?? 0 };
    }

    async connect() {
        return new SqliteClient(this);
    }

    async end() {
        this.raw.close();
    }
}

class SqliteClient {
    constructor(db) {
        this.db = db;
    }

    query(sql, params = []) {
        return this.db.query(sql, params);
    }

    release() {}
}

function translatePlaceholders(sql) {
    return sql.replace(/\$(\d+)/g, '?');
}

function toSqliteValue(value) {
    if (value === undefined) return null;
    if (Buffer.isBuffer(value)) return value;
    if (value instanceof Uint8Array) return Buffer.from(value);
    if (value instanceof Date) return value.toISOString();
    return value;
}

function normalizeRow(row) {
    const out = {};
    for (const [key, value] of Object.entries(row)) {
        if (value == null) {
            out[key] = value;
        } else if (JSON_COLUMNS.has(key) && typeof value === 'string') {
            out[key] = parseJson(value, key);
        } else if (BOOLEAN_COLUMNS.has(key)) {
            out[key] = Boolean(value);
        } else if (BLOB_COLUMNS.has(key) && value instanceof Uint8Array && !Buffer.isBuffer(value)) {
            out[key] = Buffer.from(value);
        } else {
            out[key] = value;
        }
    }
    return out;
}

function parseJson(value, key) {
    try {
        return JSON.parse(value);
    } catch (err) {
        throw new Error(`Invalid JSON in SQLite column ${key}: ${err.message}`);
    }
}
```

- [x] **Step 4: Add fresh SQLite schema**

Create `src/db/schema/sqlite-current.sql` with current tables only. Use `TEXT PRIMARY KEY` ids generated by JS, `BLOB` encrypted fields, JSON as `TEXT`, and `CURRENT_TIMESTAMP` defaults. Include these required pragmas and tables:

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    key_hash BLOB NOT NULL UNIQUE,
    key_ciphertext BLOB NOT NULL,
    key_iv BLOB NOT NULL,
    key_auth_tag BLOB NOT NULL,
    key_hint TEXT NOT NULL,
    rpm_limit INTEGER NOT NULL DEFAULT 60 CHECK (rpm_limit > 0),
    tpm_limit INTEGER NOT NULL DEFAULT 100000 CHECK (tpm_limit > 0),
    daily_budget_usd REAL,
    monthly_budget_usd REAL,
    expires_at TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    last_used_at TEXT,
    metadata TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TEXT,
    CHECK (daily_budget_usd IS NULL OR daily_budget_usd >= 0),
    CHECK (monthly_budget_usd IS NULL OR monthly_budget_usd >= 0)
);

CREATE INDEX IF NOT EXISTS api_keys_status_expires_idx ON api_keys (status, expires_at);
CREATE INDEX IF NOT EXISTS api_keys_last_used_idx ON api_keys (last_used_at DESC);
```

Continue the schema for all current tables from DS006 and `004-unified-model-bindings.sql`, excluding old `tiers`, `tier_models`, `middleware_assignments`, and legacy import-only tables. For JSON arrays such as `models.tags`, store JSON text with default `'[]'` and validate with `json_valid(tags)`.

- [x] **Step 5: Wire bootstrap to SQLite**

Change imports in `src/bootstrap.mjs`:

```js
import { openDatabase, initializeSchema } from './db/sqlite-db.mjs';
```

Replace database boot with:

```js
const db = await openDatabase(env);
await initializeSchema(db);
log.info('sqlite database initialized', { path: env.SQLITE_PATH });
```

Create app context with `pool: db` for compatibility during the DAO refactor.

- [x] **Step 6: Update shutdown**

Change comments from "pg pool" to "database", and keep:

```js
await appCtx.pool.end();
```

- [x] **Step 7: Verify the smoke test passes**

Run:

```bash
cd /Users/danielsava/work/file-parser/proxies/soul-gateway
node --experimental-test-module-mocks --test src/test/integration/sqlite-db.test.mjs
```

Expected: PASS.

---

## Task 4: Convert DAOs and Direct SQL

**Files:**
- Modify all files in `proxies/soul-gateway/src/db/dao/`
- Modify `proxies/soul-gateway/src/db/dao/helpers/query-builder.mjs`
- Modify `proxies/soul-gateway/src/runtime/registry/snapshot-loader.mjs`
- Modify `proxies/soul-gateway/src/observability/metrics-service.mjs`
- Modify `proxies/soul-gateway/src/runtime/policy/spend-cache.mjs`
- Modify `proxies/soul-gateway/src/management/models-route.mjs`
- Modify `proxies/soul-gateway/src/runtime/providers/account-pool.mjs`
- Modify `proxies/soul-gateway/src/runtime/providers/api-key-account.mjs`
- Modify `proxies/soul-gateway/src/runtime/providers/oauth-manager.mjs`
- Modify `proxies/soul-gateway/src/request/session.mjs`

- [x] **Step 1: Add DAO integration tests for the riskiest flows**

Create tests that use a temp SQLite DB and real DAO calls:

```js
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { openDatabase, initializeSchema } from '../../db/sqlite-db.mjs';
import * as apiKeysDao from '../../db/dao/api-keys-dao.mjs';
import * as providersDao from '../../db/dao/providers-dao.mjs';
import * as modelsDao from '../../db/dao/models-dao.mjs';
import * as sessionsDao from '../../db/dao/sessions-dao.mjs';
import * as auditLogsDao from '../../db/dao/audit-logs-dao.mjs';

async function withDb(fn) {
    const dir = await mkdtemp(join(tmpdir(), 'soul-dao-'));
    const db = await openDatabase({ SQLITE_PATH: join(dir, 'gateway.sqlite3') });
    try {
        await initializeSchema(db);
        return await fn(db);
    } finally {
        await db.end();
        await rm(dir, { recursive: true, force: true });
    }
}

describe('SQLite DAO integration', () => {
    it('creates API key, provider, model, implicit session, and audit row', async () => {
        await withDb(async (db) => {
            const key = await apiKeysDao.create(db, {
                label: 'test',
                keyHash: Buffer.from('hash'),
                keyCiphertext: Buffer.from('cipher'),
                keyIv: Buffer.alloc(12),
                keyAuthTag: Buffer.alloc(16),
                keyHint: 'sk...test',
                metadata: { purpose: 'integration' },
            });
            assert.equal(key.metadata.purpose, 'integration');

            const provider = await providersDao.create(db, {
                providerKey: 'openrouter',
                displayName: 'OpenRouter',
                kind: 'external_api',
                adapterKey: 'openai-api',
                authStrategy: 'api_key',
                baseUrl: 'https://openrouter.ai/api/v1',
                enabled: true,
                settings: { extra_headers: { 'X-Test': '1' } },
            });
            assert.equal(provider.settings.extra_headers['X-Test'], '1');

            const model = await modelsDao.create(db, {
                modelKey: 'openrouter/test',
                displayName: 'Test Model',
                providerId: provider.id,
                providerModelId: 'test/model',
                executionKind: 'provider_model',
                capabilities: { supportsTools: true },
                tags: ['chat'],
            });
            assert.deepEqual(model.tags, ['chat']);

            const sessionResult = await sessionsDao.findOrCreateImplicit(db, {
                apiKeyId: key.id,
                agentName: 'agent',
                timeoutMinutes: 30,
            });
            assert.equal(sessionResult.created, true);

            const audit = await auditLogsDao.insertStart(db, {
                startedAt: new Date().toISOString(),
                requestId: 'req-1',
                requestFormat: 'openai_chat',
                apiKeyId: key.id,
                requestedModel: model.model_key,
                requestHeaders: { authorization: '[redacted]' },
                requestPayload: { model: model.model_key },
            });
            assert.equal(audit.request_payload.model, model.model_key);
        });
    });
});
```

- [x] **Step 2: Replace Postgres functions**

Apply these SQL conversions consistently:

```text
soul_gateway.table                    -> table
now()                                 -> CURRENT_TIMESTAMP
COUNT(*)::int                         -> COUNT(*)
COALESCE(SUM(x), 0)::float            -> COALESCE(SUM(x), 0)
ILIKE $n                              -> LIKE $n COLLATE NOCASE
date_trunc('hour', started_at...)     -> strftime('%Y-%m-%dT%H:00:00.000Z', started_at)
date_trunc('day', started_at...)      -> strftime('%Y-%m-%dT00:00:00.000Z', started_at)
date_trunc('week', started_at...)     -> date(started_at, 'weekday 1', '-7 days')
COUNT(*) FILTER (WHERE condition)     -> SUM(CASE WHEN condition THEN 1 ELSE 0 END)
last_activity_at > now() - interval   -> last_activity_at > datetime('now', '-' || $n || ' minutes')
NULLS FIRST                           -> ORDER BY target_id IS NOT NULL, target_id
unnest(tags)                          -> json_each(tags)
```

- [x] **Step 3: Generate ids in JS**

In each DAO `create()` function, set `id = randomUUID()` when no id is supplied:

```js
import { randomUUID } from 'node:crypto';

const id = fields.id || randomUUID();
```

Insert the id explicitly. Do not rely on database UUID defaults.

- [x] **Step 4: Rewrite implicit session creation**

Replace Postgres advisory-lock logic with a SQLite write transaction:

```js
await client.query('BEGIN IMMEDIATE');
try {
    const existing = await client.query(
        `SELECT *
         FROM sessions
         WHERE api_key_id = $1
           AND agent_name = $2
           AND explicit_session_id IS NULL
           AND status = 'open'
           AND last_activity_at > datetime('now', '-' || $3 || ' minutes')
         ORDER BY last_activity_at DESC
         LIMIT 1`,
        [apiKeyId, agentName, String(timeoutMinutes)]
    );
    if (existing.rows[0]) {
        await client.query('COMMIT');
        return { session: existing.rows[0], created: false };
    }

    const seqResult = await client.query(
        `SELECT COALESCE(MAX(sequence_no), 0) + 1 AS seq
         FROM sessions
         WHERE group_key = $1`,
        [groupKey]
    );
    const sequenceNo = seqResult.rows[0]?.seq || 1;
    const inserted = await client.query(
        `INSERT INTO sessions
            (id, group_key, group_display, sequence_no, api_key_id, soul_id, agent_name)
         VALUES ($1, $2, $3, $4, $5, $6, $7)
         RETURNING *`,
        [randomUUID(), groupKey, `${agentName} #${sequenceNo}`, sequenceNo, apiKeyId, soulId, agentName]
    );
    await client.query('COMMIT');
    return { session: inserted.rows[0], created: true };
} catch (err) {
    await client.query('ROLLBACK');
    throw err;
}
```

- [x] **Step 5: Replace audit partition functions**

Make `ensurePartition()` a no-op that returns `'audit_logs'` for compatibility. Replace `dropExpiredPartitions(pool, cutoffDate)` with:

```js
export async function dropExpiredPartitions(pool, cutoffDate) {
    const result = await pool.query(
        `DELETE FROM audit_logs WHERE started_at < $1`,
        [cutoffDate.toISOString()]
    );
    return result.rowCount > 0 ? ['audit_logs'] : [];
}
```

Rename later if desired, but keep the export during the first refactor to reduce call-site churn.

- [x] **Step 6: Replace tags query**

In `management/models-route.mjs`, replace:

```sql
SELECT DISTINCT unnest(tags) AS tag FROM soul_gateway.models ORDER BY tag ASC
```

with:

```sql
SELECT DISTINCT json_each.value AS tag
FROM models, json_each(models.tags)
WHERE json_each.value IS NOT NULL AND json_each.value <> ''
ORDER BY tag ASC
```

- [x] **Step 7: Run DAO integration tests**

Run:

```bash
cd /Users/danielsava/work/file-parser/proxies/soul-gateway
node --experimental-test-module-mocks --test src/test/integration/sqlite-db.test.mjs src/test/integration/sqlite-dao.test.mjs
```

Expected: PASS.

---

## Task 5: Make Runtime Persistent by Default

**Files:**
- Modify `proxies/soul-gateway/src/bootstrap/service-installers.mjs`
- Modify `proxies/soul-gateway/src/bootstrap/local-llm-bootstrap.mjs`
- Modify `proxies/soul-gateway/src/bootstrap/soul-gateway-provider-bootstrap.mjs`
- Modify `proxies/soul-gateway/src/runtime/route/authenticate.mjs`
- Modify `proxies/soul-gateway/src/runtime/route/resolve-session.mjs`
- Modify `proxies/soul-gateway/src/background/scheduler.mjs`
- Modify `proxies/soul-gateway/src/runtime/security/api-key-auth.mjs`

- [x] **Step 1: Replace `env.DATABASE_URL` gates**

Every place that currently means "persistent DB is available" should use:

```js
const hasPersistentDb = Boolean(appCtx.pool);
```

or, inside middleware:

```js
const hasDb = Boolean(pool);
```

Do not keep `DATABASE_URL` as the feature flag.

- [x] **Step 2: Preserve explicit no-db test behavior**

If tests need synthetic no-db mode, build app contexts with `pool: null`. Do not set fake `DATABASE_URL`.

- [x] **Step 3: Update workspace default key persistence**

In `api-key-auth.mjs`, change:

```js
const hasPersistentDb = appCtx.pool && env.DATABASE_URL;
```

to:

```js
const hasPersistentDb = Boolean(appCtx.pool);
```

Keep duplicate handling, but recognize SQLite uniqueness errors as well as Postgres `23505`:

```js
if (err?.code === 'SQLITE_CONSTRAINT_UNIQUE' || err?.code === '23505') {
    const row = await apiKeysDao.findByHash(appCtx.pool, keyHash);
    if (row) return normalizeWorkspaceApiKeyRecord(row);
}
```

- [x] **Step 4: Run route and auth tests**

Run:

```bash
cd /Users/danielsava/work/file-parser/proxies/soul-gateway
node --experimental-test-module-mocks --test \
  src/test/unit/embedded-auth.test.mjs \
  src/test/unit/service-installers.test.mjs \
  src/test/unit/local-llm-bootstrap.test.mjs \
  src/test/unit/soul-gateway-provider-bootstrap.test.mjs
```

Expected: PASS after tests are updated to use `pool` presence instead of `DATABASE_URL`.

---

## Task 6: Update Deploy and Admin Workflows

**Files:**
- Modify `proxies/.github/workflows/deploy-soul-gateway.yml`
- Modify `proxies/.github/workflows/soul-gateway-admin.yml`
- Modify `proxies/soul-gateway/deploy.sh`

- [x] **Step 1: Remove PG secrets and env writes**

In `deploy-soul-gateway.yml`, remove `PGPASSWORD=${{ secrets.SG_PGPASSWORD }}` from `/tmp/soul_env`.

Remove:

```bash
"$PLOINKY" var PGHOST "10.0.2.2"
"$PLOINKY" var PGPORT "5432"
"$PLOINKY" var PGUSER "postgres"
"$PLOINKY" var PGPASSWORD "$PGPASSWORD"
"$PLOINKY" var PGDATABASE "$SOUL_DATABASE"
```

Remove `SOUL_DATABASE="soul_gateway_v2"`.

- [x] **Step 2: Remove Postgres startup block**

Delete the old Postgres data copy and the "Wait for postgres" block from deploy workflow lines that migrate `postgres/data`, patch `pg_hba.conf`, set password, and create database.

- [x] **Step 3: Add SQLite verification**

After health succeeds, add:

```bash
SOUL_CONTAINER=$(podman ps --filter "name=soul-gateway" --format "{{.Names}}" 2>/dev/null | head -1)
if [ -n "$SOUL_CONTAINER" ]; then
  podman exec "$SOUL_CONTAINER" sh -lc 'test -f "${SQLITE_PATH:-/data/soul-gateway.sqlite3}" && sqlite3 "${SQLITE_PATH:-/data/soul-gateway.sqlite3}" "SELECT name FROM sqlite_master WHERE type='\''table'\'' AND name='\''api_keys'\'';"'
fi
```

- [x] **Step 4: Update status output**

Replace the "Postgres Container" status section with:

```bash
echo "=== Soul Gateway SQLite ==="
CONTAINER=$(podman ps --filter "name=soul-gateway" --format "{{.Names}}" 2>/dev/null | head -1)
if [ -n "$CONTAINER" ]; then
  podman exec "$CONTAINER" sh -lc 'echo "SQLITE_PATH=${SQLITE_PATH:-/data/soul-gateway.sqlite3}"; sqlite3 "${SQLITE_PATH:-/data/soul-gateway.sqlite3}" "SELECT count(*) AS api_keys FROM api_keys;"'
else
  echo "No soul-gateway container found"
fi
```

- [x] **Step 5: Update admin workflow SQL**

Replace the `psql` query in `soul-gateway-admin.yml` with:

```bash
CONTAINER=$(podman ps --filter "name=soul-gateway" --format "{{.Names}}" 2>/dev/null | head -1)
podman exec "$CONTAINER" sh -lc '
  sqlite3 -header -column "${SQLITE_PATH:-/data/soul-gateway.sqlite3}" \
    "SELECT model_key, provider_model_id, enabled FROM models ORDER BY model_key;"
' 2>&1
```

- [x] **Step 6: Verify workflow syntax**

Run:

```bash
cd /Users/danielsava/work/file-parser/proxies
npx --yes yaml-lint .github/workflows/deploy-soul-gateway.yml .github/workflows/soul-gateway-admin.yml
```

Expected: both workflow YAML files parse successfully.

---

## Task 7: Update Docs and Specs

**Files:**
- Modify `proxies/soul-gateway/docs/specs/DS006-database-schema.md`
- Modify `proxies/soul-gateway/docs/specs/DS013-configuration-deployment.md`
- Modify `proxies/soul-gateway/docs/specs/DS016-ploinky-agent-mode.md`
- Modify `proxies/soul-gateway/CLAUDE.md`
- Modify `proxies/soul-gateway/docs/specs/README.md` only if spec summary text references Postgres.

- [x] **Step 1: Rewrite DS006 summary**

Replace Postgres-specific summary with:

```markdown
This spec describes the SQLite tables Soul Gateway uses to persist configuration and audit data. The database file lives at `SQLITE_PATH`, defaulting to `/data/soul-gateway.sqlite3` inside the Ploinky-managed Soul Gateway container. The runtime initializes the current schema on startup. There is no Postgres schema, no separate database agent, and no historical import path in the SQLite deployment.
```

- [x] **Step 2: Update encryption wording**

Replace `bytea` language with:

```markdown
Encrypted columns are SQLite `BLOB` values. The runtime normalizes SQLite `Uint8Array` values back to Node `Buffer` instances before decrypting so encryption callers continue to use raw bytes.
```

- [x] **Step 3: Replace partitioning section**

Use:

```markdown
SQLite stores audit logs in a single indexed `audit_logs` table. The retention job deletes rows older than `LOG_RETENTION_DAYS`; it does not create or drop monthly partitions.
```

- [x] **Step 4: Remove historical import section**

State:

```markdown
The SQLite cutover intentionally starts from an empty database. Old Postgres data and main-branch historical data are not imported.
```

- [x] **Step 5: Update DS013 deployment**

Change the database env table from `DATABASE_URL` and `PG_*` to:

```markdown
| Database | `SQLITE_PATH` |
```

Change startup step 2 to:

```markdown
2. **Open SQLite and initialize schema** - the database file is created under `/data` and schema objects are created if missing.
```

Change health detail to:

```markdown
- the handler probes SQLite with `SELECT 1`
```

Change graceful shutdown step 7 to:

```markdown
7. The SQLite database handle closes.
```

- [x] **Step 6: Update DS016**

Replace "When Postgres is configured" with:

```markdown
When the SQLite database is open, the generated workspace key is idempotently persisted to `api_keys` so request sessions, budgets, and audit rows have a durable key id.
```

- [x] **Step 7: Update production instructions**

Remove "Expected production database: `soul_gateway_v2`" and the instruction to verify `PGDATABASE`. Replace with:

```markdown
- Expected production database file: `/data/soul-gateway.sqlite3` inside the Soul Gateway container.
```

Post-deploy verification should confirm the health endpoint, the Soul Gateway container status, absence of a Ploinky Postgres dependency, and that the SQLite file exists.

---

## Task 8: Full Verification and Rollout

**Files:**
- No new source files unless verification reveals missing tests.

- [x] **Step 1: Search for remaining Postgres references**

Run:

```bash
cd /Users/danielsava/work/file-parser
rg -n "Postgres|postgres|PGHOST|PGPORT|PGUSER|PGPASSWORD|PGDATABASE|DATABASE_URL|pg_advisory|date_trunc|jsonb|bytea|timestamptz|soul_gateway\\." proxies/soul-gateway proxies/.github/workflows container-image-builds -S
```

Expected: only historical notes that explicitly explain removal, if any. No runtime code should depend on these terms.

- [x] **Step 2: Run Soul Gateway tests**

Run:

```bash
cd /Users/danielsava/work/file-parser/proxies/soul-gateway
npm test
```

Expected: PASS.

- [x] **Step 3: Run image repo tests**

Run:

```bash
cd /Users/danielsava/work/file-parser/container-image-builds
node --test tests/image-definitions.test.mjs
```

Expected: PASS.

- [ ] **Step 4: Publish image**

Run from any directory with GitHub CLI authenticated:

```bash
gh workflow run publish-soul-gateway-image.yml \
  --repo AssistOS-AI/container-image-builds \
  -f source_ref=main \
  -f image_tag=node24-sqlite
```

Expected: workflow publishes `assistos/soul-gateway:node24-sqlite` and `assistos/soul-gateway:node24-sqlite-<sourceSha>`.

- [ ] **Step 5: Deploy Soul Gateway**

Run:

```bash
gh workflow run deploy-soul-gateway.yml \
  --repo PloinkyRepos/proxies \
  -f action=deploy
```

Expected: workflow starts only the Soul Gateway agent container, health returns HTTP 200 with `db: true`, and no Postgres container is required.

- [ ] **Step 6: Production smoke checks**

Use read-only checks:

```bash
ssh -i ~/proxies_server_private_key.pem admin@45.136.70.141 'cd ~/soulGateway && ploinky status'
ssh -i ~/proxies_server_private_key.pem admin@45.136.70.141 'curl -s http://localhost:8080/public-services/soul-gateway-health/'
ssh -i ~/proxies_server_private_key.pem admin@45.136.70.141 'podman ps --format "table {{.Names}}\t{{.Status}}"'
ssh -i ~/proxies_server_private_key.pem admin@45.136.70.141 'podman exec $(podman ps --filter "name=soul-gateway" --format "{{.Names}}" | head -1) sh -lc "test -f ${SQLITE_PATH:-/data/soul-gateway.sqlite3} && sqlite3 ${SQLITE_PATH:-/data/soul-gateway.sqlite3} \"SELECT count(*) FROM api_keys;\""'
```

Expected: Soul Gateway is running, health includes `db: true`, SQLite file exists, and the key table is queryable.

---

## Known Risk Areas

- JSON normalization is required. Node SQLite returns JSON text, while the current runtime expects objects and arrays.
- BLOB normalization is required. Node SQLite can return `Uint8Array`; encryption expects `Buffer`.
- Session creation must use `BEGIN IMMEDIATE` instead of Postgres advisory locks.
- Audit log partition maintenance must become row retention.
- Metrics queries need SQLite date bucketing.
- Tests that currently assert Postgres SQL strings must be rewritten around behavior.
- The image smoke test is mandatory because local Docker is unavailable in this workspace.

## Self-Review Checklist

- [ ] Manifest has no `enable: ["postgres"]`.
- [ ] No runtime code imports `pg`.
- [ ] `package.json` has no `pg` dependency.
- [ ] Fresh startup creates `/data/soul-gateway.sqlite3`.
- [ ] Health checks SQLite with `SELECT 1`.
- [ ] Generated workspace API key persists in SQLite.
- [ ] Provider bootstrap still creates provider/account/model rows.
- [ ] Public `/v1/*` auth still uses Soul Gateway API keys.
- [ ] Management routes remain protected by Ploinky router auth.
- [ ] Image contains `sqlite3`, Node SQLite support, `src/`, scripts, and production dependencies.
- [ ] Deploy workflow contains no PG vars, no psql, and no Postgres container wait.
- [ ] Docs no longer instruct operators to verify `PGDATABASE=soul_gateway_v2`.
