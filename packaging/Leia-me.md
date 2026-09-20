# Steam Achievement Analytics

O **Steam Achievement Analytics** organiza sua biblioteca Steam, mostra o
progresso das conquistas e ajuda a planejar o próximo 100%.

## Como iniciar

1. Abra o arquivo `SAA.exe`.
2. O navegador será aberto automaticamente em `http://127.0.0.1` (ou na primeira porta livre a partir da 80).
3. Informe sua Steam Web API Key na aplicação, se ainda não estiver configurada.

Enquanto o programa estiver aberto, a janela desktop permite abrir o navegador,
alterar a API Key, criar um atalho e encerrar o servidor. Fechar essa janela
encerra a aplicação corretamente. Fechar apenas a aba do navegador não encerra
o servidor.

Se o navegador não abrir sozinho, acesse manualmente:

```text
http://127.0.0.1
```

## Configuração da Steam

O arquivo `.env` fica na mesma pasta do executável. Preencha:

```env
STEAM_API_KEY=sua_chave_aqui
```

A chave pode ser criada em:

```text
https://steamcommunity.com/dev/apikey
```

Não compartilhe o arquivo `.env`, pois ele contém sua chave privada.

## Dados e atualizações

Os dados são salvos localmente em:

```text
%APPDATA%\Steam Achievement Analytics
```

Atualizar ou substituir a pasta do programa não apaga o banco local.

O aplicativo usa SQLite e cache temporário em memória. Python não é necessário
para esta versão.

## Distribuição

Mantenha todos os arquivos desta pasta juntos. O `SAA.exe` depende das DLLs,
arquivos estáticos e pastas que acompanham a distribuição.

Para atualizar o aplicativo, substitua a pasta do programa preservando os dados
em `%APPDATA%\Steam Achievement Analytics`.
