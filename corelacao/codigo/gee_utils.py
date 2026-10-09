"""Inicializacao comum: credencial Earth Engine e, como alternativa, ADC do gcloud."""
import os

import ee
import google.auth

# Projeto do GEE para processamento e cota (o mapbiomas-brazil tem mais acesso que a conta pessoal
# fcoliveira); EE_PROJECT sobrescreve. Os assets em projects/fcoliveira/assets continuam legíveis.
PROJETO_PADRAO = os.environ.get("EE_PROJECT", "mapbiomas-brazil")


def conectar(projeto=None):
    projeto = projeto or PROJETO_PADRAO
    if not projeto:
        raise ValueError('Informe --projeto ou defina EE_PROJECT com seu projeto registrado no GEE.')
    errors = []
    for kind in ['earthengine', 'adc']:
        try:
            if kind == 'earthengine':
                ee.Initialize(project=projeto)
            else:
                credentials, _ = google.auth.default(scopes=[
                    'https://www.googleapis.com/auth/earthengine',
                    'https://www.googleapis.com/auth/cloud-platform'])
                ee.Initialize(credentials=credentials, project=projeto)
            ee.data.setDeadline(120000)
            return kind
        except Exception as exc:
            errors.append(f'{kind}: {type(exc).__name__}')
    raise RuntimeError('Nao foi possivel inicializar o GEE (' + '; '.join(errors) +
                       '). Verifique credenciais, registro do projeto e permissoes.')
