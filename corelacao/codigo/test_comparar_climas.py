"""Testes do método de comparação com dados sintéticos (resposta conhecida).

python -m pytest codigo  (ou python codigo/test_comparar_climas.py)
"""
import unittest

import numpy as np

import comparar_climas as cc


class TesteMetodo(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        self.n = 4000
        self.lon = rng.uniform(-70, -35, self.n)
        self.lat = rng.uniform(-33, 5, self.n)
        # classe "verdadeira": faixas de latitude; y depende dela + ruído
        self.verdadeira = np.digitize(self.lat, [-25, -15, -5]).astype(str)
        efeito = {'0': 0.0, '1': 1.0, '2': 2.0, '3': 3.0}
        self.y = np.array([efeito[c] for c in self.verdadeira]) + rng.normal(0, 1, self.n)
        self.ruido = rng.integers(0, 4, self.n).astype(str)          # classes sem relação com y
        self.muitas = rng.integers(0, 400, self.n).astype(str)       # 400 classes sem relação

    def test_omega2_classe_informativa_e_ruido(self):
        cod, k = cc.codificar(self.verdadeira)
        self.assertGreater(cc.omega2(self.y, cod, k), 0.5)
        cod, k = cc.codificar(self.ruido)
        self.assertAlmostEqual(cc.omega2(self.y, cod, k), 0.0, delta=0.01)

    def test_omega2_nao_premia_numero_de_classes(self):
        cod, k = cc.codificar(self.muitas)
        self.assertLess(cc.omega2(self.y, cod, k), 0.02)

    def test_r2_fora_da_amostra_penaliza_classes_sem_informacao(self):
        codigos = {'verdadeira': cc.codificar(self.verdadeira), 'ruido': cc.codificar(self.ruido),
                   'muitas': cc.codificar(self.muitas)}
        r = cc.r2_repeticoes(self.y, codigos, self.lon, self.lat, None, n_rep=5).mean()
        self.assertGreater(r['verdadeira'], 0.5)
        self.assertLess(r['ruido'], 0.01)
        # 400 classes sem informação: R² fora da amostra fica negativo (sobreajuste punido)
        self.assertLess(r['muitas'], 0.0)

    def test_blocos_espaciais_mantem_bloco_inteiro_na_mesma_dobra(self):
        grupos = cc.grupos_espaciais(self.lon, self.lat, 2.0)
        dobras = cc.sortear_dobras(grupos, 5, np.random.default_rng(1))
        for g in np.unique(grupos):
            self.assertEqual(len(np.unique(dobras[grupos == g])), 1)

    def test_classe_ausente_no_treino_recebe_media_geral(self):
        y = np.array([1.0, 1.0, 3.0, 3.0, 10.0])
        cod = np.array([0, 0, 1, 1, 2])
        dobras = np.array([0, 0, 0, 0, 1])      # a classe 2 só existe na dobra de teste 1
        pred = cc.prever_media_da_classe(y, cod, 3, dobras, 2)
        self.assertAlmostEqual(pred[4], 2.0)    # média geral do treino (1, 1, 3, 3)

    def test_mesmas_dobras_para_todos_os_preditores(self):
        codigos = {'a': cc.codificar(self.verdadeira), 'b': cc.codificar(self.verdadeira)}
        r = cc.r2_repeticoes(self.y, codigos, self.lon, self.lat, 5.0, n_rep=3)
        np.testing.assert_allclose(r['a'], r['b'])


if __name__ == '__main__':
    unittest.main()
