# Steam Achievement Analytics

Aplicação web em **Python + FastAPI + Jinja2 + SQLite** para explorar sua biblioteca
Steam e construir, por etapas, um planejamento de jogos para fazer 100%.
O frontend é HTML/CSS renderizado pelo Python, com um pequeno script JavaScript
para trocar o painel de detalhes sem recarregar a página. Não precisa de Node ou React.

## Rodar localmente (PowerShell)

Requer Python 3.10 ou superior. Na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

No `.env`, preencha `STEAM_API_KEY` com a chave obtida em
[Steam Web API Key](https://steamcommunity.com/dev/apikey). A chave é lida no
servidor e não é enviada ao navegador. O `.env` está ignorado pelo Git.
Opcionalmente, configure `STEAM_PROFILE` com o link do seu perfil para deixar o
campo inicial preenchido. Links como `https://steamcommunity.com/id/cidosilvestre/`
são convertidos automaticamente para SteamID64 pela API.

```powershell
.\.venv\Scripts\python.exe -m uvicorn steam_analytics.web:app --reload
```

Abra **http://127.0.0.1:8000** e informe o SteamID64 ou o link do perfil.
Também pode acessar diretamente:

```text
http://127.0.0.1:8000/profile/SEU_STEAMID64
```

Substitua `SEU_STEAMID64` pelos 17 dígitos do seu perfil. O campo inicial também
aceita links `steamcommunity.com/profiles/...` e `steamcommunity.com/id/...`.
Links personalizados são resolvidos pela API antes de redirecionar à URL canônica.
Reinicie o servidor depois de alterar a chave no `.env`.

## Rodar com Docker Compose

Com Docker instalado, mantenha a `STEAM_API_KEY` no `.env` e execute:

```powershell
docker compose up --build
```

A aplicação fica em `http://127.0.0.1:8000`. O SQLite é persistido no volume
`steam_data` e o Redis no volume `redis_data`. As respostas dos endpoints JSON
ficam em cache por 5 minutos; importações e atualizações invalidam as chaves
relacionadas imediatamente. Se o Redis estiver indisponível fora do Compose, a
aplicação continua funcionando sem cache.

## O que funciona

- Tela dividida por `/profile/{steamid}`: cards à esquerda e detalhes à direita.
- Seleção de jogo sem recarregar a página, com capa, horas jogadas e conquistas Steam.
- Percentual e contagem de conquistas nos cards; ordenação por maior ou menor percentual.
- Tempo de completionist do HowLongToBeat nos cards; ordenação por menor ou maior tempo.
- Resultados do HLTB ficam salvos localmente; jogos ainda não consultados aparecem como
  “HLTB a consultar” e a consulta é feita ao abrir o detalhe do jogo.
- Percentuais carregados em segundo plano, em lotes de três jogos. A ordenação acompanha
  a chegada dos dados. Jogos sem percentual ficam no fim em ambas as direções.
- O parâmetro `?game=APPID` preserva o jogo selecionado ao compartilhar ou recarregar a URL.
- Busca por nome, filtro de jogados/não iniciados e ordenação por nome, horas ou última sessão.
- SQLite com a última biblioteca válida de cada perfil, sem duplicar jogos nas atualizações.
- Cache de 15 minutos; o botão **Atualizar biblioteca** força uma nova consulta.
- Último resultado salvo com aviso quando uma atualização falha.
- Conquistas persistidas no SQLite: detalhes com cache de 5 minutos e atualização
  dos percentuais da biblioteca a cada 15 minutos. Falhas também são registradas para
  evitar repetir consultas de jogos indisponíveis a cada visita.
- API JSON em `GET /api/profile/{steamid}`; contrato em `/openapi.json`.
- Importador opcional de terminal com exportação JSON/CSV:

```powershell
.\.venv\Scripts\python.exe -m steam_analytics sync --profile SEU_STEAMID64
```

Dados locais ficam em `data/steam.sqlite3`. JSON/CSV são gerados apenas pelo importador
de terminal. Campos de tempo ausentes ficam nulos: não são tratados como zero.
Tempos originais são minutos; `rtime_last_played` é Unix timestamp quando disponível.
As datas de atualização exibidas estão em UTC. A atualização substitui o snapshot
daquele perfil e não mantém histórico de importações.

## Acesso à Steam e limites desta etapa

Usamos o host público `api.steampowered.com`, `GetOwnedGames` com
`include_appinfo=true` e `include_played_free_games=true`, e `ResolveVanityURL`
para links personalizados. `GetPlayerAchievements` fornece o progresso do jogo selecionado.
A biblioteca depende da visibilidade de **Detalhes dos jogos**
nas configurações de privacidade da Steam. Se o tempo estiver oculto, os totais
podem estar incompletos. Um retorno sem `game_count` é tratado como indisponível,
nunca como uma biblioteca vazia.

O conjunto exibido é o retornado por `GetOwnedGames`; pode diferir do cliente Steam
(por exemplo, jogos compartilhados ou gratuitos nunca jogados). Horas jogadas não
representam porcentagem de conclusão. PSNProfiles fica para uma próxima etapa. O
HowLongToBeat usa o pacote comunitário `howlongtobeatpy`; como o site não oferece uma
API pública estável, uma mudança no site pode exigir atualização do adaptador. Nenhum
resultado fictício é apresentado como sua biblioteca.
Jogos sem dados de conquistas mostram indisponibilidade; uma lista vazia não significa 100%.
As capas vêm do CDN da Steam e dependem de conexão; os dados já importados ficam locais.

## Banco local

O schema versionado está em `steam_analytics/schema.sql`. O banco é criado
automaticamente ao iniciar a aplicação. São onze tabelas:

| Tabela | Dados |
| --- | --- |
| `games` | Catálogo de jogos, uma linha por appid |
| `libraries` | Perfis e data da última importação |
| `library_games` | Jogos de cada perfil e seus tempos de jogo |
| `achievement_definitions` | Nome e descrição de cada conquista de um jogo |
| `player_achievements` | Conquistas desbloqueadas ou pendentes por perfil |
| `achievement_sync` | Controle de atualização das conquistas por perfil e jogo |
| `achievement_attempts` | Última tentativa de consulta e falhas, sem descartar conquistas salvas |
| `hltb_data` | Tempos de história, extras e completionist associados aos jogos |
| `trophy_guides` | Dificuldade, playthroughs e horas dos guias de troféus |
| `game_notes` | Anotações privadas por perfil e jogo |
| `game_checklist` | Itens de planejamento e preparação |
| `game_links` | Links úteis associados ao jogo |

As gravações são transacionais, com chaves estrangeiras e chaves únicas para evitar
duplicação. Jogos são compartilhados entre perfis; tempos e conquistas são individuais.
Dados válidos são preservados em falhas da Steam. O formato inicial do importador é
migrado automaticamente, sem perder a biblioteca existente. A chave da API não é salva
no banco. Para backup, pare a aplicação e copie `data/steam.sqlite3`.

Esta versão foi preparada para execução local, sem autenticação de usuários.
Os testes usam respostas simuladas da Steam; a validação com sua conta exige
configurar a chave e consultar seu perfil real.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Cobertura: contrato da Steam, resolução de perfis, falhas de rede, biblioteca
privada/vazia, cache, preservação de dados em falhas, isolamento entre perfis,
renderização HTML, escape de conteúdo externo, busca, filtros e atualização.

## Estrutura

```text
steam_analytics/
  web.py          # rotas web e API
  service.py      # importação, cache e atualização
  steam.py        # cliente HTTP da Steam
  storage.py      # SQLite e exportação
  schema.sql      # tabelas e relacionamentos locais
  config.py       # configuração local
  templates/      # páginas Jinja2
  static/         # CSS
  __main__.py     # importador opcional de terminal
tests/
```

Referências: [GetOwnedGames](https://partner.steamgames.com/doc/webapi/iplayerservice),
[ResolveVanityURL](https://partner.steamgames.com/doc/webapi/ISteamUser),
[Steam Web API](https://partner.steamgames.com/doc/webapi_overview) e
[templates do FastAPI](https://fastapi.tiangolo.com/advanced/templates/).
