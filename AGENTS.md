# Comandos do projeto

Quando uma mensagem começar com `$steam-guide`, trate o restante como nome ou AppID do jogo e execute a skill em `.agents/skills$steam-guide/SKILL.md`. Leia suas instruções e a referência indicada; gere o Markdown e publique como Nota na aplicação em execução. Não confunda AppID do jogo com SteamID do perfil.

## Versão e validação

A versão em `steam_analytics/version.py` só muda por solicitação explícita do usuário. O fluxo de teste do aplicativo é desktop: após alterações que precisam de uma nova build, gere o executável e abra-o. Preserve o banco local existente.
