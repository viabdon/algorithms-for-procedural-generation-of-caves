# Métricas estruturais e tabela de execuções

Implementação de 02/11/2026. Este registro cobre o contrato estrutural até
`evaluate_structure`, as perguntas sobre distância, conectividade e linha
central e a persistência inicial em uma tabela única. A padronização completa
da instrumentação computacional continua sendo uma etapa posterior.

## Entrada, API e grade de referência

O padrão de geração passa a ser `(64, 64, 64)` em ZYX, tanto nas funções de
Random Walk e CA quanto no benchmark sem `shape` explícito. São 262.144 voxels.
`configs/experiments/baseline_64.yaml` é uma configuração de desenvolvimento;
as cinco sementes e os parâmetros herdados não constituem o protocolo final
de repetições ou de ajuste. A configuração histórica `baseline_32.yaml`
continua disponível para reprodução explícita.

As funções matemáticas aceitam grades menores ou não cúbicas para permitir
diagnósticos e testes com respostas verificáveis manualmente. Uma comparação
de resultados finais deve selecionar apenas a grade padrão e contratos iguais;
não há redimensionamento automático de entradas.

```python
from cavegen.generators.random_walk import generate_random_walk
from cavegen.metrics import evaluate_structure

volume = generate_random_walk(seed=42)  # bool[64,64,64], True = ar
metrics = evaluate_structure(volume, connectivity=6, spacing_zyx=(1, 1, 1))
row = metrics.to_record()
print(row["component_count"], row["dt_mean"])
```

O agregador recebe `Volume3D`; as funções individuais recebem `numpy.ndarray`.
A validação compartilhada em `metrics/validation.py` exige:

- dtype booleano e exatamente três dimensões não vazias;
- conectividade inteira 6 ou 26, rejeitando 18, floats, strings e booleanos;
- três espaçamentos reais, positivos e finitos em ordem ZYX, sem booleanos.

Arrays read-only e views são aceitos sem cópia de validação. A avaliação não
altera voxels, metadados nem estado aleatório. `Volume3D` já convertia arrays
numéricos para booleano em seu construtor; a nova avaliação valida o conteúdo
que recebe e não modifica esse comportamento do contêiner. Quem precisa
detectar dtype numérico antes dessa conversão deve validar o array original.

É responsabilidade de quem chama fornecer um volume de ar conhecido.
Uma grade de superfície embrulhada em `Volume3D` continua semanticamente
inadequada, mesmo tendo dtype e shape válidos. O Elaphes não é uma referência
de `VOID` validada. Point clouds devem ser acessadas preferencialmente no
volume `D:` após o término das descompactações.

## Transformada da distância: cálculo e interpretação

Para cada voxel aberto `p`, a distância euclidiana ao centro do voxel sólido
mais próximo `q` é:

```text
d(p) = min_q sqrt(((pz-qz)*sz)^2 + ((py-qy)*sy)^2 + ((px-qx)*sx)^2)
```

`sz, sy, sx` são os espaçamentos. O fundo `False` representa sólido. Em volumes
mistos, acrescentamos uma camada externa sólida antes da EDT e resumimos
somente os voxels abertos da grade original. A operação usa
[`scipy.ndimage.distance_transform_edt`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.distance_transform_edt.html),
que calcula a distância euclidiana ao fundo com espaçamento por eixo.

O resultado expõe média, mediana e máximo sobre **todos** os voxels abertos,
inclusive os de componentes pequenas. É uma média ponderada pelos voxels, não
uma média por túnel ou por componente. Uma câmara grande pode dominar a média;
a mediana descreve o voxel aberto típico e o máximo destaca a região com
maior afastamento do sólido.

Exemplo: um bloco aberto `3×3×3`, cercado por sólido, contém 26 voxels a
distância 1 e um central a distância 2. A média é `28/27`, a mediana é 1 e o
máximo é 2. Num túnel de um voxel de espessura, todas as distâncias são 1 com
spacing unitário. Esses exemplos têm testes com expectativas independentes.

A distância é entre centros: um voxel aberto adjacente ao sólido tem distância
1, e não zero nem meio voxel. Não fazemos correção de meia célula. Os valores
não são um SDF assinado nem uma largura de túnel validada; não multiplicar a
média por dois e apresentá-la como diâmetro real. O SDF sintético do projeto
tem outro contrato, com zero nos voxels de borda do vazio.

Com `(1,1,1)`, `distance_unit` é `voxel`. Com spacing diferente, é
`spacing_unit`; o experimento precisa registrar que unidade foi fornecida.
Não se infere metro a partir da resolução nem dos metadados do gerador.
As distâncias do SciPy usam temporários float64, sem modificar o dtype dos
volumes ou de quaisquer coordenadas de point clouds.

