# Ploinky + AssistOSExplorer: context tehnic pentru extinderea modelului de securitate

Acest document este un handoff high-level, dar detaliat, pentru o sesiune noua de ChatGPT. Scopul lui este sa ofere context suficient despre Ploinky, agentii Ploinky si AssistOSExplorer, astfel incat discutia urmatoare sa se poata concentra pe extinderea modelului de securitate la cinci tipuri de acces:

1. endpointuri complet publice;
2. endpointuri publice protejate prin token anonim temporar;
3. endpointuri autentificate cu utilizator/JWT;
4. endpointuri MCP interne intre agenti;
5. endpointuri MCP administrative.

Documentul separa explicit ce este observat in cod/spec-uri de ce este propunere sau directie de design.

## 1. Rezumat executiv

Ploinky este runtime-ul local care porneste si conecteaza agenti izolati. Din perspectiva aplicatiei, Ploinky are un Router public, iar agentii ruleaza ca procese/container-e locale, expuse catre client prin rute de forma `/<agent>/...`. Routerul citeste registrul runtime din `.ploinky/routing.json`, aplica autentificare/autorizare la nivel de ruta si redirectioneaza cererile catre portul local al agentului corespunzator.

Un agent Ploinky este o unitate declarata prin `manifest.json`: are comanda de start, imagine/container sau sandbox local, env vars, volume, dependinte, servicii HTTP expuse prin Router si/sau un server MCP/OpenAI-compatible. Agentii pot fi compusi prin `enable[]`: agentul Explorer porneste o intreaga familie de agenti dependenti, precum `gitAgent`, `dpuAgent`, `soplangAgent`, `tasksAgent`, `llmAssistant`, `webAssist`, `webmeetAgent`, `onlyOffice`, `multimedia`, `liveKitServerAgent`, `webmeetStt`, `AchillesCLI` si `soul-gateway`.

AssistOSExplorer este aplicatia/IDE-ul principal din acest workspace. Agentul `explorer` serveste UI-ul static, navigarea prin fisiere, preview/editare documente, integrarea pluginurilor si delega operatiile de domeniu catre agenti specializati prin MCP sau servicii HTTP. Explorer nu trebuie sa devina owner-ul tuturor operatiilor sensibile: DPU detine date confidentiale/secrete/ACL, GitAgent detine fluxuri Git, SoplangAgent detine build/skill execution, TasksAgent detine backlog, WebMeetAgent detine intalniri, OnlyOffice detine Document Server runtime, etc.

Modelul curent de securitate are deja patru idei mari:

- Routerul este brokerul de incredere pentru acces HTTP, sesiuni, guest sessions si minting de invocation JWT-uri.
- Agentii primesc `PLOINKY_DERIVED_MASTER_KEY`, nu `PLOINKY_MASTER_KEY`; cheia derivata permite verificarea/minting-ul invocation JWT-urilor, dar nu decriptarea magazinelor `.secrets` sau minting-ul sesiunilor de utilizator.
- MCP execution foloseste "secure wire": Routerul mintage un JWT scurt, cu audience, caller, tool, scope, body hash, user si replay protection; AgentServer verifica tokenul inainte sa execute tool-uri.
- Izolarea container/sandbox, volumele sub `.ploinky/`, stripping-ul headerelor de identitate si filtrarea fisierelor sunt aparari de adancime, nu un model hostile multitenant complet.

Extinderea la cele cinci tipuri de acces este aliniata cu o specificatie existenta propusa in Ploinky (`DS013-router-whitelist-public-access.md`), dar nu pare complet implementata. Punctul central de design ar trebui sa fie: Routerul trebuie sa decida clasa de acces pentru fiecare ruta HTTP/MCP, iar agentii trebuie sa continue sa aplice autorizarea de domeniu pentru operatiile lor.

## 2. Surse analizate

Ploinky:

- `ploinky/docs/ploinky-overview.md`
- `ploinky/docs/specs/DS003-agent-manifest-and-registry.md`
- `ploinky/docs/specs/DS004-runtime-execution-and-isolation.md`
- `ploinky/docs/specs/DS005-routing-and-web-surfaces.md`
- `ploinky/docs/specs/DS006-auth-capabilities-and-secure-wire.md`
- `ploinky/docs/specs/DS011-security-model.md`
- `ploinky/docs/specs/DS013-router-whitelist-public-access.md`
- `ploinky/cli/server/RoutingServer.js`
- `ploinky/cli/server/authHandlers.js`
- `ploinky/cli/server/httpServiceRoutes.js`
- `ploinky/cli/server/routerHandlers.js`
- `ploinky/cli/server/mcp-proxy/index.js`
- `ploinky/cli/server/mcp-proxy/invocationMinter.js`
- `ploinky/Agent/server/AgentServer.mjs`
- `ploinky/Agent/lib/invocationAuth.mjs`

AssistOSExplorer si agentii sai:

- `AssistOSExplorer/CLAUDE.md`
- `AssistOSExplorer/docs/specs/*`
- `AssistOSExplorer/explorer/manifest.json`
- `AssistOSExplorer/explorer/**/*`
- `AssistOSExplorer/dpuAgent/**/*`
- `AssistOSExplorer/gitAgent/**/*`
- `AssistOSExplorer/llmAssistant/**/*`
- `AssistOSExplorer/multimedia/**/*`
- `AssistOSExplorer/onlyOffice/**/*`
- `AssistOSExplorer/soplangAgent/**/*`
- `AssistOSExplorer/tasksAgent/**/*`
- `AssistOSExplorer/webAssist/**/*`
- `AssistOSExplorer/webmeetAgent/**/*`
- `AssistOSExplorer/webmeetLivekitAiAgent/**/*`
- `AssistOSExplorer/webmeetStt/**/*`
- `AchillesCLI/achilles-cli/**/*`
- `webmeetInfra/liveKitServerAgent/**/*`

## 3. Ce este Ploinky

