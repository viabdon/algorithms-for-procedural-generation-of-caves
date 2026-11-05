# CaveGen TCC — Algoritmos de Geração Procedural de Cavernas 3D

Repositório do Trabalho de Conclusão de Curso **"Algoritmos de Geração Procedural de Cavernas: Uma Comparação Holística"**.

O objetivo do projeto é comparar algoritmos clássicos e baseados em aprendizado de máquina para geração procedural de cavernas tridimensionais. A avaliação atual prioriza custo computacional, estrutura, controle e diversidade dos volumes gerados. A IoU volumétrica contra o scan do Elaphes saiu do escopo atual porque ainda não há uma referência validada de seu espaço interno.

## Estratégia atual

A arquitetura prioriza um pipeline científico **offline-first**:

1. Python gera volumes 3D booleanos em ZYX, persiste NPZ e calcula métricas e CSV.
2. Random Walk e Cellular Automata básico formam o benchmark inicial, com
   domínio, resolução, sementes e orçamento documentados.
3. Malhas extraídas dos volumes gerados por Marching Cubes permitem inspeção
   na Unity; gRPC é posterior.
4. GAN e PCGRL são frentes futuras; a branch `CA` contém um protótipo de CA
   com peso espacial. O ajuste genético de parâmetros de CA e Random Walk
   está planejado; seus espaços de busca e orçamento ainda serão definidos.
5. O Elaphes permanece referência de superfície para inspeção qualitativa,
   sem IoU volumétrica ou SDF real no benchmark atual.

Essa decisão reduz risco operacional e mantém o foco principal na comparação quantitativa dos algoritmos.

## Guia de interação e reprodução

Execute os comandos a partir da raiz do repositório. As interfaces disponíveis
estão reunidas nas seções abaixo:

