# Qual clima usar como base para estimar SOC e textura do solo

Comparação de classificações climáticas CHELSA (Köppen, Holdridge, Thornthwaite) como base para estimar
carbono orgânico (SOC) e textura (areia, silte, argila) do solo em 0-30 cm, com o Köppen IPEF das
matrizes do MapBiomas Solo C3 como referência. Métrica: R² fora da amostra com validação em blocos
espaciais.

- **[comparacao_climas.ipynb](comparacao_climas.ipynb):** qual classificação climática sozinha explica melhor
  SOC e textura (método, resultados e interpretação).
- **[experimento_clima_modelos.ipynb](experimento_clima_modelos.ipynb):** o que pôr no lugar do Köppen nos
  modelos do MapBiomas Solo (clima contínuo, zonas climáticas homogêneas, estratificação).
- `codigo/`: `preparar_dados.py` (GEE), `comparar_climas.py` (métricas), `legendas.py`, testes;
  `experimento_dados.py`, `zonas_clima.py`, `experimento_modelos.py` (experimento dos modelos).
- `resultados/tabelas/`: resultados agregados. Os dados por ponto são restritos e ficam em `.local/`
  (fora do git).
- `docs/memoria_fabricio.md`: registro do que foi feito e decidido.

```bash
python -m pip install -r requirements.txt
python codigo/preparar_dados.py     # exige a conta GEE com acesso às matrizes do MapBiomas
python codigo/comparar_climas.py
python codigo/experimento_dados.py && (cd codigo && python -c "import zonas_clima as z; z.main(ks=(10, 15))")
python codigo/experimento_modelos.py   # ~75 min
python -m pytest codigo
```
