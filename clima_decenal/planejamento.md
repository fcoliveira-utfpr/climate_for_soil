# Planejamento: variáveis climáticas decenais (média móvel) para a predição do SOC

**Objetivo.** Gerar, a partir do Xavier (BR-DWGD), um conjunto amplo de variáveis climáticas em **média
móvel de 10 anos** e avaliar quais mais afetam a predição do SOC do MapBiomas Solo C3, em especial no tempo.
Continua o relatório v3 (`climas_tempo/`): lá, classificar o clima por década não ajudou no tempo; o que
ajudou foi o clima **contínuo** decenal (temperatura, chuva e CDD, relatório v2). Aqui o contínuo decenal é
ampliado com energia, umidade e balanço hídrico.

**Decisões do usuário (13/10/2026)**
- Pasta própria: `clima_decenal/`.
- **ETo calculada a partir do saldo de radiação (Rn), com a `agrometeorologiapy`**, e não a ETo pronta do
  Xavier.
- Balanço hídrico climatológico da biblioteca e novas variáveis a partir dele.

**Janela.** Como no GT de clima do MapBiomas e no contínuo decenal do v2: o ano Y recebe a normal mensal de
Y−10 a Y−1 (média móvel), para Y = 1985 a 2024. No GEE, temperatura, umidade, radiação e vento do Xavier vão
até 07/2020 e a chuva até 2022: as janelas de 2021 a 2024 usam os anos disponíveis (registrado por variável).

**ETo de Penman-Monteith FAO-56, mensal** (Allen et al. 1998), com as funções da biblioteca:
- Qo (Ra): `nda`, `declinacao_solar`, `angulo_horario_nascer`, `fator_correcao_distancia`,
  `irradiancia_extraterrestre`, no dia 15 de cada mês;
- Qg_cs (Rso) = (0,75 + 2·10⁻⁵·z) Qo (FAO-56, eq. 37), com z = altitude média do pixel (MERIT);
- BOC = `boc_saldo(Qg, r=0.23)` (albedo da grama de referência; o padrão da função é 0,25);
- BOL = `bol_saldo(Tmax, Tmin, ea, Qg, Qg_cs)` com Qg/Qg_cs limitado a 1 (FAO-56, eq. 39; a função não limita);
- Rn = `saldo_radiacao(BOC, BOL)`; G mensal = 0,14 (T_mês − T_mês anterior) (FAO-56, eq. 44);
- es = média de `es_tetens(Tmax)` e `es_tetens(Tmin)`; ea = es · UR/100 (eq. 19); Δ = `declive_pressao_vapor(Tmed)`;
  γ = `constante_psicrometrica(patm_altitude(z))`;
- ETo = `eto_penman_monteith_fao56(Rn, G, Tmed, u2, es, ea, Δ, γ)` × dias do mês.
Conferência: ETo calculada × ETo do Xavier (também FAO-56, diária).

**Variáveis** (cada uma na média móvel de 10 anos): temperatura (média, máxima, mínima, mês mais quente e mais
frio, amplitude diária, biotemperatura), chuva (anual, mês mais seco e mais chuvoso, sazonalidade, meses
secos), energia e umidade (Rs, Rn, ETo, UR, DPV, vento), razões (ETo/P, P − ETo) e o **balanço hídrico
climatológico** (CAD 100 mm e CAD do solo: DEF, EXC, ETR, ETR/ETo, Ih, Ia, Im, meses com deficiência,
armazenamento médio) e o CDD decenal já calculado (`Climas2/CDD_DECENAL_BRDWGD`).

**Etapas**
1. `baixar_xavier.py`: Tmax, Tmin, UR, Rs e vento médios mensais de cada ano (1961-2022) e a altitude.
2. `eto_rn.py`: ETo de Penman-Monteith mensal a partir do Rn; conferência com a ETo do Xavier.
3. `variaveis.py`: médias móveis por ano (1985-2024), balanço hídrico e o conjunto de variáveis.
4. Valores nos pontos de SOC e avaliação (importância, seleção e validação V2/V3/V4).

Dados por pixel em `clima_decenal/dados/` (fora do git).