- [Preparar o ambiente](#instalação-local-mínima-com-uv).
- [Menu interativo e suas opções](#menu-interativo-de-terminal).
- [Geração automatizada pela CLI](#primeiro-teste-pela-cli).
- [Avaliação, parsing e geração pela API Python](#api-python-para-scripts-e-notebooks).
- [Voxelização de superfície](#voxelização-direta-de-superfície-para-diagnóstico).
- [Malhas](#exportação-de-volumes-gerados-para-malha) e [visualização](#visualização-de-volumes).
- [Ferramentas legadas e frentes futuras](#interfaces-legadas-e-frentes-futuras).
- [Roteiro de reprodução científica](#roteiro-de-reprodução-do-experimento).
- [Testes e checagens](#validação-para-contribuições-e-forks).

Nos exemplos, `uv run python` seleciona o ambiente do projeto. O mesmo comando
Python pode ser chamado por qualquer uma destas formas, conforme o ambiente:

| Ambiente | Prefixo do comando |
| --- | --- |
| uv | `uv run python` |
| PowerShell, ambiente local existente | `.\.venv\Scripts\python.exe` |
| Linux/macOS, ambiente local existente | `./.venv/bin/python` |
| Ambiente virtual já ativado ou Colab com pacote instalado | `python` |

Por exemplo, `uv run python -m cavegen` e
`.\.venv\Scripts\python.exe -m cavegen` abrem o mesmo menu. Substitua apenas
o prefixo nos demais comandos. Exemplos multilinha com `\` usam sintaxe de
shell POSIX; no PowerShell, reúna-os em uma linha.

## Algoritmos previstos

- Random Walk 3D ponderado por waypoints, portado do projeto base
  3D-Cave-Generation ([`docs/random-walk.md`](docs/random-walk.md))
- Cellular Automata 3D básico; uma variante guiada por campo procedural
  poderá ser estudada depois
- Ajuste genético dos parâmetros de CA e Random Walk
- GAN 3D, após auditar a semântica e a independência dos volumes de treino
- PCGRL 3D, após definir e validar um ambiente pequeno e a recompensa

## Convenção de volume

Neste repositório, um volume 3D é representado por um `numpy.ndarray` booleano de forma `(depth, height, width)`.

- `True`: voxel aberto, isto é, espaço de caverna/túnel.
- `False`: voxel fechado/sólido.

Essa convenção descreve os **volumes gerados**. Na grade diagnóstica de
superfície do Elaphes, `True` significa parede observada. Não existe uma
conversão validada dessa grade para o ar interno real.

Para o SDF de um volume gerado com vazio conhecido, o contrato adotado é
`float32[D,H,W]` em ZYX: **positivo no interior do vazio**, **negativo no
exterior sólido** e **zero na borda**, com distância euclidiana em **voxels**
até o voxel de borda mais próximo. O protótipo de SDF do Random Walk, que
ficou no histórico da branch `CA` (`a58155e`), usava essa convenção. A regra
de borda e a origem do campo devem ser registradas; o SDF ainda não é uma API
integrada ao pacote principal.

## Estrutura

```text
cavegen-tcc/
├── configs/              # Configurações de algoritmos, experimentos e hardware
├── data/                 # Dados externos, brutos, processados e referências
├── docs/                 # Arquitetura, roadmap e decisões metodológicas
├── models/               # Checkpoints de modelos treinados
├── notebooks/colab/      # Notebooks de treino e prototipação no Colab
├── proto/                # Arquivos .proto para a fase gRPC
├── results/              # CSVs, figuras, meshes e relatórios de profiling
├── src/cavegen/          # Pacote Python principal
└── unity/                # Visualizador Unity e futura integração gRPC
```

## Instalação local mínima com uv

O projeto usa `pyproject.toml` como fonte principal das dependências. O `uv` cria o ambiente virtual, instala o pacote em modo editável e sincroniza as dependências declaradas no projeto.

```bash
uv sync
```

Para instalar também as dependências de aprendizado de máquina e profiling:

```bash
uv sync --extra ml --extra profiling
```

No Google Colab, quando estiver trabalhando a partir de uma cópia do repositório:

```bash
pip install uv
uv pip install -e . --system
```

Os arquivos em `requirements/` ficam apenas como fallback/compatibilidade para ambientes em que `uv` não estiver disponível.

Em uma nova cópia sem ambiente virtual, a instalação alternativa pelo Python
no Windows é:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

Para instalar os extras nessa alternativa, use
`.\.venv\Scripts\python.exe -m pip install -e ".[ml,profiling]"`.
Essa instalação resolve as restrições do `pyproject.toml`; para repetir a
resolução versionada em `uv.lock`, prefira `uv sync --locked`. Dependências
opcionais de ML/profiling não são necessárias para o menu e as métricas estruturais.

## Dados externos locais

As point clouds grandes disponíveis nesta máquina devem ser acessadas
preferencialmente no volume externo `D:`, sem cópia para o repositório. O
caminho exato de cada dataset deve ser configurado ou informado no momento da
execução, pois a organização do volume é local e pode mudar.

Três cavernas obtidas entre as 16 usadas na fonte associada ao
KarstConduitCatalogue ainda estão em descompactação. Elas não devem ser
tratadas como entradas disponíveis até a extração terminar. Antes de criar ou
escolher um parser, validar formato, cabeçalho, tamanho, eixos e unidade de
cada conjunto. O processamento deve continuar incremental, preservar
`float32` e não carregar a point cloud completa por padrão.

## Validação para contribuições e forks

Depois de sincronizar as dependências, execute a suíte unitária completa antes
de abrir um PR, criar um commit importante ou integrar mudanças de outra
branch:

```bash
uv run python -m unittest discover -s tests -v
```

Para investigar apenas um módulo, substitua o caminho pelo arquivo desejado:

```bash
uv run python -m unittest tests/test_normalization.py -v
```

Os comandos abaixo são verificações leves que não exigem os datasets externos:

```bash
# Confere se a interface de linha de comando pode ser importada.
uv run python -m cavegen.datastream.run_reference_voxelization --help

# Detecta espaços em branco e outros problemas de patch no Git.
git diff --check
```

## Padrão das mensagens de commit

A partir de agora, cada commit deve ter um título conciso sobre a mudança e
um corpo com esta estrutura, mantendo a ordem e os nomes das três seções:

```text
1. O que havia sido planejado:
   Descrever o que era planejado ser feito antes desse commit.

2. O que foi feito:
   Descrever o que de fato foi feito, com qual objetivo e como se alinha
   ao histórico de commits anteriores. Incluir verificações relevantes
   e seus resultados reais, inclusive falhas conhecidas.

3. O que será feito após este commit:
   Descrever pendências adiante e próximos passos, distinguindo planos
   de resultados já obtidos.
```

## Menu interativo de terminal

Na raiz do repositório, abra a interface de geração e métricas:

```bash
uv run python -m cavegen
```

No PowerShell, usando diretamente o ambiente já existente:

```powershell
.\.venv\Scripts\python.exe -m cavegen
```

O menu permite gerar um volume `64³`, executar as seeds de um YAML, reavaliar
NPZ existentes, consultar a tabela central e mudar os destinos da sessão.
Enter aceita o valor mostrado; `:voltar` ou Ctrl+C cancela a ação. O glossário
de cada opção está em [métricas estruturais](docs/metricas-estruturais.md#menu-interativo-e-glossário).

Também é possível abrir a interface com `uv run python -m cavegen.menu`.

| Opção | Operação | Saída |
| --- | --- | --- |
| `1` | Gerar Random Walk ou CA básico em `64³`, informando seed e parâmetros | NPZ e nova linha de métricas no CSV |
| `2` | Executar algoritmos/seeds de um YAML, padrão `baseline_64.yaml` | Uma linha por execução concluída e seus NPZ |
| `3` | Reavaliar NPZ existente com conectividade e spacing explícitos | Linha `structural_evaluation`, preservando o volume |
| `4` | Consultar as últimas linhas da tabela | Exibição no terminal, sem alteração de arquivos |
| `5` | Escolher CSV e pasta de geração individual da sessão | Destinos válidos durante a sessão; o YAML mantém sua própria pasta de volumes |
| `6` | Consultar ajuda e atalhos | Texto no terminal |
| `0` | Sair | Resultados concluídos permanecem salvos |

Os padrões são `results/csv/experiments.csv` e `results/volumes`. Os caminhos
são relativos ao diretório de execução, salvo quando absolutos. O menu atual
opera geração e métricas; parsing de novas cavernas ainda não tem uma opção
própria. Para leitura incremental já implementada, consulte a API abaixo.

Funcionalidades futuras que exigirem repetir comandos, incluindo parsing,
coleta e geração, devem ser integradas a esse menu, reutilizando as mesmas
funções de serviço das interfaces automatizáveis.

## Primeiro teste pela CLI

Gere volumes de Random Walk e Cellular Automata na grade padrão `64³`:

```bash
uv run python -m cavegen.benchmark.run_generation_benchmark \
  --config configs/experiments/baseline_64.yaml \
  --out results/csv/experiments.csv
```

Cada execução acrescenta uma linha à tabela central, com identidade,
parâmetros efetivos, versões, ocupação, componentes, distâncias e custo inicial.
Os NPZ ficam em subpastas de `results/volumes/` por experimento, com caminhos
na própria tabela; novas invocações preservam os resultados anteriores.
`baseline_64.yaml` ainda é uma configuração de desenvolvimento, sem protocolo
final de ajuste/repetições. O benchmark histórico `baseline_32.yaml` permanece
disponível quando solicitado explicitamente.

O contrato `StructuralMetrics`, os casos degenerados, a explicação de EDT e
conectividade e a proposta de reaproveitamento da linha central estão em
[`docs/metricas-estruturais.md`](docs/metricas-estruturais.md).
O CSV inicial tem cabeçalho diferente dos CSVs antigos e exige um único
escritor por vez; não aponte o novo benchmark para a tabela histórica.

Para consultar as flags sem gerar dados:

```bash
uv run python -m cavegen.benchmark.run_generation_benchmark --help
```

## API Python para scripts e notebooks

Após instalar o pacote, execute os exemplos no REPL Python, em um script ou
notebook. A CLI e o menu reutilizam esses serviços.

Avaliar um volume em memória não grava arquivos:

```python
from cavegen.generators.random_walk import generate_random_walk
from cavegen.metrics import evaluate_structure

volume = generate_random_walk(seed=42)  # padrão 64³ em ZYX
result = evaluate_structure(volume, connectivity=6, spacing_zyx=(1, 1, 1))
print(result.to_record())
```

Para reavaliar um NPZ e acrescentar uma linha à tabela, sem regenerar o volume:

```python
from cavegen.benchmark.structural_evaluation import evaluate_archive

row = evaluate_archive(
    "results/volumes/EXPERIMENT_ID/random_walk_RUN_ID.npz",
    "results/csv/experiments.csv",
    connectivity=6,
    spacing_zyx=(1, 1, 1),
)
print(row["run_id"])
```

Substitua o caminho pelo `volume_path` real da tabela. Essa operação também
está na opção `3` do menu; não tem uma CLI própria. Sua variante é
`structural_evaluation`, com tempo de geração e RSS ausentes.

Para automatizar a geração, use
`cavegen.benchmark.run_generation_benchmark.run(config_path, out_csv)` ou
`run_configuration(config, out_csv)` com um dicionário equivalente ao YAML.
Os geradores individuais são `generate_random_walk` e
`cavegen.generators.cellular_automata.generate_cellular_automata`; ambos
retornam `Volume3D`. A persistência isolada usa `save_volume_npz` e
`load_volume_npz` de `cavegen.datastream.voxel_io`.

Os leitores de point clouds são APIs incrementais, não comandos independentes:

```python
from itertools import islice

from cavegen.datastream.ply import iter_ply_xyz
from cavegen.datastream.f32 import iter_f32_xyz
from cavegen.datastream.bounds import calculate_xyz_bounds
from cavegen.datastream.sampling import reservoir_sample_xyz

# Caminhos ilustrativos: confirme os arquivos reais e o fim da descompactação.
ply_path = "D:/PASTA_DA_CAVERNA/caverna.ply"
batches = islice(iter_ply_xyz(ply_path, batch_size=65536), 10)
sample = reservoir_sample_xyz(batches, max_points=10000, seed=42)

# Para F32 compatível, trocar por iter_f32_xyz(caminho_f32, batch_size=65536).
# Varredura integral opcional, cara em datasets grandes:
# minimum, maximum = calculate_xyz_bounds(iter_ply_xyz(ply_path, batch_size=65536))
```

F32 exige registros de sete `float32`: XYZ, refletância NIR e RGB. A extensão
sozinha não garante compatibilidade. A amostra é de superfície e não pode ser
avaliada como volume de ar. O exemplo limita a leitura aos primeiros dez
lotes; a amostra é uniforme somente nesse prefixo, não na caverna inteira.
Remover `islice` exige uma varredura integral, embora a memória da amostragem
continue limitada. A voxelização PLY tem a CLI documentada a seguir;
normalização e voxelização independentes do formato estão em
`cavegen.core.normalization` e `cavegen.core.voxelization`.

Na branch `CA`, esse comando e o menu `python -m cavegen` ainda não rodam: o
benchmark importa `generate_cellular_automata`, ausente no pacote do CA, e o
Felipe vai escrever essa integração separadamente. O lado do Random Walk já usa
`caverna` e `raio_voxels` (grade cúbica com lado maior que 5). Para gerar só o
Random Walk, ver [`docs/random-walk.md`](docs/random-walk.md):

```bash
uv run python -m cavegen.generators.random_walk.generator [seed] [lado] [raio|proporcional]
```

## Voxelização direta de superfície para diagnóstico

Para inspecionar uma nuvem de pontos PLY como grade de voxels de superfície,
execute uma primeira passagem em baixa resolução. O leitor processa o arquivo
em lotes, portanto não carrega toda a nuvem na memória:

```bash
uv run python -m cavegen.datastream.run_reference_voxelization \
  --ply /caminho/para/elaphes_cave.ply \
  --bounds data/params/elaphes_xyz_bounds.json \
  --shape 32 32 32 \
  --batch-size 65536 \
  --progress-every 1000000 \
  --output data/processed/references/elaphes_surface_32.npz \
  --report-slices
```

O comando usa os limites XYZ previamente calculados, normaliza os pontos para
índices ZYX, mostra o progresso a cada milhão de vértices e salva a grade como
um `.npz` comprimido. O arquivo preserva os limites XYZ, a resolução, o caminho
da fonte e a convenção de normalização. Nessa grade, `True` significa superfície
observada, e não espaço aberto de caverna. Ela serve ao diagnóstico do scan e
não fornece a classificação volumétrica necessária para IoU.

Execução registrada para o Elaphes em `32³`: 245 de 32.768 voxels (0,75%) foram
marcados como superfície. O arquivo `elaphes_surface_32.npz` é um artefato local
de dados processados e não faz parte do Git.

## Limite da referência real

Os experimentos com amostragem, Screened Poisson, linha central, orientação
de normais e espessamento não produziram uma malha com interior validado para
o Elaphes. Mesmo as malhas sem arestas de borda no teste de dilatação tiveram
auto-interseções. A grade de parede observada não pode ser invertida para
obter o vazio: seu complemento reúne interior, exterior e regiões não
observadas. Assim, SDF real e IoU volumétrica contra o scan não fazem parte
do benchmark atual. Os experimentos estão preservados na branch
`experiment/elaphes-meshing` e em artefatos locais; o
[resumo quinzenal](docs/relatorios/resumo-quinzenal-tcc-2026-10-18.docx)
registra os resultados e limites.

Na branch `CA` (`a58155e`), o CA já aceita um peso espacial somado à
contagem de vizinhos. Há testes de equivalência entre ausência de peso e
peso zero. A branch também contém flood fill e EDT experimentais da grade
de **parede** do Elaphes. O campo do Elaphes usa o mesmo sinal e unidade,
mas seu "interno" pode representar parede ou buracos fechados; não fornece
`VOID` real validado.
Na mesma branch, o gerador de Random Walk passou a ser o random walk
ponderado por waypoints do projeto base (3D-Cave-Generation), em
`src/cavegen/generators/random_walk/`, no lugar do random walk de 6 direções;
ver [`docs/random-walk.md`](docs/random-walk.md). Os waypoints vêm de modelos
de cavernas reais, então essa caverna não é um controle totalmente
independente de referências. Um guia procedural com semântica, escala e
sinal definidos continua pendente. O benchmark mede pelo `ResourceSampler`, mas
ainda não importa na branch, por falta da integração do CA. O ajuste genético de CA e Random Walk está planejado, com custo de
busca separado do tempo de geração.

## Exportação de volumes gerados para malha

```bash
uv run python -m cavegen.meshing.export_mesh \
  --input results/volumes/EXPERIMENT_ID/random_walk_RUN_ID.npz \
  --output results/meshes/random_walk_seed_0.obj
```

Substitua a entrada pelo `volume_path` registrado no CSV da execução desejada.

## Visualização de volumes

Os scripts recebem o caminho do NPZ como primeiro argumento. Substitua os
identificadores pelo caminho real da tabela:

```bash
uv run python plots/matriz.py "results/volumes/EXPERIMENT_ID/random_walk_RUN_ID.npz"
uv run python plots/plot_matplotlib.py "results/volumes/EXPERIMENT_ID/random_walk_RUN_ID.npz"
uv run python plots/plot_plotly.py "results/volumes/EXPERIMENT_ID/random_walk_RUN_ID.npz"
```

`matriz.py` imprime um resumo; Matplotlib salva PNG em `results/figures/` e
abre uma janela; Plotly salva HTML nessa pasta e abre a figura interativa.
O HTML atual carrega Plotly por CDN e requer acesso à biblioteca para exibição.
Os nomes das figuras derivam do NPZ e podem ser reutilizados numa nova
plotagem. A amostragem visual do Plotly não altera as métricas do volume.

`fatia.py` é um script exploratório com entrada fixa
`results/volumes/random_walk_seed_0.npz`, sem argumento para selecionar NPZ.
Depende desse artefato histórico e não integra o fluxo atual de reprodução.

## Interfaces legadas e frentes futuras

| Interface | Como acessar | Estado e limite |
| --- | --- | --- |
| Resumo estatístico legado | `uv run python -m cavegen.benchmark.summarize_results --input results/csv/baseline_32.csv --output results/csv/baseline_32_summary.csv` | Agrupa apenas por algoritmo. Usar somente um conjunto homogêneo; não resumir diretamente o CSV central com variantes/experimentos misturados. O destino é regravado. |
| IoU genérica | `uv run python -m cavegen.benchmark.run_iou_benchmark --reference CAMINHO_VOID_VALIDADO.npz --generated-dir PASTA_DO_EXPERIMENTO --out results/csv/iou.csv` | Exige volumes de vazio comparáveis, alinhados e com mesmo shape. Lê NPZ diretamente na pasta indicada, sem recursão; destino regravado. Não usar a superfície do Elaphes. Fora do benchmark atual. |
| Treino GAN | `uv run python -m cavegen.training.train_gan` | Placeholder: encerra com mensagem, sem treinar. |
| Treino PCGRL | `uv run python -m cavegen.training.train_pcgrl` | Placeholder: encerra com mensagem, sem treinar. |
| Colab | [Orientações de notebooks](notebooks/colab/README.md) | Sequência planejada; os notebooks sugeridos ainda precisam ser criados. |
| Unity e gRPC | `unity/`, `proto/caves.proto`, `cavegen.datastream.grpc_adapter` | Há contrato/serialização, mas não um aplicativo Unity ou servidor gRPC integrado para executar. |
| Menu experimental do CA | Na branch `CA`: `uv run python -m cavegen.generators.cellular_automata.menu` | Disponível naquela branch, com API própria. Não existe nesse caminho no `main`; não misturar resultados sem conferir implementação e contrato. |
| Reconstrução e linha central do Elaphes | Branch `experiment/elaphes-meshing` | Comandos e artefatos descritos na documentação daquela branch; não são etapas exigidas na avaliação atual. |

As CLIs com `argparse` oferecem `--help`: geração, voxelização de superfície,
exportação de malha, resumo estatístico e IoU. O menu oferece a opção `6` de
ajuda. APIs Python e scripts de plotagem não compartilham essas mesmas flags.

## Roteiro de reprodução do experimento

1. Registrar a revisão e o estado do código com `git rev-parse HEAD` e
   `git status --short`. Para outra máquina reproduzir as mudanças, usar uma
   revisão commitada; `-dirty` não substitui um snapshot do código.
2. Sincronizar dependências com `uv sync --locked` e executar as checagens da
   seção de validação. Em outras instalações, registrar as versões efetivas.
3. Conferir `configs/experiments/baseline_64.yaml`: shape, seeds e parâmetros.
   Não alterar o YAML entre execuções que deveriam reproduzir o mesmo caso.
4. Executar `uv run python -m cavegen.benchmark.run_generation_benchmark`
   ou escolher a opção `2` do menu com o mesmo YAML e destino CSV.
5. Consultar `results/csv/experiments.csv` pela opção `4` ou por um leitor CSV.
   Cada linha identifica experimento, execução, versões, seed, argumentos,
   contrato de métricas e caminho do NPZ. Preservar CSV e NPZ juntos.
6. Para conferir uma geometria existente, usar a opção `3` ou
   `evaluate_archive`. Filtrar `variant` antes de analisar resultados: uma
   reavaliação não é outra geração independente. Exportar/plotar os NPZ
   selecionados quando for necessária inspeção visual.
7. Comparar somente resolução, conectividade, spacing, contratos e condições
   experimentais compatíveis. Repetir a seed reproduz a geometria sob a mesma
   implementação/versões; IDs, timestamps, tempos e RSS podem variar.

O baseline `64³` atual permite reproduzir o pipeline de desenvolvimento.
Sementes finais, repetições de desempenho, orçamento de ajuste e inventário
completo de hardware ainda precisam ser fechados antes da coleta científica
final. O monitor atual registra tempo e RSS amostrado; CPU/GPU/VRAM ainda
exigem padronização adicional. A suíte tem uma falha F32 conhecida no Windows
por `memmap` aberto durante a limpeza do teste, detalhada em
[métricas estruturais](docs/metricas-estruturais.md#memória-e-verificação).

Datasets reais não são necessários para gerar/avaliar os baselines sintéticos.
Para reproduzir diagnósticos de superfície, fornecer os arquivos externos e
seus limites/proveniência. O JSON versionado de limites do Elaphes não substitui
a point cloud. Dados, volumes e tabelas gerados são ignorados pelo Git e devem
ser transferidos separadamente quando necessários à reprodução.

## Roadmap resumido

1. Pablo implementa e padroniza a coleta de métricas, incluindo contratos,
   casos degenerados, unidades, recursos computacionais e esquema de saída.
2. Com essa interface estável, Pablo implementa GAN e PCGRL sob o contrato
   `Volume3D`, mantendo treino separado de geração/inferência.
3. Pablo inventaria e parseia incrementalmente as novas cavernas no volume
   `D:` após a conclusão das descompactações.
4. Em paralelo, Felipe continua CA e Random Walk e, depois, implementa o
   algoritmo evolutivo para ajustar os dois geradores usando as métricas
   padronizadas.
5. Após a coleta e a análise, padronizar a documentação, consolidar os
   resultados e inspecionar volumes e malhas na Unity.

A lista detalhada, com decisões ainda abertas, está em
[`Orientacao-codex.md`](Orientacao-codex.md). A justificativa das métricas e da
delimitação do scan está em [`docs/methodology-adjustments.md`](docs/methodology-adjustments.md).
O Random Walk está descrito em [`docs/random-walk.md`](docs/random-walk.md).
As tarefas individuais estão em
[`Pablo`](docs/tarefas-pablo-reconstrucao-modelos.md) e
[`Felipe`](docs/tarefas-felipe-sdf-ca.md).

## Observação sobre benchmarks

As métricas finais devem ser calculadas em ambiente controlado e reportadas com separação clara entre:

- tempo de treinamento;
- tempo de inferência/geração;
- custo de renderização/visualização;
- custo de integração, caso gRPC seja usado.

Não misture resultados de Colab, máquina local e ROCm na mesma tabela principal sem identificá-los como ambientes distintos.

As medições finais de estrutura usarão volumes `64³` em ZYX. CA e Random Walk
podem permanecer na CPU enquanto modelos neurais usam GPU para treino ou
inferência; o backend deve aparecer nos resultados de custo. Não é requisito
portar o CA para GPU apenas para produzir os mesmos volumes. Uma comparação
direta de tempo precisa considerar ambiente, etapa medida e transferências.
