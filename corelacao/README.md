# Textura e carbono do solo × clima

Trabalho com dados do MapBiomas Solo C3 beta: associação de areia, silte, argila e carbono orgânico
do solo com Köppen e Holdridge, na camada de **0-30 cm**.

Duas matrizes de treino do Earth Engine (acesso restrito, liberado para a conta usada aqui — ver
`docs/assets.md`): uma de carbono, outra de textura medida em laboratório. Köppen já vem pronto, em
dummy, nas duas matrizes; Holdridge é extraído à parte, com legenda confirmada.

## Comece por aqui

1. **[Notebook executado](solo_clima_consolidado.ipynb)**: leitura principal, com texto, figuras e exploração
   das tabelas. A execução padrão usa só os arquivos do repositório, sem login no Earth Engine.
2. **[Tabelas, figuras e fontes](resultados/README.md)**: resultados completos, com precisão numérica integral.
3. **[Assets em uso](docs/assets.md)**: fontes de dados e do Earth Engine, com o que cada uma fornece.
4. **[Orientações originais](docs/orientacoes_solo_clima.md)** e **[reprodução da análise](docs/reproducao.md)**.

## O que foi feito

- Textura: filtro em 0-30 cm, exclusão de amostras artificiais, mediana por local, com areia + silte +
  argila = 100% (±1 ponto percentual). SOC: estoque acumulado até 30 cm, sem a variável qmap (não existe
  nesta fonte).
- Remoção de pseudoamostras, coordenadas impossíveis e repetições indevidas.
- Mesma extração climática para as duas etapas; descritivas, Kruskal-Wallis, ANOVA/Welch,
  Dunn-Holm, ponto-bisserial, Spearman e gráficos. Filtro n ≥ 30 por grupo nos testes.
- Regressões de log(SOC), random forest e logística; cinco dobras aleatórias e blocos espaciais de 1°, 2° e 5°.

| Conjunto final | Locais |
| --- | ---: |
| Textura | 12.062 |
| SOC | 12.286 |
| Mesmo local com SOC e textura | 9.792 |

Há associação entre solo e clima nos pontos analisados, mas a inferência é exploratória.
Adicionar clima à textura aumenta o R² do ajuste; isso **não demonstra mediação causal**.
A vantagem preditiva do random forest depende da separação espacial usada na validação.

A legenda de Holdridge (HLZ_L1/L2) vem do asset `holdridge_lifezones_chelsa-v2026`, que documenta a
tabela ID → zona/subzona na própria descrição (CHELSA V2.1). Na amostra usada, só 2 das 7 zonas
térmicas aparecem de fato (Tropical e Subtropical) — coerente com o clima do Brasil. A matriz
`c03_soc_v2025_trainingFinal`, indicada nas orientações originais, continua bloqueada mesmo com o
acesso liberado às demais matrizes desta conta — não é apresentada aqui como equivalência certificada.

## Estrutura da entrega

```text
README.md                       guia de leitura
solo_clima_consolidado.ipynb     caderno executado, documento principal
requirements.txt                dependências
codigo/                         código científico, exportação e testes
docs/                           orientações, assets em uso e reprodução
resultados/
  tabelas/                      14 CSVs consolidados; nenhuma comparação omitida
  figuras/                      13 figuras principais + 5 painéis complementares
  fontes/                       proveniência, amostras, legenda e verificação
```

Somente esse material e as configurações do Git compõem a entrega. `.local/` é ignorada: contém
dados/cache e resultados intermediários. Ela não deve ser enviada ao professor.

## Reproduzir e conferir

```powershell
python -m pip install -r requirements.txt
python codigo/verificar_resultados.py
```

Roda os testes unitários e recalcula cada número publicado a partir dos dados, comparando com os CSVs
entregues. Para recalcular a partir das fontes (exige conta com acesso liberado ao Earth Engine),
siga [docs/reproducao.md](docs/reproducao.md). O notebook é a entrega editorial desta execução; o
pipeline científico recalcula tabelas e figuras sem reexecutá-lo — isso precisa ser feito manualmente
depois de qualquer recálculo.

**A reprodução exige acesso liberado** às duas matrizes de treino do Earth Engine usadas (ver
[docs/assets.md](docs/assets.md)) — não é acesso público. Sem essa conta, os resultados já calculados
ficam preservados em `resultados/`.

Assets e proveniência em `resultados/fontes/proveniencia.json`; lista completa em [docs/assets.md](docs/assets.md).
Referências metodológicas e checklist no notebook, seção final.