Ploinky este un runtime de agenti pentru un workspace local. El creeaza un director runtime `.ploinky/`, rezolva manifestele agentilor, porneste agentii in container/sandbox, scrie tabela de rutare si expune un Router central care primeste traficul browserului sau al altor clienti.

Componentele principale:

- CLI/runtime: `ploinky start` rezolva graful de dependinte, porneste agentii si Routerul.
- Registru runtime: `.ploinky/agents.json` tine agentii enabled; `.ploinky/routing.json` tine rutele efective si porturile locale.
- Router/Watchdog: `cli/server/Watchdog.js` supravegheaza routerul, iar `cli/server/RoutingServer.js` aplica rute, auth si proxy.
- AgentServer: libraria comuna din `ploinky/Agent/server/AgentServer.mjs` pentru agentii MCP/OpenAI-compatible.
- Secret/runtime state: `.ploinky/.secrets`, `.ploinky/keys`, `.ploinky/logs`, `.ploinky/transcripts`, `.ploinky/repos`, `.ploinky/deps`, `.ploinky/data`.

Suprafete importante expuse de Router:

- `/health`: health-check public.
- `/MCPBrowserClient.js`: asset public pentru client MCP.
- `/auth/*`: login/logout/session.
- `/dashboard`, `/status`, `/webtty`, `/webchat`, `/webmeet`: suprafete web Ploinky.
- `/upload`, `/blobs`, `/workspace-files`: upload si fisiere mediate prin Router.
- `/mcp`: MCP agregat/router-level.
- `/<agent>/mcp`: MCP catre agentul tinta.
- `/<agent>/v1/chat/completions`: endpoint OpenAI-compatible catre agent.
- `/<agent>/...`: proxy transparent catre agent.
- `/services/...` si `/public-services/...`: servicii HTTP declarate de agenti prin `httpServices`.
- `/agent-card`: descrieri/metadata despre agenti; in cod exista si o ruta agregata publica.

Observatie importanta pentru securitate: Ploinky este proiectat pentru workspace local / operator unic / echipa de incredere. Documentatia curenta spune explicit ca nu este inca un sistem hostile multitenant pentru internet public fara hardening suplimentar.

## 4. Ce este un agent Ploinky

Un agent Ploinky este o aplicatie declarata prin `manifest.json`. Manifestul stabileste cum se porneste agentul, cum este izolat, ce porturi asculta, ce alte agenti activeaza si ce servicii expune.

Elemente tipice de manifest:

- `agent`: comanda de start, de exemplu `node /code/src/index.mjs`.
- `container`: imaginea Docker/Podman folosita.
- `lite-sandbox`: permite sandbox local pentru anumite profile.
- `profiles`: override-uri pentru `dev`, `qa`, `prod`, `embedded`, `global`, etc.
- `enable`: lista de agenti dependenti care se pornesc impreuna cu agentul principal.
- `httpServices`: servicii HTTP proxy-uite prin Router.
- `env`: variabile de mediu, inclusiv secrete generate si shared secrets.
- `volumes`: mount-uri sub `.ploinky/`.
- `networks`: moduri de retea, inclusiv bridge-uri interne pentru WebMeet.
- `ports`: porturi locale/container.
- `webchat`, `pwd`, `ssoProvider`: configuratii pentru suprafete web si auth.

Un agent poate expune una sau mai multe dintre aceste suprafete:

- UI static prin `/<agent>/...`;
- API HTTP prin `httpServices`;
- MCP tools/resources prin `/<agent>/mcp`;
- API OpenAI-compatible prin `/<agent>/v1/chat/completions`;
- CLI intern sau comanda single-shot.

Ploinky nu ar trebui sa aiba agenti optionali hardcodati in core. Agentii apar prin manifest/registry/routing, iar Routerul ar trebui sa se comporte generic.

## 5. Fluxuri runtime importante

### 5.1 Browser catre UI agent

Flux tipic:

1. Browserul cere `/<agent>/...`.
2. Routerul identifica agentul din ruta si tabela `.ploinky/routing.json`.
3. Routerul decide daca ruta este publica, guest, protejata sau deferata catre MCP.
4. Daca este nevoie, Routerul autentifica utilizatorul sau creeaza o sesiune guest.
5. Routerul face proxy catre portul local al agentului.

Pentru rutele transparente non-MCP, agentul tinta ramane responsabil de autorizarea de domeniu. Autentificarea la nivel de ruta nu este suficienta pentru secrete, fisiere confidentiale, operatii admin sau actiuni destructive.

### 5.2 Servicii HTTP declarate de agenti

Agentii pot declara `httpServices` in manifest. Fiecare serviciu are:

- `externalPrefix`: ruta externa prin Router;
- `internalPrefix`: ruta interna in agent;
- `auth`: `none`, `guest` sau `protected`;
- optional `guestScope`, `forceGuest`, `invocation`.

Routerul:

- normalizeaza serviciile;
- decide auth mode;
- sterge headerele de identitate venite de la client;
- genereaza `x-ploinky-auth-info`;
- poate minta un invocation JWT pentru serviciu;
- face proxy catre agent.

Exemple:

- Explorer expune `/services/explorer/office/` protejat si `/public-services/explorer/office/` public pentru fluxuri OnlyOffice strict controlate.
- Explorer expune `/services/explorer/avatar-settings/` protejat.
- WebMeet expune `/services/webmeet/` protejat si `/public-services/webmeet/` guest cu `forceGuest:true`.

### 5.3 MCP first-party: user/browser catre agent

Flux tipic:

1. Clientul autentificat apeleaza `/<agent>/mcp`.
2. Pentru discovery (`initialize`, `tools/list`, `resources/list`, `ping`), Routerul poate permite vizibilitate fara token de executie.
3. Pentru `tools/call`, `resources/read` si task status, Routerul mintage un invocation JWT scurt.
4. JWT-ul include agent tinta (`aud`), tool, caller, body hash, user, scope, expiry si jti.
5. AgentServer verifica JWT-ul inainte sa execute tool-ul.