## Connectivity: conectividade e componentes

Cada voxel aberto é um vértice. A regra de vizinhança define quais vértices
podem ser ligados diretamente:

| Regra | Contato admitido | Dois voxels que só se tocam pelo canto |
| --- | --- | --- |
| 6, padrão | Uma das seis faces | Duas componentes |
| 26 | Faces, arestas e cantos | Uma componente |

Usamos [`scipy.ndimage.label`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.label.html)
com uma estrutura explícita. Voxel sólido recebe rótulo 0; cada conjunto de
voxels abertos alcançáveis entre si recebe outro rótulo. Não há conexão
periódica entre lados opostos da grade. O spacing muda comprimentos, mas não
essa regra de contato.

O resultado inclui número de componentes, tamanho da maior e a razão:

```text
largest_component_ratio = voxels da maior componente / todos os voxels abertos
```

Se existem componentes com 30 e 10 voxels, a razão é `30/40 = 0,75`.
`open_ratio`, por sua vez, divide os 40 voxels pelo tamanho da grade inteira.
As duas medidas respondem a perguntas diferentes: quanto espaço foi aberto
e quanto desse espaço está conectado. Razão 1 indica uma única componente
aberta; também ocorre com um único voxel isolado, portanto deve ser lida junto
da ocupação. Contato por canto em 26 vizinhos não garante passagem com largura
suficiente para trânsito. A comparação principal registra conectividade 6.

Empates entre maiores componentes selecionam o primeiro rótulo na ordem do
array. A avaliação contabiliza todas as componentes; ela não executa limpeza
ou remove bolsões para melhorar o resultado.

## Casos degenerados

| Caso | Ocupação | Componentes | Maior componente / ar | EDT | Motivo |
| --- | ---: | ---: | ---: | --- | --- |
| Tudo sólido | 0 | 0 | 0 por convenção | `None` | `no_open_voxels` |
| Tudo aberto | 1 | 1 | 1 | `None` | `no_solid_voxels` |
| Volume misto | Entre 0 e 1 | Pelo menos 1 | Entre 0 e 1 | Calculada | `None` |

Nos dois primeiros casos, `is_degenerate=True`. A EDT de um volume totalmente
aberto fica ausente por decisão do protocolo, embora a camada externa
artificial permitisse produzir números. Evitamos interpretar o próprio
domínio inteiro aberto como uma caverna com tamanho de túnel mensurado.
Essa exceção é verificada antes de chamar o SciPy. Desconexão, por si só, não
torna um volume misto degenerado.

Ausência é `None` em Python, `null` em JSON e célula vazia no CSV. Não se troca
ausência por zero. A penalidade de um candidato degenerado pertence à futura
função de aptidão, não à definição das métricas.

## O que mudou nos contratos anteriores

| Antes | Contrato implementado |
| --- | --- |
| Qualquer conectividade diferente de 6 virava 26 | Apenas inteiros 6 e 26 são aceitos |
| Arrays numéricos eram convertidos implicitamente nas métricas | Funções individuais exigem bool 3D não vazio |
| EDT do volume sem ar retornava zeros | EDT ausente e degeneração explícita |
| Exterior da EDT não estava declarado | Camada sólida explícita em volumes mistos |
| Sugestão de nomes `distance_*_voxels` com spacing variável | Campos `distance_mean/median/max`, spacing e unidade explícitos |
| `_row` calculava métricas de forma dispersa | `evaluate_structure(...).to_record()` fornece colunas versionadas |

As colunas CSV `dt_mean`, `dt_median`, `dt_max`, `open_ratio` e
`largest_component_ratio` conservam seus nomes para facilitar leitura, mas
agora acompanham `structural_schema_version=structural-v1`. O CSV histórico
não deve ser concatenado silenciosamente ao novo: seu contrato de borda,
degeneração e resolução pode ser diferente. Arquivos com cabeçalho antigo
são rejeitados antes de acrescentar uma linha.

Essas ambiguidades foram identificadas na revisão do contrato, antes dos
testes novos. Não foi necessário mudar expectativas de teste para aceitar
resultados incorretos. A decisão de manter EDT ausente no caso todo aberto
foi preservada e documentada expressamente.

## Ramificações e reaproveitamento da linha central

