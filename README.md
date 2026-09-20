<div align="center">
  <img src="steam_analytics/static/assets/logo-title.png" alt="Steam Achievement Analytics" width="520">
  <p>Organize sua biblioteca Steam, acompanhe conquistas e planeje o próximo 100%.</p>
</div>

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10 ou superior">
  <img src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLite-local-003B57?logo=sqlite&logoColor=white" alt="SQLite">
</div>

O Steam Achievement Analytics é um aplicativo desktop para Windows que abre uma
interface web local. Ele reúne biblioteca Steam, progresso de conquistas, HLTB,
guias de troféus e uma área de workspace por jogo com notas, checklists e links.
Os dados ficam no SQLite local do usuário.

## Executar a versão distribuída

Baixe e extraia `SteamAchievementAnalytics.zip`, mantendo todos os arquivos da
pasta juntos. Execute `SAA.exe`. A janela desktop permite informar e salvar a
Steam Web API Key, abrir a aplicação no navegador, criar um atalho e encerrar o
servidor local.

A chave é gerada em [Steam Web API Key](https://steamcommunity.com/dev/apikey).
O banco é salvo em `%APPDATA%\Steam Achievement Analytics` e permanece intacto
quando o executável é atualizado.

## Gerar uma nova build Windows

Para desenvolver ou gerar uma nova distribuição, instale Python 3.10+ e execute:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\scripts\build_windows.ps1
```

O resultado fica em `dist\SteamAchievementAnalytics\SAA.exe` e o script também
gera `dist\SteamAchievementAnalytics.zip`. Sem parâmetros, ele copia
`.env.example`; com `-ExportEnv`, copia o `.env` atual para a build.
Para abrir automaticamente a aplicação ao final do build, use `-Launch`.

## Desenvolvimento

```powershell
.\.venv\Scripts\python.exe -m uvicorn steam_analytics.web:app --reload
```

Abra `http://127.0.0.1:8000` ou `/profile/SEU_STEAMID64`. A chave pode ficar no
`.env` como `STEAM_API_KEY=...`.

## Workspace e arquivos editáveis

Na página de workspace de cada jogo é possível criar vários checklists nomeados,
como `Itens de magia` e `Inimigos encontrados`, além de notas e links úteis.
O workspace pode ser exportado para Markdown, editado manualmente e importado de
volta. O próprio arquivo exportado contém comentários com exemplos da estrutura.

## Qualidade

```powershell
.\.venv\Scripts\python.exe -m ruff check steam_analytics tests
.\.venv\Scripts\python.exe -m pytest -q
```

O pre-commit executa Ruff, djLint e Prettier para bloquear commits com problemas.

## Estrutura principal

```text
steam_analytics/
  desktop.py       # janela Windows e servidor local
  web.py           # páginas e endpoints FastAPI
  service.py       # integrações Steam, HLTB e guias
  storage.py       # SQLite e workspace
  schema.sql       # schema versionado
  templates/       # páginas Jinja2
  static/          # CSS, JavaScript e assets
scripts/
  build_windows.ps1
packaging/
  Leia-me.md
```