Aceasta este "secure wire": executia MCP este conditionata de un token de invocare mintat de Router si verificat de agent.

### 5.4 MCP delegated: agent catre alt agent

Fluxul curent observat nu foloseste in primul rand un secret static per agent pentru identificare MCP. In schimb:

1. Un agent primeste o cerere MCP valida de la Router, cu invocation JWT.
2. Daca agentul trebuie sa cheme alt agent, trimite catre Router acel token ca `X-Ploinky-Caller-JWT`.
3. Routerul verifica tokenul callerului.
4. Routerul mintage un nou invocation JWT pentru agentul tinta.
5. Agentul tinta verifica noul token.

Identitatea callerului devine un principal de forma `agent:<route-or-name>`, derivat din tokenul validat. Acest model este mai bun decat un header static sau un secret simplu in env, pentru ca are audience, tool, body hash, expirare si protectie la replay.

Totusi, pentru extinderea "MCP interne", lipseste sau este incomplet un policy matrix administrabil care sa spuna explicit: agentul X are voie sa cheme tool-ul Y al agentului Z, cu aceste scopes si numai pentru aceste roluri/utilizatori.

### 5.5 API OpenAI-compatible

Agentii Ploinky pot expune endpointuri de forma `/<agent>/v1/chat/completions`, compatibile cu API-uri OpenAI. In documentatia existenta, aceste rute sunt tratate ca ruta catre agent, iar agentul/Routerul trebuie sa impuna auth adecvat in functie de context.

Riscul relevant pentru discutia viitoare: tool-urile MCP administrative nu trebuie sa devina apelabile implicit prin API-uri OpenAI-compatible, mai ales prin trasee folosite de Soul Gateway sau agenti LLM. Daca un agent are tool-uri admin, acestea trebuie marcate si filtrate explicit.

## 6. Modelul de securitate existent

### 6.1 Trust model

Modelul curent este workspace-local:

- operator unic sau echipa de incredere;
- Routerul si agentii enabled sunt in acelasi trust domain operational;
- containerele/sandbox-urile limiteaza blast radius, dar nu transforma sistemul intr-o platforma hostile multitenant;
- accesul internet-public necesita hardening suplimentar.

Documentatia mentioneaza explicit gap-uri pentru un deployment internet/multitenant:

- bind host explicit;
- TLS/reverse proxy;
- CSRF/origin policy;
- login rate limiting;
- upload quotas;
- hardening dashboard commands;
- izolarea mai stricta a credentialelor per agent.

### 6.2 Chei si secrete

`PLOINKY_MASTER_KEY` este cheia root a workspace-ului. Cine o poate citi poate decripta `.secrets`, minta sesiuni si controla sistemul.

Agentii primesc `PLOINKY_DERIVED_MASTER_KEY`, derivata prin HKDF cu scopul `derived-master`. Aceasta permite verificarea/minting-ul invocation JWT-urilor pentru secure wire, dar nu permite decriptarea magazinelor de secrete sau minting-ul sesiunilor de utilizator.

Manifestele pot declara:

- `generatedSecret`: secret unic generat pentru agent/config;
- `sharedGeneratedSecret`: secret comun intre agenti, de exemplu `SOUL_GATEWAY_API_KEY`, `ONLYOFFICE_JWT_SECRET`, LiveKit keys sau tokenuri interne WebMeet.

Aceste shared secrets exista pentru integrare de servicii, dar pentru autorizarea MCP intre agenti directia existenta este invocation JWT, nu secret static per agent.

### 6.3 Sesiuni autentificate

Routerul foloseste un cookie local `ploinky_jwt` pentru sesiuni de utilizator. JWT-ul contine tip sesiune, user, variabile user, revision, jti si are fereastra de valabilitate limitata.

Surse de identitate:

- user/parola local, configurat prin route variables precum `PLOINKY_AUTH_<ROUTE>_USERS`;
- provider SSO declarat prin agent cu `ssoProvider:true`;
- configuratii speciale precum `webchat.auth`.

Explorer are in manifest `pwd enable` cu useri de dezvoltare `admin/admin` si `user/user`, deci este un exemplu de agent care activeaza autentificare locala pentru UI.

### 6.4 Guest sessions

Routerul suporta sesiuni guest prin `ploinky_guest`. Acestea sunt folosite cand:

- agentul are `guest:true`;
- un `httpService` are `auth:"guest"`;
- o ruta publica protejata vrea identitate anonima temporara si scope.

Guest session poate avea `roles:["guest"]` si `gscope`. Pentru servicii `forceGuest:true`, Routerul ignora o sesiune login existenta si trateaza requestul ca guest. WebMeet foloseste acest comportament pentru linkuri de invitatie, astfel incat linkurile publice sa nu devina accidental operatii de user autentificat.

### 6.5 HTTP auth modes curente

In manifestele `httpServices`, auth mode-ul este:

- `none`: fara identitate; Routerul nu pune o identitate de incredere.
- `guest`: Routerul creeaza/reutilizeaza guest identity si poate minta invocation proof.
- `protected`: Routerul cere identitate autentificata sau fallback la static route auth.

Aceste trei moduri sunt baza curenta pentru primele trei clase din modelul dorit, dar `none` ar trebui restrans prin whitelist daca sistemul devine mai public.

### 6.6 Secure-wire MCP

MCP execution este protejata prin invocation JWT:

- algoritm: HS256 pe cheia derivata;
- issuer: `ploinky-router`;
- audience: agentul tinta;
- caller: router, user sau agent delegat;
- tool/resource: numele operatiei;
- body hash: leaga tokenul de payload;
- user: identitatea userului cand exista;
- expiry scurt: default ~60 secunde;
- replay protection prin `jti`.

AgentServer cere token valid pentru:

- `tools/call`;
- `resources/read`;
- task status.

Discovery poate ramane vizibil:

- `initialize`;
- `tools/list`;
- `resources/list`;
- `ping`.

Aceasta distinctie este importanta: faptul ca un tool apare in lista nu inseamna ca poate fi executat fara autorizare.

