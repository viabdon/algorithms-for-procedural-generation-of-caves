
# Por que ainda não treinei a GAN?

Resumo iniciado em novembro de 2026, com o primeiro piloto de Archamps.
O código da GAN está preparado. Os exemplos globais da auditoria perderam
quase todo o ar, e os interiores locais ainda passam por revisão. Nenhum
treino nas referências foi iniciado.

## O gargalo atual

As nuvens mostram pontos nas paredes, no piso e no teto, sem indicar
diretamente onde é ar ou rocha. Entradas abertas e falhas nas paredes
dificultam separar o interior do exterior. Colocar a caverna inteira em uma
grade pequena também pode apagar passagens.

Na auditoria, as quatro referências tinham apenas **2, 1, 98 e 5 pequenos
blocos de ar**, em grades com 262.144 blocos cada. Essa representação quase
inteiramente sólida não descreve o vazio real das galerias.

## Por que treinar agora não ensinaria a criar galerias fiéis?

A GAN aprende com os exemplos recebidos. O discriminador poderia aceitar
esses volumes quase sólidos como corretos e orientar o gerador a imitá-los.
O código funcionaria, mas a rede poderia produzir quase nenhum túnel:
aprenderia os defeitos dos exemplos, sem demonstrar aprendizado das galerias.

Aumentar os blocos atuais ou convertê-los em uma malha não recupera a
informação perdida.

## O que o piloto mudou

Separar a galeria em trechos permitiu recuperar um interior reconhecível
no 004 de Archamps / PostEtroiture. O 003 parecia similar na nuvem, porém
uma rota lateral ligava a semente ao exterior. A busca com duas tampas
móveis restringiu a investigação a janelas menores. Um remendo de um
voxel, sustentado pela continuidade da parede próxima, fechou o trecho.
Esse voxel fica em uma máscara própria e o volume segue em revisão.
O [registro do piloto](plano-reconstrucao-secoes.md#evolucao-do-piloto-em-archamps)
documenta como os testes distinguiram uma fresta lateral de um problema
de tampa e o que ainda precisamos medir antes do treino.

## Próximos passos

1. **Buscar cortes com melhor cobertura.** Reavaliar primeiro os limites
   001/002 e 005/006 de PostEtroiture, em passos de quatro voxels pela linha
   central e com refinamento de um voxel. [Planejamento da busca](planejamento-recortes-voxelizacao.md#busca-de-cortes-com-melhor-cobertura)
2. **Reextrair e verificar os vizinhos.** Os dois recortes devem compartilhar
   o limite escolhido. A cobertura angular ajuda a escolher a posição, e
   o flood fill testa se o interior obtido fica isolado.
3. **Processar o restante de Archamps** após o ensaio e reunir os resumos
   das voxelizações em um CSV por caverna.
4. **Comparar resoluções e conferir os túneis com os pontos observados**,
   registrando o que foi medido e o que precisou ser estimado.
5. **Repetir a auditoria e manter os recortes separados por caverna** antes
   de iniciar um experimento de treino.

O objetivo da GAN planejada é gerar novas galerias semelhantes; reconstruir
uma nuvem específica é outra tarefa. Exemplos melhores ajudam, mas a qualidade
do treinamento ainda precisará ser testada.

O [plano detalhado](plano-reconstrucao-secoes.md) registra o procedimento e
os cuidados de validação; o [planejamento dos recortes](planejamento-recortes-voxelizacao.md)
explica a separação dos pontos e dos limites. A [auditoria](auditoria/gan/README.md) apresenta as
evidências do problema atual.
