
# Por que ainda não treinei a GAN?

Resumo de 10/11/2026 a 15/11/2026, atualizado em 17/11/2026.
O código da GAN está preparado, mas os exemplos ainda
não representam bem o interior das galerias. Nenhum treino nas referências
foi iniciado.

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

## Próximos passos

1. **Escolher um trecho curto e bem observado** e preservar a precisão dos
   pontos originais. Separar os pontos desse trecho mantendo uma faixa de
   contexto, para não cortar paredes por acidente.
2. **Reconstruí-lo por cortes sucessivos**, como fatias transversais, revisando
   o contorno interno de cada uma.
3. **Colocar tampas computacionais nas extremidades do recorte** para delimitar
   seu interior. As tampas seguem os contornos da galeria; não são as faces da
   caixa que guarda os blocos. São limites artificiais; falhas nas paredes
   ainda exigem revisão.
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