### 6.7 Headere de identitate

Routerul sterge headerele de identitate venite de la client, precum `x-ploinky-auth-info` si variante user-related, apoi le regenereaza. Astfel, un client nu poate pretinde direct ca este alt user sau alta sesiune.

Pentru un serviciu HTTP protejat/guest, `x-ploinky-auth-info` este de incredere doar cand vine prin Router si, ideal, este insotit de un invocation proof verificabil.

### 6.8 Fisiere, upload, static assets

AgentServer serveste fisiere statice din code root si verifica traversal/NUL/outside root. Explorer si DPU au reguli suplimentare:

- fisierele `.secrets` si `*.secrets` sunt rezervate/ascunse;
- `/Confidential` este virtual si se rezolva prin DPU, nu prin filesystem normal;
- uploadurile WebChat au scope de sesiune, dar nu sunt considerate o granita de securitate puternica;
- path-urile host absolute nu ar trebui expuse catre browser.

## 7. Mapare catre cele cinci tipuri de acces propuse

### 7.1 Endpointuri complet publice

Stare curenta observata:

- `/health` este public.
- `/MCPBrowserClient.js` este public.
- `/agent-card` are o ruta agregata publica in cod.
- `httpServices` cu `auth:"none"` sunt publice la nivel de Router.
- Explorer foloseste `/public-services/explorer/office/` cu `auth:"none"` pentru callback/document routes OnlyOffice strict controlate.

Problema:

`auth:"none"` este prea larg daca se vrea expunere internet-publica. E nevoie de whitelist explicit, cu metode permise, prefix/exact path, query restrictions si audit.

Directie propusa:

- Un fisier/policy store de tip `.ploinky/router-whitelist.json`.
- Rute publice declarate explicit: exact sau prefix.
- Default `GET/HEAD` pentru public, cu `POST` doar cand este explicit justificat.
- Query params deny by default sau allowlist.
- Denials generice, fara leak de existenta agentului/routei.
- Admin endpoint pentru management whitelist, dar acesta trebuie sa fie auth/admin-only.

### 7.2 Endpointuri publice protejate cu token anonim temporar

Stare curenta observata:

- Ploinky are deja `guest` sessions prin cookie `ploinky_guest`.
- `webAssist` are `guest:true`, deci este potrivit pentru chat public/anonim.
- `webmeetAgent` are `/public-services/webmeet/` cu `auth:"guest"`, `forceGuest:true` si `guestScope:"webmeet-public-service"`.
- Linkurile WebMeet folosesc token de invitatie si guest route; tokenul de invitatie singur nu trebuie sa fie suficient fara ruta guest si invocation proof.

Ce lipseste fata de formularea dorita:

- Un mecanism general explicit "clientul cere token anonim temporar, apoi il trimite la fiecare request" pentru toate endpointurile public-protected.
- Rate limiting si blocare/filtrare automate triviale la nivel generic de Router.
- Politici uniforme de expirare, revocare si scope pe ruta.

Directie propusa:

- Generalizarea guest session ca "anonymous access token".
- Token legat de browser/session, scope de ruta si eventual fingerprint soft.
- Rate limit per route + token + IP.
- Expirare scurta, refresh controlat, revocare in Router.
- `forceGuest` pentru linkuri unde autentificarea userului nu trebuie sa mareasca privilegiile.

### 7.3 Endpointuri autentificate

Stare curenta observata:

- Acesta este modul default pentru rutele protejate.
- Routerul foloseste `ploinky_jwt` pentru utilizator autentificat.
- Explorer activeaza local password auth.
- `/services/explorer/office/`, `/services/explorer/avatar-settings/`, `/services/explorer/axi-face/` sunt protected.
- `/services/webmeet/` este protected.
- `/mcp` si majoritatea `/<agent>/mcp` necesita user auth pentru flow first-party.

Directie propusa:

- Pastrarea autentificarii la Router.
- JWT user cu roluri si drepturi clare.
- Separarea authN de authZ: Routerul decide accesul la ruta, agentul decide permisiuni de domeniu.
- Politici route-level pe roluri pentru servicii HTTP sensibile.

### 7.4 Endpointuri MCP interne

Stare curenta observata:

- Agentii pot face cereri MCP intre ei folosind secure-wire delegation.
- Identificarea recomandata este `X-Ploinky-Caller-JWT` cu invocation JWT existent, nu un secret static simplu.
- Routerul verifica caller JWT si mintage un token nou pentru target.
- Agentul tinta verifica audience/tool/body hash/expiry/replay.

Ce lipseste:

- Whitelist administrabil per caller/target/tool.
- Scope-uri MCP standardizate.
- Diferentiere clara intre "agentul poate vedea tool-ul" si "agentul poate executa tool-ul".
- Politici care combina userul delegat, rolurile userului si principalul agentului.

Directie propusa:

- Policy de forma `(callerPrincipal, targetAgent, method/tool/resource, scope, userRoleConstraints)`.
- Principals de forma `agent:explorer`, `agent:gitAgent`, `agent:dpuAgent`, eventual cu route key stabil.
- Deny by default pentru delegated MCP execution.
- Allow pentru perechi concrete, de exemplu:
  - `agent:explorer -> dpuAgent.dpu_access_check`
  - `agent:gitAgent -> dpuAgent.dpu_secret_get/put` doar pentru secret-store Git si userul curent
  - `agent:webmeetAgent -> webmeetStt` prin retea interna/token intern, daca este formalizat MCP
- Audit pentru toate delegated calls.

Nota despre secret per agent:

O varianta simpla ar fi ca fiecare agent sa primeasca un token secret in env si sa-l foloseasca la cereri interne. Totusi, arhitectura existenta Ploinky are deja un mecanism mai expresiv: invocation JWT cu audience, caller, tool, body hash, expiry si replay protection. Secretul static poate fi folosit pentru servicii non-MCP interne, dar pentru MCP inter-agent este mai aliniat sa se foloseasca secure-wire JWT plus policy whitelist.

