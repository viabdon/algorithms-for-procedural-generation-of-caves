# Dados processados

```text
data/processed/
├── experiments/
│   └── experiment_elaphes-meshing/   # ensaios históricos do Elaphes
├── references/                      # superfícies e interiores candidatos de scans
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

## Recortes de referência planejados

A organização proposta para o piloto é
`reference_sections/<caverna>/<levantamento>/<recorte>/<resolucao>/`, separada
dos volumes globais. Cada recorte registrará seleção de pontos, contexto,
seções inicial/final, tampas, bounds da grade, transformação local e tamanho
físico do voxel, além de máscaras de incerteza.

A caixa de seleção não representa uma parede, e as tampas não coincidem
obrigatoriamente com a borda da grade. O
[planejamento dos recortes](../../docs/planejamento-recortes-voxelizacao.md)
define essas diferenças e os campos do manifesto. São saídas futuras, ainda
não produzidas pelo menu. Manter recortes da mesma caverna na mesma partição
e não sobrescrever os NPZ da auditoria atual.
