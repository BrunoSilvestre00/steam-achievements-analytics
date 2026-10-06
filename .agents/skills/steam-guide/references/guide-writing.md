# Steam Platinum Guide

## Objetivo

Gerar um arquivo `.md` pesquisado, atualizado e acionável para completar
**100% das achievements da versão Steam**. "Platina" significa 100%
Steam, mesmo quando difere de PlayStation/Xbox.

## Entrada

Comando: `$steam-guide <nome do jogo ou AppID Steam>`

Não peça confirmação se o jogo estiver inequívoco. Desambigue apenas
quando edição/jogo alterar substancialmente a lista.

## Pesquisa obrigatória

Pesquise na web antes de gerar o guia. Steam define o escopo; use
documentação oficial, trackers, guias especializados, wikis e comunidade
como apoio.

Confirme: - total atual de achievements; - DLCs/updates com achievements
e se são pagos; - online, multiplayer, coop e PvP; - estado dos
servidores; - perdíveis; - chapter select/free roam; - NG+ e
playthroughs mínimos; - dificuldade obrigatória e se achievements
acumulam; - cheats/modificadores que desativam achievements; -
achievements bugadas; - grind; - tempo e dificuldade do 100%; - ações
críticas que devem ser feitas no início.

Nunca copie automaticamente um trophy guide de PlayStation como se fosse
a lista Steam. Não invente requisitos. Se houver divergência, pesquise
fontes recentes e declare incerteza restante.

## Dificuldade

Informe dificuldade geral **1--10** e dificuldade individual: - ★☆☆☆☆
trivial/automática - ★★☆☆☆ simples, ação específica - ★★★☆☆ atenção,
habilidade moderada ou grind - ★★★★☆ difícil/demorada - ★★★★★ grande
barreira do 100%

## Perdíveis

Crie `## ⚠️ Perdíveis` e diferencie realmente perdível, temporariamente
perdível e não perdível. Se não houver: **Nenhuma achievement é
perdível.**

## Online

Crie `## 🌐 Online / Multiplayer`. Informe quantidade, PvP/coop,
boosting, jogadores mínimos e servidores. Se não houver: **Nenhuma
achievement exige online ou multiplayer.** Se servidores fechados
impedirem 100%, destaque no topo.

## DLC

Crie `## DLC e conteúdo adicional`: DLCs com achievements,
gratuitas/pagas, necessidade para 100%, quantidade e melhor momento.

## Antes de começar

Sempre crie `# ⚠️ Antes de começar` com apenas decisões realmente
críticas: perdíveis cedo, dificuldade, personagem/classe, collectibles
sem replay, configurações que desativam achievements, save manual etc.
Se nada: **Não há preparação obrigatória antes de começar.**

## Roadmap

Otimize para minimizar playthroughs, backtracking e grind duplicado.
Adapte ao jogo, por exemplo: 1. Preparação 2. Campanha 3. Limpeza
pós-game 4. Colecionáveis 5. Dificuldade máxima 6. Challenges/Time
Trials 7. Grind 8. Online 9. DLC 10. Limpeza final

## Estrutura obrigatória

# <JOGO> --- Guia de 100% das Conquistas (Steam)

> Guia para completar **X/X achievements na Steam**.

## Visão geral

| Item | Informação |
| --- | --- |
| Achievements | X |
| Dificuldade | X/10 |
| Tempo estimado | X–Y horas |
| Playthroughs mínimos | X |
| Perdíveis | Sim/Não |
| Online | Sim/Não |
| Multiplayer | Sim/Não |
| DLC necessária | Sim/Não |
| Dificuldade obrigatória | ... |
| Achievement mais difícil | ... |

# ⚠️ Antes de começar

# Roadmap

## Etapa 1 --- ...

## Etapa 2 --- ...

# Guia das achievements

Agrupe utilmente: História, Perdíveis, Combate, Colecionáveis,
Exploração, Secundárias, Dificuldade, Speedrun/Time Trial, Grind,
Online, Coop, DLC, Finais, Miscellaneous. Não crie categorias vazias.

## Formato de CADA achievement

## ☐ Nome oficial

**Dificuldade:** ★★★☆☆\
**Tipo:** ...\
**Perdível:** Sim/Não\
**Etapa recomendada:** Etapa X

**Requisito:** objetivo curto.

**Como fazer:** instruções concretas:
fase/capítulo/mapa/NPC/personagem/quantidade/pré-requisitos/estratégia/grind
quando relevante. Para achievements automáticas de história, seja breve.

Mantenha o nome oficial Steam, preferindo PT-BR quando disponível;
inglês pode aparecer entre parênteses.

# Checklist 100%

Liste todas, uma por linha, usando checkboxes reais de Markdown:

- [ ] Achievement 1
- [ ] Achievement 2

A quantidade deve ser exatamente igual ao total Steam, incluindo ocultas
e DLC necessárias.

# Fontes principais

Liste poucas fontes importantes e confiáveis usadas na pesquisa.

## Verificação antes de finalizar

Cheque: 1. total Steam correto; 2. todas aparecem no guia; 3. todas
aparecem no checklist; 4. checklist tem exatamente o total; 5. nenhuma
duplicada; 6. DLC correta; 7. ocultas incluídas; 8. online correto; 9.
perdíveis corretas; 10. roadmap evita retrabalho.

Se a contagem não fechar, pesquise novamente; nunca finja consistência.

## Arquivo

Salvar no caminho definido pelo SKILL.md principal, UTF-8, Markdown puro
compatível com GitHub/Obsidian/VS Code. Use headings, tabelas,
checkboxes, listas e negrito.

O resultado principal é uma Nota no workspace da aplicação, com uma cópia local do mesmo Markdown em generated-guides/. Siga o fluxo de publicação descrito no SKILL.md da skill.

## Resposta final

Forneça o link e um resumo curto:
`Dificuldade: X/10 | ~X–Yh | N perdíveis | N online` Não cole novamente
o guia inteiro.

## Preferências do usuário

-   Português do Brasil.
-   Steam.
-   Completionismo/100%.
-   Pesquisa atualizada.
-   Instruções concretas.
-   ★1--5 por achievement.
-   Roadmap eficiente.
-   Spoilers permitidos quando necessários.
-   Não especular.
-   Explicar exatamente farms/grinds.
-   Declarar incertezas.

Se o usuário fornecer progresso depois, atualize o guia: - `[x]`
concluída - `[ ]` pendente e reorganize o roadmap priorizando o que
falta.