### 7.5 Endpointuri MCP Admin

Stare curenta observata:

- Unele tool-uri sunt conceptual admin-only in agentii de domeniu. Exemplu: DPU are operatii de audit si `dpu_agent_policy_get/set` care sunt specificate ca sensibile/admin.
- Nu pare sa existe inca un standard global Router-level pentru taguirea tool-urilor MCP admin.
- Nu pare sa existe inca un filtru global care sa interzica tool-urile admin in API-uri OpenAI-compatible.

Directie propusa:

- Tool-urile MCP administrative trebuie marcate explicit in metadata, de exemplu `annotations.ploinky.admin=true` sau `security.admin=true`.
- Routerul trebuie sa aplice deny by default pentru admin tools.
- Executia admin trebuie permisa doar pentru:
  - user autentificat cu rol admin;
  - agent intern explicit autorizat;
  - surface explicit admin, nu API generic.
- API-urile OpenAI-compatible expuse catre Soul Gateway nu trebuie sa poata apela tool-uri admin by default.
- `tools/list` poate fie sa ascunda tool-urile admin pentru non-admin, fie sa le arate cu metadata fara a permite executia; pentru siguranta operationala, ascunderea este mai simpla pentru clienti LLM.

## 8. AssistOSExplorer high-level

AssistOSExplorer este aplicatia IDE/Explorer a workspace-ului. Agentul `explorer` este shell-ul web: serveste UI, navigare filesystem, preview/editare documente, plugin host, setari, integrare DPU, Git, Tasks, SOPLang, LLM helper, WebMeet, WebAssist si OnlyOffice.

Flux conceptual:

1. Browserul incarca UI-ul Explorer prin Router.
2. Explorer afiseaza filesystem normal si resurse virtuale precum `/Confidential`.
3. Pentru operatii simple de UI/local FS, Explorer poate folosi propriile servicii.
4. Pentru operatii de domeniu, Explorer cheama agenti MCP specializati prin Router.
5. Pluginurile adauga comenzi globale si sloturi UI, dar ownership-ul operatiilor ramane la agentii lor.

Structura principala in `AssistOSExplorer/explorer/`:

- `manifest.json`: declaratia agentului Explorer si a grafului sau de dependinte.
- `filesystem-http-server.mjs`: serverul HTTP static/custom al Explorer.
- `index.html`, `main.js`, `imports.js`, `styles.css`, `plugins.css`: shell-ul browser.
- `web-components/`: pagini, componente si modale UI.
- `services/`: servicii client-side/domain pentru documente, DPU paths, OnlyOffice, media, runtime plugins, profile avatars, audit, storage.
- `utils/`: utilities pentru filesystem, plugins, theme, keymap, loader, preview HTML, paths.
- `admin/`: UI/setari admin.
- `assets/`: fonturi, iconuri, imagini si vendor assets.
- `tests/unit/`: teste unitare pentru DPU path resolver, OnlyOffice, avatar settings, plugin aggregation, filesystem protections etc.

Explorer este un agent static/IDE, nu un agent LLM central. El orchestreaza UI-ul si delega.

## 9. Graful de agenti pornit de Explorer

Manifestul Explorer activeaza urmatorii agenti principali:

- `gitAgent` pentru Git workflows.
- `dpuAgent` pentru confidential data, secrets, ACL si audit.
- `soplangAgent` pentru SOPLang build/skill runtime.
- `tasksAgent` pentru backlog/task files.
- `llmAssistant` pentru autocomplete, commit messages si conflict resolution.
- `AchillesCLI/achilles-cli` pentru skill management si Achilles CLI.
- `webmeetInfra/liveKitServerAgent` pentru LiveKit/Redis/Coturn/Egress/Nginx.
- `webmeetStt` pentru speech-to-text intern.
- `webmeetAgent` pentru control plane intalniri.
- `multimedia` pentru media tooling.
- `onlyOffice` pentru Document Server.
- `webAssist` pentru assistant public/guest.
- `proxies/soul-gateway` pentru gateway LLM local.

Explorer mai declara pluginuri aplicatie:

- `git`
- `dpu-runtime-support`
- `dpu-audit-menu`
- `soplang-builder`
- `tasks`
- `webmeet`
- `soul-gateway`

## 10. Inventar agenti si roluri

### 10.1 `explorer`

Rol: IDE shell si file explorer. Serveste UI-ul principal, gestioneaza navigare, preview/editare, plugin host, document services, profile avatar settings si integrarea OnlyOffice.

Suprafete:

- `/<explorer>/...` UI static.
- `/services/explorer/office/` protected.
- `/public-services/explorer/office/` none/public pentru OnlyOffice document/callback routes.
- `/services/explorer/avatar-settings/` protected.
- `/services/explorer/axi-face/` protected.

Security notes:

- Activeaza `pwd enable`.
- Are useri locali de dezvoltare `admin/admin` si `user/user`.
- Public OnlyOffice routes trebuie sa ramana strict tokenizate si limitate.
- Explorer trebuie sa trateze `/Confidential` ca DPU virtual path, nu filesystem normal.
- Nu ar trebui sa detina secrete/ACL de domeniu in locul DPU.

### 10.2 `dpuAgent`

Rol: confidential data platform. Detine `/Confidential`, secrete, ACL, audit, comments si policy pentru agent access.

Suprafete:

- MCP tools prin `/<dpuAgent>/mcp`.
- Date persistente in `/dpu-data`.

Tool-uri/operatii observate:

- identity: `dpu_whoami`;
- audit: config/list/read/append;
- workspace roots;
- secrets: list/get/put/delete/grant/revoke;
- confidential files: list/get/create/update/delete/comment/grant/revoke;
- agent policy: `dpu_agent_policy_get`, `dpu_agent_policy_set`;
- access check: `dpu_access_check`.

Security notes:

- DPU este owner-ul autorizarii pentru date confidentiale.
- Grants pentru agenti se bazeaza pe principalul agentului si pe DPU-owned `permissions.manifest.json`.
- Tool-urile de audit/policy sunt candidate clare pentru `MCP Admin`.
- DPU respinge legacy identity headers; se bazeaza pe invocation context.

