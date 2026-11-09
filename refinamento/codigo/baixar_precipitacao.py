"""Baixa pr.npz cedido pelo autor e registra origem e hash; não redistribui."""
import argparse
import json
import zipfile
import gdown
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest

FILE_ID = '1VC9UGPHyhcyPppOMw-Wp3TEvaN3g5AsA'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retomar',action='store_true',help='Retomar arquivo parcial após encerrar o download anterior.')
    args = parser.parse_args()
    path = safe_path('dados/brutos/pr.npz')
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        if list(path.parent.glob('pr.npz*.part')) and not args.retomar:
            raise RuntimeError('Há download parcial; não iniciar em paralelo. Após encerrar o anterior, usar --retomar.')
        result = gdown.download(id=FILE_ID,output=str(path),quiet=False,use_cookies=False,
                                timeout=(30,120),retries=1,resume=args.retomar)
        if not result:
            raise RuntimeError('Download não concluído.')
    with zipfile.ZipFile(path) as archive:
        if not {'data.npy','ID.npy','lat_lon_alt.npy'}.issubset(archive.namelist()):
            raise ValueError('Arquivo NPZ sem as variáveis declaradas pelo autor.')
    manifest = {'source':f'https://drive.google.com/file/d/{FILE_ID}/view',
                'bytes':path.stat().st_size,'sha256':digest(path)}
    safe_path('dados/brutos/pr.fonte.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':
    main()
