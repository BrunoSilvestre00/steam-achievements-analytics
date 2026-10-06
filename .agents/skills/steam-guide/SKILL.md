---
name: steam-guide
description: Pesquisa um guia de 100% das conquistas Steam, salva o Markdown localmente e publica como Nota no workspace do Steam Achievement Analytics aberto. Use para $steam-guide seguido de nome ou AppID, ou pedido equivalente.
---

# Steam Guide

Gere um guia pesquisado em português do Brasil para a versão Steam e publique-o como Nota na aplicação local em execução. A invocação autoriza criar a nota e a cópia local do guia; não substitua notas anteriores nem altere a versão do projeto.

## Entrada e destino

- Aceite `$steam-guide <nome_do_jogo|appid>` e a skill selecionada no menu de skills. O cliente pode rejeitar comandos personalizados com `/` antes de enviá-los à LLM; não recomende esse prefixo.
- Leia [guide-writing.md](references/guide-writing.md) antes de pesquisar: define o conteúdo e a verificação do guia.
- Execute a partir da raiz do projeto: `.\.venv\Scripts\python.exe scripts/steam_guide_client.py context`. Se não houver venv, use `python` (o cliente usa apenas a biblioteca padrão).
- O cliente procura a aplicação nas portas 80–109; para outro endereço local use `--base-url http://127.0.0.1:PORTA`. Não inicie outro servidor, não leia .env/API keys e não abra SQLite diretamente.
- Se a aplicação não estiver disponível ou não reconhecer o endpoint, pare e explique que é necessário abrir a build atualizada. Preserve qualquer arquivo já gerado.
- `active_steamid` é o último perfil aberto na aplicação; com um único perfil salvo, ele é usado automaticamente. Com múltiplos perfis e nenhum ativo, pergunte qual perfil usar. Nunca escolha arbitrariamente entre perfis.
- Para nomes, procure primeiro os jogos do perfil no contexto retornado. Se houver ambiguidade de edição ou título, pergunte. Se o nome não estiver cadastrado, identifique o AppID correto pela página da loja Steam. Um AppID é o ID do jogo, não o SteamID de 17 dígitos do jogador.
- Confirme que o AppID pertence ao perfil antes de gerar. Se não pertencer, peça ao usuário para adicioná-lo usando “Adicionar jogo externo” na aplicação; não publique em outro jogo nem acrescente jogos silenciosamente.

## Geração

Pesquise na web e siga a referência de escrita. Steam determina a lista de conquistas, incluindo ocultas e DLCs. Não use dados de PlayStation como equivalentes sem verificação. Use links Markdown reais para fontes, não marcadores de citação internos da ferramenta. Use `- [ ]`/`- [x]` sem escape para checkboxes interativos. Registre a data de pesquisa e o AppID no guia. Se fontes não permitirem verificar o total/lista, declare a lacuna e não afirme que o guia está completo.

Salve em UTF-8, sem frontmatter obrigatório, em `generated-guides/<appid>/<nome-seguro>_Steam_100_<YYYYMMDD-HHMMSS>.md`. Use nome seguro para Windows. Crie a pasta se necessário. O conteúdo do arquivo deve ser exatamente o Markdown que será enviado à nota; não encapsule em um bloco de código. Não sobrescreva guias anteriores.

## Publicação e confirmação

Execute:

```powershell
.\.venv\Scripts\python.exe scripts/steam_guide_client.py publish --steamid <perfil> --appid <appid> --file "generated-guides/<appid>/<arquivo>.md" --base-url <base_url_retornada>
```

O cliente lê o arquivo e envia JSON UTF-8 ao endpoint `POST /api/profile/<steamid>/games/<appid>/workspace/note`. Preferir este cliente a interpolar Markdown em comandos cURL: evita perda de acentos, novas linhas e escaping do PowerShell. O arquivo inteiro vira uma nota, sem passar pelo importador de workspace (que substitui os dados existentes).

Verifique `ok`, `note_id`, `created` e `workspace_url`. Só diga que a nota foi salva depois de resposta positiva. Reenvios de conteúdo idêntico reutilizam a nota; conteúdo diferente cria uma nova, preservando edições e notas anteriores. Em erro de conexão, uma única nova tentativa com o mesmo arquivo é suficiente; se continuar falhando, pare e forneça o arquivo e o erro. Não altere o banco diretamente.

Ao concluir, envie o link do Markdown local, o link do workspace, o ID da nota e um resumo curto de dificuldade, horas, perdíveis e online. O usuário pode precisar atualizar uma página de workspace que já esteja aberta para ver a nota criada externamente.