### 10.3 `gitAgent`

Rol: operatii Git workspace-scoped.

Suprafete:

- MCP tools prin `/<gitAgent>/mcp`.
- Plugin Explorer pentru Git UI.

Operatii:

- repo info/init/remotes/status/diff/stage/unstage/restore/conflicts/stash;
- commit/push/pull;
- auth status/device flow/manual token/disconnect/store token;
- identity config;
- repo overview si diagnostics.

Security notes:

- Verifica repo path impotriva root-urilor permise.
- Nu trebuie sa fie proxy generic de filesystem.
- Tokenurile Git sunt persistate prin DPU Secrets, per user rutat.
- Cand apeleaza DPU, forwardeaza invocation JWT prin `X-Ploinky-Caller-JWT`.

### 10.4 `llmAssistant`

Rol: helper LLM limitat pentru IDE.

Suprafete:

- MCP tools pentru autocomplete, commit message si conflict resolution.

Operatii:

- `llm_autocomplete`;
- `git_commit_message`;
- `llm_resolve_conflict`.

Security notes:

- Nu este chat general.
- Contextul este limitat/clipped.
- Nu trebuie sa expuna payload-uri brute, secrete sau provider internals.
- Toate apelurile LLM trebuie sa treaca prin `ploinky/node_modules/achillesAgentLib`; apelurile directe la provideri sunt interzise in acest workspace, cu exceptii strict mentionate pentru Soul Gateway probe/model discovery.

### 10.5 `soplangAgent`

Rol: interfata MCP catre SOPLang runtime.

Suprafete:

- MCP tools.
- Plugin Explorer pentru build/skills.

Operatii:

- sincronizare documente markdown;
- build workspace;
- variabile si comenzi SOPLang;
- tipuri;
- executie skill.

Security notes:

- UI-ul nu ar trebui sa cheme direct internals SOPLang; trece prin tool-uri finite.
- Operatiile au lifecycle strict parse/normalize/validate/dispatch/execute/respond.
- Executia de skill poate fi sensibila si trebuie incadrata atent in authZ.

### 10.6 `tasksAgent`

Rol: backlog/task workflows pentru repo-uri.

Suprafete:

- MCP tools.
- Plugin Explorer pentru task UI.

Operatii:

- config;
- list/history/get;
- create/update/delete;
- reorder.

Security notes:

- Lucreaza pe `.backlog` si `.history` in repo root.
- Verifica repoPath si nu trebuie sa devina mutator generic de fisiere.

### 10.7 `multimedia`

Rol: media tooling pentru documente si preview-uri.

Suprafete:

- Skill/tooling media, inclusiv `ffmpegImageToVideo`.
- Pluginuri pentru audio, image, video, document-video-preview si actions.

Operatii:

- conversii media, inclusiv image-to-video MP4 din imagini/audio.

Security notes:

- Respinge SVG in fluxurile unde poate fi risc.
- Outputurile sunt incarcate in blob storage.
- Trebuie validate input paths, MIME si marime.

### 10.8 `onlyOffice`

Rol: OnlyOffice Document Server gestionat de Ploinky.

Suprafete:

- Container OnlyOffice, port local.
- Folosit de Explorer prin servicii `/services/explorer/office/` si `/public-services/explorer/office/`.

Security notes:

- JWT OnlyOffice este `sharedGeneratedSecret` cu Explorer.
- OnlyOffice agent detine runtime-ul serverului, nu storage/session bridge.
- Explorer detine tokenizarea sesiunilor si callback bridge.
- Rutele publice OnlyOffice sunt un exemplu de public strict controlat, nu public generic.

### 10.9 `webAssist`

Rol: assistant public/guest pentru vizitatori: informare, profilare, lead conversion, meeting scheduling.

Suprafete:

- MCP endpoint `/webAssist/mcp`.
- Plugin `webassist-chat`.
- CLI/chat single-shot.

Operatii:

- `web_cli_chat`;
- `web_cli_history`;
- `register-visitor`.

Security notes:

- Manifestul are `guest:true`.
- Persistenta include sesiuni/leads.
- Trebuie sa refuze out-of-domain si sa nu divulge internals.
- Este exemplu natural pentru "public protejat cu token anonim temporar".

### 10.10 `webmeetAgent`

Rol: WebMeet control plane: workspaces, rooms, guest invites, LiveKit tokens, chat, transcripts, artifacts, recordings, AI dispatch metadata.

Suprafete:

- MCP tools pentru control/admin/team operations.
- HTTP API intern/protected pe `8791`.
- AgentServer MCP pe `7001`.
- proxy public/protected pe `7000`.
- `/services/webmeet/` protected.
- `/public-services/webmeet/` guest cu `forceGuest:true`.

Operatii:

- workspace list/create;
- meeting list/create/join/join_guest/leave/get/rename/delete;
- events;
- participant avatar;
- chat list/send;
- transcript append/list;
- AI agent attach/list/detach;
- recording start/stop;
- artifact list.

Security notes:

- Datele meeting sunt persistate in `/data/meetings/*.json`.
- Payloadurile sunt criptate AES-GCM cu meeting keys wrapped de `PLOINKY_WEBMEET_MASTER_KEY`.
- Guest access necesita ruta guest si token de invitatie; tokenul singur nu e suficient.
- Guest API este ingust si nu include admin/recording/AI controls.
- Media plane LiveKit este trusted si criptat in tranzit, dar nu E2E.

### 10.11 `webmeetStt`

Rol: internal speech-to-text pentru WebMeet.

Suprafete:

- Serviciu Python Faster-Whisper pe retea interna WebMeet.
- Fara public HTTP services declarate.

Security notes:

- Doar agentii din reteaua interna ar trebui sa-l acceseze.
- Nu trebuie sa logheze raw audio, transcript sensibil sau tokenuri.

### 10.12 `webmeetLivekitAiAgent`