O trabalho da branch `experiment/elaphes-meshing` é reaproveitável. Consulte,
naquela branch, `docs/metodologia/linha-central-elaphes-exploracao.md` e
`docs/resumos-teoricos/linha-central-racine.md` (referência `21cff18`).
O método exploratório contrai pontos da superfície por Laplaciano, reduz os
nós e os liga por uma árvore geradora mínima. A fonte é a seção 2.7 de
[Racine et al. (2025)](https://essd.copernicus.org/articles/17/4671/2025/).

Com um grafo aceito, contar graus é simples: grau 1 sugere ponta, grau 2 é
continuação e grau pelo menos 3 sugere junção. Em um esqueleto voxelizado,
vários voxels de alto grau podem representar uma única junção física; é
necessário agrupá-los antes da contagem. Ramos podem ser definidos como
caminhos entre junções e pontas, contraindo sequências de grau 2.

A parte a validar é a extração desse grafo a partir do volume gerado. Uma
árvore elimina ciclos, portanto não conserva toda a topologia de uma caverna
com laços. A extração experimental da nuvem não equivale automaticamente a
uma esqueletização do ar conhecido. Podemos reaproveitar a representação,
os comprimentos e a análise por graus, avaliando separadamente o extrator.

O ensaio anterior mostrou sensibilidade real: uma bifurcação do recorte
curto desapareceu ao ampliar a janela; a poda protegeu manualmente um ramo
curto reconhecido como real. Um limiar genérico removeria esse ramo. Antes de
adotar ramificação como métrica comum, testar tubo reto, Y, T, ciclo e ruído,
fixar vizinhança, agrupamento de junções e regra de poda, e registrar sua
versão. A métrica ainda não foi implementada nesta entrega até o tópico 5.

## Uma tabela para todas as execuções experimentais

O benchmark usa por padrão `results/csv/experiments.csv`:

```bash
python -m cavegen.benchmark.run_generation_benchmark
# Equivalente explícito:
python -m cavegen.benchmark.run_generation_benchmark --config configs/experiments/baseline_64.yaml --out results/csv/experiments.csv
```

Use o Python do ambiente do projeto; `uv run python` é uma alternativa quando
`uv` estiver instalado. O CSV é o índice central dos resultados escalares.
Os volumes continuam NPZ, com o caminho registrado na própria linha. Não é
necessário abrir JSONs externos para localizar seed, parâmetros e métricas.

| Grupo de colunas | Conteúdo |
| --- | --- |
| Identidade | `run_id`, `experiment_id`, `recorded_at_utc`, `experiment_name` |
| Geração | `algorithm`, `variant`, `seed`, `repetition`, `parameters_json`, `volume_path` |
| Software e ambiente | `config_path`, `code_revision`, Python, NumPy, SciPy, plataforma, backend |
| Contrato estrutural | versão, eixos, dimensões, spacing, conectividade, política externa e referência da distância |
| Resultados estruturais | ocupação, componentes, maior componente, EDT e degeneração |
| Custo inicial | tempo de geração, RSS amostrado, número de amostras e intervalo solicitado |

`parameters_json` é uma célula da tabela com os argumentos efetivos do gerador,
incluindo defaults, shape e seed; não é outro arquivo. Novas invocações geram
identificadores e subpastas próprios, preservando os NPZ anteriores.
Os parâmetros de execução são dados, não colunas criadas dinamicamente.

Cada execução concluída é persistida imediatamente após a avaliação e o NPZ.
As próximas invocações acrescentam linhas. Cabeçalho incompatível ou run_id
duplicado causam erro sem alterar o CSV existente. O gravador usa leitura
incremental dos IDs e um único escritor sequencial. Uma queda durante a escrita
não tem recuperação transacional; concorrência, registros de falhas e retomada
automática exigem outra etapa. Um erro após salvar o NPZ pode deixar um arquivo
sem linha correspondente; as linhas já salvas permanecem preservadas.

`evaluate_structure` permanece puro: produz resultado imutável sem salvar nada.
`to_record()` produz as colunas estruturais; `append_experiment_record` é a
função reutilizável de persistência. Testes unitários verificam esses contratos
em diretórios temporários, sem contaminar a tabela de experimentos.

O monitor de tempo/RSS ainda é o inicial: métricas, salvamento e escrita ficam
fora do tempo de geração. RSS é do processo inteiro, amostrado, não uma medida
exata da alocação exclusiva do gerador. Sem amostras, fica vazio. CPU, GPU,
VRAM, inventário completo de hardware e repetições de desempenho continuam
pendentes. `repetition=0` registra a única medição atual por seed; repetições
de tempo não devem ser confundidas com novas sementes geométricas.

O identificador Git pode conter `-dirty` para edições rastreadas; ele não é
snapshot dos arquivos ainda não versionados. Para reprodução em outra
máquina, usar código commitado e as versões/argumentos registrados. Não
agrupar configurações ou contratos diferentes só por nome de algoritmo.
O resumidor legado agrupa apenas por algoritmo e deve ser atualizado antes
de resumir uma tabela central com experimentos diferentes.

## Menu interativo e glossário

A interface segue o padrão de perguntas e repetição do menu do CA na branch
do Felipe. Ela opera os serviços disponíveis no `main`, com o CA básico de
26 vizinhos; não importa ou substitui a implementação experimental da outra
branch. Execute na raiz do repositório:

```bash
uv run python -m cavegen
# Alternativa com o ambiente ativo:
python -m cavegen
```

No PowerShell, sem ativar o ambiente:

```powershell
.\.venv\Scripts\python.exe -m cavegen
```

`python -m cavegen.menu` abre a mesma interface. Comandos diretos do benchmark
continuam disponíveis para scripts. A interface usa texto simples e não exige
uma biblioteca nova de terminal.

| Comando | Ação e parâmetros | Efeito nos arquivos |
| --- | --- | --- |
| `1` — Gerar e avaliar um volume 64³ | Escolher Random Walk ou CA básico; informar seed e parâmetros com padrões visíveis. Random Walk pergunta passos e raio; CA pergunta probabilidade inicial de ar, iterações e limiar de vizinhos. | Gera NPZ em subpasta própria e acrescenta uma linha `baseline` ao CSV da sessão. |
| `2` — Executar experimento YAML | Informar o caminho da configuração, conferir shape/seeds e iniciar. O padrão é `configs/experiments/baseline_64.yaml`. | Executa todos os algoritmos/seeds do YAML, mostrando cada resultado persistido. Usa a pasta de volumes do YAML e o CSV da sessão. |
| `3` — Avaliar NPZ existente | Escolher entre as últimas dez linhas da tabela ou informar outro caminho. Definir conectividade 6/26 e spacing Z Y X; o padrão é `6` e `1 1 1`. | Mantém o NPZ original e acrescenta nova linha `structural_evaluation`, com novo run_id. Tempo de geração e RSS ficam ausentes. |
| `4` — Consultar resultados recentes | Informar quantas linhas mostrar, de 1 a 1000; o padrão é 10. Mostra identidade, variante, seed, shape, ocupação, componentes, EDT, conectividade, spacing e caminho do volume. | Apenas lê o CSV. Usa streaming e retém somente as linhas solicitadas, sem abrir os volumes. |
| `5` — Alterar destinos da sessão | Informar CSV central e pasta para volumes da geração individual. | Muda os caminhos somente na sessão atual. Não move, apaga ou sobrescreve arquivos e não modifica YAML. A opção 2 continua usando a pasta declarada no YAML. |
| `6` — Ajuda e glossário | Consultar as opções, atalhos e significado das ausências. | Apenas exibe ajuda. |
| `0` — Sair | Encerrar a interface pelo menu principal. | Mantém todos os resultados já salvos. |

Enter aceita o padrão mostrado entre colchetes. `:voltar` ou Ctrl+C cancela a
opção atual e retorna ao menu; EOF (fim da entrada) encerra a interface, mesmo
durante uma pergunta. Uma interrupção durante um lote preserva as linhas já
concluídas. Não há retomada automática ou registro de falhas por execução.

Os caminhos podem conter espaços e aspas externas. Caminhos relativos partem
do diretório de onde o programa foi iniciado; use caminhos absolutos para
trabalhar com destinos em outro volume. Alterações da opção 5 não persistem
entre sessões. O CSV inicial é `results/csv/experiments.csv` e a pasta da
geração individual é `results/volumes`. Abrir o menu não cria arquivos.

A opção 1 mantém a grade padrão `64³`; a opção 2 respeita a grade explícita
do YAML, inclusive configurações diagnósticas menores. A opção 3 respeita a
grade do NPZ e não redimensiona ou regenera sua geometria. Spacing é informado
com ponto decimal e três valores separados por espaços. Probabilidade e
spacing rejeitam NaN/infinito; entradas inválidas pedem correção.

Reavaliar com outra conectividade ou spacing é uma nova medição da **mesma
geometria**, não outra amostra independente. A variante `structural_evaluation`
identifica essa diferença na tabela; não agregar essas linhas com gerações
`baseline` como se fossem novas seeds. O campo `parameters_json` da reavaliação
guarda os metadados disponíveis no NPZ; pode não recuperar todos os argumentos
efetivos se um arquivo antigo não os preservou. Algoritmo desconhecido aparece
como `unknown` e seed ausente permanece vazia, sem inventar proveniência.

NPZ de `surface_voxels` é rejeitado pela opção 3. A interface não lê point
clouds nem tenta converter superfície em vazio. As próximas operações de
parsing devem ter opções próprias quando forem implementadas, respeitando a
preferência pelo volume `D:` e o término das descompactações.

### Organização para os próximos menus

O ponto de entrada é `src/cavegen/menu.py`. As perguntas e a apresentação
ficam nessa camada; as operações chamam `run_configuration` e
`evaluate_archive`, sem construir comandos de shell ou YAML temporário.
`create_experiment_context` e `make_experiment_record` são compartilhados para
manter as mesmas colunas da tabela anterior. A CLI de geração também usa esse
serviço; a refatoração preserva a ordem do cabeçalho existente.

Novas funcionalidades repetitivas devem acrescentar uma opção ou submenu a
essa interface e documentar seus parâmetros e efeitos neste padrão de
glossário. Preservar serviços chamáveis em Python e as CLIs para automação,
testando o fluxo por entradas/saídas e pelos artefatos realmente produzidos.

## Memória e verificação

A avaliação rotula componentes uma vez, descarta informação por voxel na
saída e usa memória proporcional ao número de voxels. A EDT cria padding,
distâncias e temporários do SciPy; não percorre nem carrega point clouds.
Em `64³` o volume booleano tem 256 KiB, mas esse valor não representa a memória
total da avaliação, que também inclui labels e temporários.

Os testes novos verificam expectativas geométricas manuais e uma referência
independente por enumeração de distâncias, sem chamar a EDT para calcular as
respostas esperadas. Também verificam repetibilidade, ausência de mutação,
spacing anisotrópico ZYX, inputs read-only, persistência incremental e igualdade
dos volumes de duas invocações com a mesma seed.

```bash
python -m unittest discover -s tests -v
python -m cavegen.benchmark.run_generation_benchmark --help
```

Na suíte original, antes das alterações, 27 dos 28 testes passaram. O teste
`test_f32.F32ReaderTests.test_counts_maps_and_iterates_xyz_records` falhou na
limpeza do diretório temporário com `PermissionError: [WinError 32]`: o
`numpy.memmap` permanece aberto quando o Windows tenta remover `points.f32`.
É um problema anterior de ciclo de vida do recurso no teste; não foi
alterado para produzir aprovação artificial desta entrega.

Resultado da verificação da entrega no Python 3.12.10, NumPy 2.5.0 e SciPy
1.18.0: os 20 testes novos passaram na primeira execução, e a suíte completa
teve 47 aprovações e a mesma falha F32 entre 48 testes. A checagem de importação
pela CLI e `git diff --check` passaram.

O benchmark de desenvolvimento `baseline_64.yaml` foi executado uma vez,
produzindo dez linhas em `results/csv/experiments.csv` e dez NPZ. Todos foram
reabertos; shape `64³` e cada campo estrutural foram conferidos contra a linha
correspondente. Os artefatos são locais, ignorados pelo Git. Não representam
a coleta final de desempenho, pois a política de hardware e repetições ainda
não está fechada.

Na seed 0 desse diagnóstico, Random Walk teve 18.349 voxels abertos em uma
componente, enquanto CA teve 41.236 voxels abertos em 44 componentes sob
conectividade 6. Isso ilustra por que ocupação e conectividade devem ser lidas
juntas: mais ar não implica que todo ele esteja conectado.

### Verificação do menu

Os dez testes de `tests/test_menu.py` exercitam a interface pública com entrada
de texto e arquivos reais em diretórios temporários. Cobrem geração de ambos
os algoritmos, reavaliação com conectividade/spacing diferentes, execução e
cancelamento de YAML, destinos com espaços, consulta limitada de linhas,
entradas inválidas, arquivo inexistente, superfície ou metadados incompatíveis,
EOF e Ctrl+C. A interrupção depois da primeira seed confirma que seu NPZ e
sua linha continuam salvos.

O primeiro teste de arquivo ausente identificou uma mensagem do Windows com
barras escapadas no caminho. A implementação passou a prefixar o caminho
literal na mensagem, preservando a expectativa do teste e facilitando copiar
o caminho exibido. Não foi necessário relaxar os contratos estruturais.

Após a inclusão do menu, a suíte tem 58 testes: 57 passaram e permanece a
falha F32 preexistente descrita acima. O lançamento real de
`python -m cavegen`, a ajuda e a saída foram conferidos pelo terminal.
A construção compartilhada de registros foi comparada ao CSV já existente:
suas 45 colunas e a ordem do cabeçalho foram preservadas, sem regravar a tabela.
