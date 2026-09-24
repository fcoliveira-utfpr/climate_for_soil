# Qual clima usar como base para estimar SOC e textura do solo

Comparação de classificações climáticas CHELSA (Köppen, Holdridge, Thornthwaite) como base para estimar
carbono orgânico (SOC) e textura (areia, silte, argila) do solo em 0-30 cm, com o Köppen IPEF das
matrizes do MapBiomas Solo C3 como referência. Métrica: R² fora da amostra com validação em blocos
espaciais.

- **[comparacao_climas.ipynb](comparacao_climas.ipynb):** método, resultados e interpretação.
- `codigo/`: `preparar_dados.py` (GEE), `comparar_climas.py` (métricas), `legendas.py`, testes.
- `resultados/tabelas/`: resultados agregados. Os dados por ponto são restritos e ficam em `.local/`
  (fora do git).
- `docs/memoria_fabricio.md`: registro do que foi feito e decidido.

```bash
python -m pip install -r requirements.txt
python codigo/preparar_dados.py     # exige a conta GEE com acesso às matrizes do MapBiomas
python codigo/comparar_climas.py
python -m pytest codigo
```