Rol: optional LiveKit Agents worker pentru participanti AI reali in meeting-uri.

Suprafete:

- Worker separat, nu parte din default graph.
- Conectare la LiveKit cu shared credentials.
- Foloseste `WEBMEET_AGENT_INTERNAL_TOKEN`.

Security notes:

- AI participantii apar ca participanti LiveKit reali.
- Dispatch-ul trebuie sa fie explicit si autorizat.
- Are shared generated secrets cu WebMeet/LiveKit.

### 10.13 `webmeetInfra/liveKitServerAgent`

Rol: infrastructura media pentru WebMeet.

Procese supravegheate:

- Redis;
- Coturn;
- LiveKit Server;
- LiveKit Egress;
- Nginx + Certbot in prod.

Suprafete:

- Porturi media/control LiveKit.
- Volume pentru config generat, recordings, redis, tls.

Security notes:

- Nu detine policy de guest/admin pentru aplicatie; este media runtime.
- In dev/default foloseste bridge/network mapping; in prod poate folosi host network.
- Este o zona importanta pentru hardening daca se expune public.

### 10.14 `AchillesCLI/achilles-cli`

Rol: CLI/agent pentru management de skills si Achilles workflows.

Suprafete:

- MCP/CLI.
- WebChat static auth in manifest.

Operatii:

- CRUD pentru skills;
- schema validation;
- code generation;
- REPL;
- Achilles LLMAgent workflows.

Security notes:

- Poate genera/modifica code/skills, deci are potential admin/developer power.
- Trebuie clasificat atent; multe operatii sunt candidate admin sau developer-only.
- Foloseste AchillesAgentLib pentru LLM.

### 10.15 `proxies/soul-gateway`

Rol: gateway LLM local folosit de agenti pentru inferenta/model routing.

Security notes:

- In acest workspace, apelurile LLM trebuie sa treaca prin AchillesAgentLib.
- Soul Gateway are shared generated API key.
- API-urile OpenAI-compatible expuse catre Soul Gateway nu trebuie sa poata invoca tool-uri admin implicit.

## 11. Exemple concrete de securitate existente

### 11.1 Explorer + DPU pentru `/Confidential`

Explorer vede `/Confidential` ca path virtual. Cand utilizatorul listeaza sau editeaza resurse confidentiale, Explorer trebuie sa cheme DPU. DPU decide ACL, storage, comments, secrets si audit. Aceasta separare este corecta: Explorer este UI, DPU este authority.

Extindere posibila:

- Router policy: `explorer -> dpuAgent` doar tool-uri DPU necesare UI-ului.
- DPU policy: userul curent trebuie sa aiba grant pe resursa.
- Admin DPU tools doar pentru user/admin sau agenti explicit aprobati.

### 11.2 GitAgent + DPU Secrets

GitAgent nu ar trebui sa stocheze token Git direct in browser sau fisiere normale. El foloseste DPU Secrets si apeleaza DPU prin Router, forwardand invocation JWT ca `X-Ploinky-Caller-JWT`.

Extindere posibila:

- Policy intern: `gitAgent -> dpuAgent.dpu_secret_get/put/delete` doar pentru namespace Git si userul curent.
- Audit al tuturor acceselor la tokenuri.
- Interdictie pentru `gitAgent` de a accesa secrets non-Git fara grant explicit.

### 11.3 OnlyOffice public callbacks

OnlyOffice necesita rute accesibile fara sesiune browser pentru document/callback flows. Explorer expune `/public-services/explorer/office/` cu auth `none`, dar aceste rute ar trebui sa ramana tokenizate, limitate si validate.

Extindere posibila:

- Whitelist public exact/prefix doar pentru rutele OnlyOffice necesare.
- Metode permise explicit.
- Token document/session obligatoriu.
- Deny generic pentru orice altceva.

### 11.4 WebMeet guest link

WebMeet foloseste public guest service cu `forceGuest:true`. Un invite link trebuie sa ramana o sesiune guest, chiar daca browserul are si login user. Astfel, linkul public nu devine accidental admin/team operation.

Extindere posibila:

- Guest token anonim temporar plus guest invitation token.
- Rate limit per room/token/IP.
- Scope `webmeet-public-service:<roomId>`.
- Guest API strict separat de team/admin API.

### 11.5 WebAssist chat public

WebAssist este natural guest/public-protected: vizitator anonim, sesiune temporara, istoric local/server, rate limiting, lead capture.

Extindere posibila:

- Token anonim obligatoriu obtinut inainte de chat.
- Limitari de tool-uri si context.
- Blocare/revocare pe token.
- Nu se expun tool-uri admin sau MCP interne.

### 11.6 AchillesCLI si tool-uri developer/admin

AchillesCLI poate manipula skills si genera cod. Chiar daca este util in WebChat sau Explorer, operatiile sale pot fi administrative/developer-only.

Extindere posibila:

- Tag `MCP Admin` sau `Developer` pentru tool-uri de modificare.
- Ascundere din OpenAI-compatible default.
- Cerinta de user admin + route admin.

## 12. Propunere de model in 5 clase

### 12.1 Structura generala de policy

Un model coerent ar putea avea trei straturi:

1. Route policy HTTP: decide clasa de acces la nivel de path/method.
2. MCP policy: decide cine poate lista/executa tool-uri si resurse MCP.
3. Domain policy: agentul decide daca userul/callerul are voie sa faca operatia concreta.

Route policy exemplu:

```json
{
    "routes": [
        {
            "match": "exact",
            "path": "/health",
            "access": "public",
            "methods": ["GET"]
        },
        {
            "match": "prefix",
            "path": "/public-services/webmeet/",
            "access": "anonymous",
            "scope": "webmeet-public-service",
            "methods": ["GET", "POST"],
            "forceGuest": true
        },
        {
            "match": "prefix",
            "path": "/services/explorer/",
            "access": "authenticated",
            "roles": ["user", "admin"]
        }
    ]
}
```

MCP policy exemplu:

