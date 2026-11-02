# Transporte de ambiente e contexto

Este arquivo ajuda a retomar o TCC em outra máquina ou sessão de assistente.
O repositório é a fonte do código e das regras do projeto: atualize-o pelo Git.
Este documento registra o contexto necessário para preparar o ambiente e
continuar o trabalho; confirme o estado atual antes de agir, pois branch,
commits e pendências podem mudar.

Enquanto este arquivo estiver não rastreado, ele não será transportado por
`git pull` ou por um novo clone. Inclua-o explicitamente no versionamento ou
transfira-o por outro meio quando ele fizer parte da mudança aprovada.

## 1. Retomar o repositório

Na cópia já existente, entre na branch de trabalho e atualize-a:

```bash
git status --short
git branch --show-current
git pull
```

Se ainda não houver cópia, faça o clone pelo endereço remoto do projeto e
selecione a branch desejada. No momento desta atualização, o checkout estava
em `main` e o último commit versionado era `96e888d` (`Atualizar documentação
do benchmark voxelizado`). Esses dados são apenas um ponto de referência; use
`git status` e `git log` para conferir a situação no destino.

Não presuma que arquivos não rastreados ou ignorados, incluindo dados,
resultados, seeds locais e este próprio documento enquanto não for adicionado,
venham com `git pull`.

## 2. Regras e fontes de contexto

- Leia `AGENTS.md` na raiz antes de alterar código. Ele define convenções de
  desenvolvimento, testes e orientação. Como esse arquivo pode estar ignorado
  na cópia local, confirme separadamente que ele existe na máquina de destino.
- Leia `README.md` para objetivo, instalação, comandos e limites do benchmark.
- Consulte `Orientacao-codex.md`, `docs/roadmap.md`,
  `docs/methodology-adjustments.md` e `docs/architecture.md` para decisões e
  próximos passos. As divisões de tarefas estão em
  `docs/tarefas-pablo-reconstrucao-modelos.md` e
  `docs/tarefas-felipe-sdf-ca.md`.
- Trate resultados confirmados e hipóteses separadamente. O scan do Elaphes
  é referência de **superfície**, sem interior validado; não usar IoU
  volumétrica ou SDF real dele no benchmark atual.
- O volume gerado usa `bool[D,H,W]` em ZYX, com `True` para espaço aberto e
  `False` para sólido. Na grade diagnóstica de superfície do Elaphes,
  `True` significa parede observada. A distinção está no `README.md`.

## 3. Preparar Python e validar a cópia

O projeto requer Python 3.10 ou superior. `pyproject.toml` é a fonte principal
das dependências e `uv.lock` acompanha a resolução. A partir da raiz:

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv run python -m cavegen.datastream.run_reference_voxelization --help
git diff --check
```

Para tarefas de aprendizado de máquina ou profiling, instale também os extras
necessários com `uv sync --extra ml --extra profiling`. O `README.md` traz
as alternativas de instalação e um exemplo pequeno do benchmark.

As bibliotecas de documentos (`python-docx`, `pypdf`, `pdfplumber`,
`pdf2image`, `reportlab` e `Pillow`) estavam em um ambiente **separado** em
`/home/midnavi/.local/share/codex-artifacts-venv`. Esse caminho é específico
da máquina original. No destino, verifique se há um ambiente equivalente;
caso contrário, crie um ambiente separado para documentos e ajuste o caminho
indicado em `AGENTS.md`. Não instale essas dependências no ambiente do
projeto apenas para reproduzir o caminho antigo.

## 4. Dados, hardware e configurações locais

O código e as configurações versionadas ficam no Git. Dados externos,
artefatos em `data/`, checkpoints em `models/` e resultados em `results/`
podem exigir transferência ou regeneração **somente se a próxima tarefa os
utilizar**. Confira `configs/datasets.yaml`, `configs/hardware/` e o comando
pertinente no `README.md` antes de executar experimentos. Não copie caminhos
absolutos da máquina antiga sem revisá-los.

Nesta máquina, o volume externo `D:` é a origem preferencial para point clouds
e outros dados grandes de cavernas. Processe-os no próprio volume quando
possível; não os duplique no repositório. Três cavernas obtidas entre as 16 da
fonte associada ao KarstConduitCatalogue ainda estão em descompactação. Não
calcule hashes, limites nem tente validar esses arquivos antes de a extração
terminar. O caminho exato de cada dataset dentro de `D:` deve ser confirmado
antes da execução, pois não é uma configuração portátil do repositório.

As responsabilidades atuais são: Pablo implementa e padroniza as métricas
(prioridade 1), implementa os geradores neurais (prioridade 2) e parseia as
novas cavernas (prioridade 3). Felipe continua CA e Random Walk e, depois,
implementa o algoritmo evolutivo para ajustar ambos. A padronização ampla da
documentação fica para o encerramento do experimento.

Registre o ambiente de cada medição. Resultados de Colab, máquina local e
ROCm devem ser identificados separadamente; não misture seus tempos em uma
mesma comparação sem essa distinção. Não coloque tokens, senhas ou chaves
de API neste arquivo ou em commits. Se houver configurações pessoais de
Codex, plugins ou skills fora do repositório, configure-as separadamente no
destino conforme a necessidade.

## 5. Contexto para a próxima conversa

Use esta mensagem ao iniciar uma nova sessão, completando a última linha:

> Estou continuando o TCC CaveGen na branch de trabalho atual. Leia
> `AGENTS.md`, `README.md` e `transporte-de-ambiente.md` antes de
> alterar arquivos. Confirme `git status`, branch e último commit. O
> benchmark atual compara inicialmente Random Walk e Cellular Automata em
> volumes booleanos ZYX; o Elaphes é somente referência de superfície, sem
> IoU volumétrica validada. Use preferencialmente o volume `D:` para point
> clouds e confirme se qualquer descompactação terminou antes da leitura.
> Pablo prioriza métricas, redes neurais e parsing; Felipe conduz CA, Random
> Walk e o algoritmo evolutivo. Siga as regras de testes do projeto.
> Minha próxima tarefa é: **[descrever aqui]**.

Atualize esta seção quando uma decisão nova ainda não estiver registrada nos
documentos do repositório. Para decisões duradouras, prefira atualizar o
documento metodológico ou o roadmap correspondente.
