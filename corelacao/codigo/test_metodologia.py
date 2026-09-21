"""Testes de regressao para os erros identificados na auditoria."""
import unittest
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from preparar_dados import coordenadas_validas, decodificar_koppen
from analise_solo_clima import rotular, selecionar, ponto_bisserial, kruskal_por_nivel
from regressoes_corrigidas import grupos_espaciais, dummies_clima, ajustar


class PreparacaoTest(unittest.TestCase):
    def test_coordenadas_impossiveis(self):
        df=pd.DataFrame({'longitude':[-53.,-53000.,-53.,np.nan], 'latitude':[-29.,-29.,-29000.,-29.]})
        self.assertEqual(coordenadas_validas(df).tolist(),[True,False,False,False])

    def test_decodifica_dummy_koppen_e_rejeita_linha_invalida(self):
        # linha 0: A valido; linha 1: soma 0 (sem classe); linha 2: soma 2 (dummy invalido)
        df=pd.DataFrame({'koppen_l1_A':[1,0,1], 'koppen_l1_B':[0,0,1], 'koppen_l1_C':[0,0,0],
                         'koppen_l2_Af':[1,0,0], 'koppen_l2_Am':[0,0,0]})
        out=decodificar_koppen(df)
        self.assertEqual(out.koppen_l1.iloc[0],'A')
        self.assertTrue(pd.isna(out.koppen_l1.iloc[1]))
        self.assertTrue(pd.isna(out.koppen_l1.iloc[2]))
        self.assertEqual(out.koppen_l2.iloc[0],'Af')


class SelecaoTest(unittest.TestCase):

    def test_onehot_invalido(self):
        df=pd.DataFrame({'koppen_l1_A':[1,0,1,np.nan,.5], 'koppen_l1_B':[0,0,1,1,.5]})
        labels,_=rotular(df,'koppen_l1')
        self.assertEqual(labels.iloc[0],'A')
        self.assertTrue(labels.iloc[1:].isna().all())

    def test_ponto_bisserial_exclui_ausentes_e_raros(self):
        original=pd.DataFrame({'soc':np.arange(80,dtype=float), 'koppen_l3':['Cfa']*40+['Cfb']*40})
        extras=pd.DataFrame({'soc':[1e8]*60, 'koppen_l3':[None]*50+['Cwc']*10})
        extended=pd.concat([original,extras],ignore_index=True)
        a=ponto_bisserial(original,'soc','koppen_l3').sort_values('classe').reset_index(drop=True)
        b=ponto_bisserial(extended,'soc','koppen_l3').sort_values('classe').reset_index(drop=True)
        pd.testing.assert_frame_equal(a,b)
        self.assertTrue(b.n_total.eq(80).all())
        self.assertEqual(kruskal_por_nivel(extended,'soc','koppen_l3')['n'],80)

    def test_filtro_considera_resposta_valida(self):
        df=pd.DataFrame({'soc':[1.]*30+[np.nan], 'koppen_l1':['A']*31})
        self.assertEqual(len(selecionar(df,'soc','koppen_l1')),30)
        df.loc[0,'soc']=np.nan
        self.assertEqual(len(selecionar(df,'soc','koppen_l1')),0)


class RegressaoTest(unittest.TestCase):
    def test_referencia_dummy_remove_colinearidade(self):
        df=pd.DataFrame({'koppen_l2':['Am']*40+['Aw']*35+['Cf']*30})
        X,base=dummies_clima(df)
        self.assertEqual(base,'Am')
        self.assertEqual(X.shape[1],2)
        row,_=ajustar(pd.Series(np.arange(len(df))),X,'teste')
        self.assertEqual(row['k'],2)

    def test_bloqueia_matriz_singular(self):
        x=np.arange(50,dtype=float)
        with self.assertRaises(ValueError):
            ajustar(pd.Series(x),pd.DataFrame({'x':x,'duplicado':x}),'singular')

    def test_grupos_espaciais_sem_vazamento(self):
        df=pd.DataFrame({'longitude':[-60,-60.1,-55,-55.1,-50,-50.1,-45,-45.1,-40,-40.1],
                         'latitude':[-10]*10})
        for size in [1,2,5]:
            groups=grupos_espaciais(df,size)
            seen=[]
            for train,test in GroupKFold(5).split(df,groups=groups):
                self.assertTrue(set(groups.iloc[train]).isdisjoint(groups.iloc[test]))
                seen.extend(test)
            self.assertEqual(sorted(seen),list(range(len(df))))


if __name__=='__main__':
    unittest.main(verbosity=2)