```json
{
    "internalMcp": [
        {
            "caller": "agent:explorer",
            "target": "agent:dpuAgent",
            "tools": ["dpu_access_check", "dpu_confidential_list", "dpu_confidential_get"],
            "userRoles": ["user", "admin"]
        },
        {
            "caller": "agent:gitAgent",
            "target": "agent:dpuAgent",
            "tools": ["dpu_secret_get", "dpu_secret_put"],
            "scopes": ["secret:git:*"]
        }
    ],
    "adminMcp": [
        {
            "target": "agent:dpuAgent",
            "tools": ["dpu_agent_policy_get", "dpu_agent_policy_set"],
            "roles": ["admin"],
            "surfaces": ["router-admin", "explorer-admin"]
        }
    ]
}
```

### 12.2 Public

Definition:

- Acces fara identitate.
- Doar rute explicit whitelisted.
- Doar metode si query params explicit permise.
- Fara tool execution.

Use cases:

- health-check;
- asset JS static;
- document callback foarte restrans;
- public static content controlat.

### 12.3 Anonymous protected

Definition:

- Clientul obtine token anonim temporar.
- Tokenul are scope, expiry, revocare si rate limits.
- Identitatea este `guest`, nu user.

Use cases:

- WebAssist chat;
- WebMeet guest links;
- public link sharing;
- formulare publice cu rate limiting.

### 12.4 Authenticated

Definition:

- User login/session JWT.
- Router valideaza user/roles.
- Agentul aplica domain auth.

Use cases:

- Explorer UI;
- protected services;
- WebMeet team API;
- Git/Tasks/SOPLang normal user operations.

### 12.5 Internal MCP

Definition:

- Caller este un agent identificat prin secure-wire invocation chain.
- Router verifica caller token si policy.
- Target primeste invocation JWT nou, scurt, legat de payload.

Use cases:

- Explorer -> DPU;
- GitAgent -> DPU Secrets;
- WebMeetAgent -> STT/AI worker, daca este formalizat MCP;
- LlmAssistant -> domain helpers, daca este permis.

### 12.6 MCP Admin

Definition:

- Tool-uri/resurse marcate explicit ca administrative.
- Deny by default.
- Disponibile doar pe suprafete admin si pentru roluri/calleri admin-approved.
- Excluse din OpenAI-compatible default si din agent delegation generica.

Use cases:

- DPU policy management;
- audit config/read;
- whitelist route management;
- agent lifecycle/dashboard commands;
- skill/code generation destructive operations.

## 13. Intrebari bune pentru sesiunea urmatoare

1. Care este granita exacta intre `public` si `anonymous protected`? Trebuie orice public non-static sa devina anonymous protected?
2. Tokenul anonim trebuie sa fie cookie, bearer token sau ambele?
3. Se doreste rate limiting centralizat in Router sau per agent/service?
4. Cum se reprezinta principalul unui agent: route key, manifest name, repo path sau agent principal explicit?
5. Tool-urile MCP admin se ascund din `tools/list` pentru non-admin sau apar dar nu pot fi executate?
6. Cum se impiedica expunerea tool-urilor admin prin OpenAI-compatible APIs?
7. Cum se auditeaza delegated MCP calls fara a loga payload-uri sensibile?
8. Ce agenti au voie implicit sa cheme DPU si pentru ce namespace-uri?
9. Cum se version-eaza policy store-ul: `.ploinky/router-whitelist.json`, manifest annotations sau ambele?
10. Ce se intampla cand un agent nu are metadata security pentru tool-uri: deny by default sau legacy allow?
11. Cum se separa rolurile user (`admin`, `user`, `guest`) de rolurile agent (`internal`, `system`, `developer`, `admin-agent`)?
12. Ce rute publice existente trebuie pastrate: `/health`, `/MCPBrowserClient.js`, `/agent-card`, OnlyOffice public callbacks?
13. Este `/agent-card` agregat prea informativ pentru public internet?
14. Cum se aplica CSRF/origin policy pe rute guest/protected?
15. Ce loguri/transcripts trebuie redacted suplimentar pentru noul model?

## 14. Gaps si riscuri de tinut minte

Observate sau mentionate in spec-uri:

- Ploinky nu este inca hardened pentru hostile multitenant internet deployment.
- `auth:"none"` este prea puternic daca nu este incadrat de whitelist strict.
- `/agent-card` public poate expune metadata despre agenti; trebuie evaluat pentru deployment public.
- Secure-wire protejeaza executia MCP, dar nu inlocuieste domain authorization.
- Discovery MCP poate lista tool-uri; asta nu trebuie confundat cu permisiune de executie.
- Admin MCP tagging pare mai degraba design propus decat implementare globala existenta.
- Inter-agent MCP policy matrix pare incomplet fata de modelul dorit.
- OpenAI-compatible endpoints trebuie analizate explicit pentru a preveni tool/admin leakage.
- Agentii cu putere de code/skill generation, precum AchillesCLI, trebuie tratati ca developer/admin surfaces.
- WebMeet media plane are propriul model de incredere; transportul este criptat, dar nu E2E.

## 15. Concluzie pentru designul urmator

Directia cea mai aliniata cu arhitectura existenta este sa nu se inlocuiasca secure-wire cu secrete statice per agent, ci sa se construiasca peste el:

- Router whitelist pentru HTTP public/public-protected/authenticated.
- Guest/anonymous tokens generalizate, cu rate limit si scope.
- MCP internal policy matrix, bazat pe principalul agentului si invocation chain.
- MCP admin annotations si deny-by-default.
- Filtru explicit pentru OpenAI-compatible APIs, astfel incat tool-urile admin sa nu fie apelabile implicit de agenti LLM sau Soul Gateway.

Ploinky are deja piesele fundamentale: Router ca trust broker, sesiuni user/guest, invocation JWT-uri, header stripping, agent isolation si manifest-driven services. Munca principala este formalizarea policy-urilor, taguirea suprafetelor sensibile si inchiderea comportamentelor legacy/public implicite.
