# Origem das nuvens de cavernas

O arquivo [origem_nuvens.csv](origem_nuvens.csv) registra a identificação inicial
das nuvens ativas no HD externo, consultadas em 07/11/2026. É um inventário de
origem, não uma aprovação de volumes para treinamento.

Foram identificadas **15 nuvens de cinco cavernas**. As contagens são de arquivos,
não de fontes independentes:

| Grupo de independência | Caverna | Nuvens | Fonte |
| --- | --- | ---: | --- |
| `archamps` | Grotte d'Archamps | 4 | KarstConduitCatalogue; PreEtroiture e PostEtroiture em 2 mm e 5 cm |
| `cascadedemotiers` | Grotte de la Cascade de Môtiers | 2 | KarstConduitCatalogue; MainGallery em 2 mm e 5 cm |
| `markovspodmol` | Markov Spodmol | 2 | KarstConduitCatalogue; MainGallery em 2 mm e 5 cm |
| `indian_tunnel` | Indian Tunnel | 6 | NASA/CMU; versões Full, trechos, parede e superfície externa |
| `elaphes` | Creux des Élaphes | 1 | Fonte identificada no servidor LIRIS/CNRS |

Não se deve dividir automaticamente versões ou trechos de uma mesma caverna
entre treino e teste como se fossem fontes independentes. As partições continuam
sem definição nesta etapa. Os dados de superfície externa e de fragmento de
parede do Indian Tunnel são identificados nas observações; não pressupõem
cobertura do vazio da caverna inteira.

## Método de levantamento

A raiz local é `/run/media/midnavi/Pablo/TCC/DATA/RAW`. O caminho de cada nuvem
é `raiz_local` combinado com `arquivo_relativo`; isso permite alterar o ponto
de montagem sem perder a identificação relativa.

Foram lidos nomes/tamanhos de arquivos, cabeçalhos PLY/LAS e os pequenos arquivos
YAML/README dos pacotes. As coordenadas das nuvens não foram percorridas e não
foram calculados hashes integrais para evitar competir com a voxelização em
andamento. As contagens LAS/PLY são declaradas nos cabeçalhos; as F32 são
inferidas do tamanho dividido por 28 bytes, conforme o formato publicado pela
NASA. Essas verificações não comprovam a integridade do conteúdo completo.

O `metadata.yaml` presente na raiz RAW descreve apenas CascadeDeMotiers, não
todas as pastas ali reunidas. Para Archamps e Markov Spodmol, os descritores
individuais ainda estavam em pequenas embalagens de download descartadas,
`swissubase_3065_1_0` e `swissubase_3070_1_0`, na lixeira do HD. Somente esses
YAML foram consultados; suas localizações ficam registradas como evidência e
podem desaparecer quando a lixeira for esvaziada. As nuvens inventariadas estão
na raiz ativa, fora da lixeira. Os DOI individuais identificados são:

- Archamps, versão 1.0: <https://doi.org/10.60544/gxkd-1r73>.
- CascadeDeMotiers, versão 1.0: <https://doi.org/10.60544/7e8y-yh95>.
- MarkovSpodmol, versão 1.0: <https://doi.org/10.60544/8jsy-w511>.

A identificação usa os nomes e descritores locais, combinados com a declaração
do usuário sobre a origem. A correspondência byte a byte com os downloads não
foi verificada. A data de download é desconhecida e não foi inferida das datas
de modificação dos arquivos. Os caminhos de nuvens no `configs/datasets.yaml`
são históricos e não substituem os caminhos observados neste CSV.

## Fontes e pontos a esclarecer

**KarstConduitCatalogue.** O catálogo geral é identificado pelo DOI
<https://doi.org/10.60544/sbjr-z851>. O artigo de descrição está em
<https://doi.org/10.5194/essd-17-4671-2025>. Os `cave.yaml` e `scan.yaml`
fornecem nomes, país, data de aquisição e CRS dos trechos. As diferentes
resoluções são derivadas do mesmo levantamento e não novas cavernas.

