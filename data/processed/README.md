# Dados processados

```text
data/processed/
├── experiments/
│   └── experiment_elaphes-meshing/   # ensaios históricos do Elaphes
├── references/                      # superfícies e interiores candidatos de scans
├── crop_plans/                      # PLYs, linhas centrais e configurações de recortes
├── reference_sections/              # grades, máscaras e diagnósticos dos recortes
├── generated/
│   ├── cellular_automata/
│   │   ├── baseline_32/
│   │   └── baseline_64/
│   ├── random_walk/
│   │   ├── baseline_32/
│   │   └── baseline_64/
│   ├── gan_3d/
│   └── pcgrl_3d/
└── manifest.json                    # caminhos anteriores, atuais e hashes
```

Os 33 arquivos antes soltos na raiz foram reunidos em
`experiments/experiment_elaphes-meshing/`, incluindo amostras, grafos,
normais, grades e relatórios auxiliares. A associação à branch
`experiment/elaphes-meshing` vem dos comandos e nomes registrados em sua
documentação. Como são arquivos locais ignorados pelo Git, essa associação
não comprova em qual checkout cada arquivo foi criado.

Os NPZ e CSV foram preservados byte a byte. Os caminhos nos relatórios JSON
foram atualizados; o inventário registra hashes anteriores e atuais. Eventuais
caminhos embutidos nos NPZ continuam históricos. Comandos antigos da branch
de experimentos precisam usar o novo prefixo ao consumir esses arquivos.
Os resultados exploratórios continuam sujeitos às validações descritas nos
relatórios; esta organização não altera sua validade científica.

Para novos volumes, use `generated/<algoritmo>/<configuracao>/`.
As pastas `baseline_32` e `baseline_64` correspondem aos experimentos em
`configs/experiments/`, com os parâmetros da respectiva entrada em
`algorithms`. Estão vazias, reservadas para volumes futuros. A GAN tem
configurações propostas em `configs/gan` e código preparado para Colab, sem
treino nas referências; PCGRL continua em planejamento.

Dentro de cada configuração, separe execuções por `seed_<N>/` (ou por um
identificador de execução se houver repetições). Salve o volume junto de uma
cópia da configuração efetiva, incluindo parâmetros resolvidos, shape,
seed, versão/commit do código e semântica dos voxels. Mudanças nos parâmetros
exigem outra pasta de configuração; não reutilize uma baseline para variantes.
Exemplo: `generated/random_walk/baseline_32/seed_0/volume.npz`.

Os executores atuais continuam salvando em `results/volumes`, conforme os
YAML de experimento. As pastas aqui permitem organizar cópias destinadas a
processamento ou treino; a criação desta estrutura não redireciona os executores.
Artefatos permanecem ignorados pelo Git; este guia, o inventário e os
marcadores de diretório são versionáveis.

As nuvens preparadas pela datastream ficam em
`references/<fonte>/<D>x<H>x<W>/`, com superfície e interior candidato em NPZ
separados. O interior inferido por flood fill exige validação geométrica antes
de ser aceito como ar da caverna. Os comandos, metadados e o protocolo de
reprodução estão no [guia de preparação de volumes](../../docs/preparacao-volumes.md).
A pasta antiga `data/references/`, que continha apenas um marcador versionado,
foi substituída na estrutura por `data/processed/references/`.

## Recortes de referência

O menu grava propostas em `crop_plans/<caverna>/<levantamento>/<fold>/<plano>/`.
A voxelização planejada guarda resultados em
`reference_sections/<caverna>/<levantamento>/<fold>/<plano>/<recorte>/<resolucao>/`.
Os recortes manuais sem ID de plano usam
`reference_sections/<caverna>/<levantamento>/<recorte>/<resolucao>/`.
Manter todos os trechos da mesma caverna no mesmo grupo do fold.

- `surface.npz` guarda a parede observada. `masks.npz` guarda as tampas
  em `caps` e as alterações inferidas em `repair`. Execuções anteriores
  podem conter somente `caps`.
- `interior.npz` guarda a componente de ar candidata. `run.json` registra
  escala, seleção, transformação local, contagens e método, inclusive
  quantos voxels de reparo foram necessários.
- `diagnostics/` guarda `summary.csv` e `checks.csv`. Quando há
  vazamento, guarda também as tabelas de sondagens, bins, trajetórias
  e o NPZ compacto de inspeção. Tentativas rejeitadas ficam em
  `<resolucao>.diagnostics/<tentativa>/` junto da pasta esperada,
  sem publicar um interior. A opção 4 gera a inspeção em Plotly.

Essas saídas preservam os NPZ globais da auditoria em `references/`.
O significado das máscaras, o uso das tampas móveis e a revisão antes
do treino estão no [guia de preparação](../../docs/preparacao-volumes.md#quando-o-flood-fill-encontra-o-exterior).

## Planos de recortes

As receitas dos recortes, os grafos usados pelos planos e as instruções para
refazer a extração estão no [inventário de planos](crop_plans/README.md).