Há uma divergência documental de licença: `documents/README.md` declara
Creative Commons Attribution Non Commercial 4.0, enquanto `metadata.yaml`
individuais declaram Creative Commons Attribution-ShareAlike 4.0. O
`cave.yaml` de Markov Spodmol também indica BY-SA. A
[página de licença de CascadeDeMotiers](https://www.swissubase.ch/fr/catalogue/studies/21005/latest/datasets/3078/3951/contract/usage-license)
indica BY-SA 4.0. O CSV preserva ambas as declarações e deixa a divergência
pendente; não usa a licença do artigo como substituta da licença dos dados.

**Indian Tunnel.** A fonte é a
[página NASA Planetary Pits and Caves Analog Dataset](https://ti.arc.nasa.gov/dataset/caves/),
originalmente hospedada pela Carnegie Mellon University e depois transferida
à NASA. A página informa coordenadas em metros e aquisição em agosto de 2014.
Sua seção Attribution limita o uso a pesquisa/acadêmico e exige consentimento
escrito dos autores para uso comercial ou incorporação em uma base destinada
à distribuição pública. O CSV registra esses termos próprios, sem presumir
domínio público por estar hospedado na NASA. O
[documento suplementar](https://ti.arc.nasa.gov/dataset/caves/data/COTM_Supplemental_Info.pdf)
ajuda a distinguir levantamento externo e fragmentos de parede. Ele cita
coordenadas UTM de estações externas, o que não confirma automaticamente o CRS
de todos os arquivos F32 locais.

**Elaphes.** A fonte identificada é a
[página Elaphes cave do LIRIS/CNRS](https://dataset-dl.liris.cnrs.fr/elaphes-cave/).
Ela atribui a aquisição a EDYTEM/USMB/CNRS e declara licença Etalab 2.0. O
cabeçalho do PLY local indica 94.465.067 pontos, compatível com a versão original
publicada; a versão sanitizada descrita na fonte tem 94.465.064. Essa coincidência
não comprova identidade binária nem o histórico de conversão/renomeação para
`elaphes_cave.ply`. Unidade, CRS, data de aquisição e data de download permanecem
sem confirmação.

## Leitura e atualização do CSV

O CSV usa UTF-8, vírgula como delimitador, campos entre aspas e uma única linha
de cabeçalho. LibreOffice/Excel podem pedir seleção explícita do delimitador.
Datas conhecidas seguem ISO: `YYYY-MM-DD`, ou `YYYY-MM` para o Indian Tunnel,
cuja fonte informa apenas mês/ano. Campos vazios significam informação não
confirmada ou não aplicável; não representam zero.

- `id_arquivo` identifica uma nuvem; `id_caverna` e `grupo_independencia`
  relacionam versões e trechos da mesma caverna.
- `doi_dataset`, `versao_dataset`, `fonte_url` e `credito` descrevem a origem.
- `data_aquisicao`, `unidade_coordenadas` e `crs` distinguem a aquisição dos
  parâmetros posteriores de voxelização. A unidade dos voxels normalizados
  não substitui a unidade física da nuvem.
- `tamanho_bytes` e `quantidade_pontos` são inteiros; o método de contagem
  explica a evidência usada. As variantes 2 mm/5 cm vêm dos nomes e da
  documentação do dataset, sem nova medição de espaçamento.
- `licenca_declarada`, `evidencia_licenca` e `status_licenca` preservam termos e
  divergências. `status_identificacao` distingue origem conhecida e identidade
  exata do arquivo ainda não comprovada.
- `sha256` está vazio e `status_sha256` está pendente. Calcular depois, evitando
  concorrência de leitura no HD durante a voxelização.
- `particao` está sem definição e `aprovacao_gan` está pendente de validação
  geométrica. Nenhuma nuvem recebeu aprovação automática para treino.

Depois da voxelização, vincule cada resultado ao `id_arquivo` de origem e ao
seu registro `.run.json`, preservando o grupo da caverna. A inspeção do interior,
a resolução e as métricas serão uma etapa posterior; não foram presumidas a
partir do nome ou do tamanho dos arquivos.
