import numpy as np
import pandas as pd
import pytest
import rasterio
from affine import Affine
from codigo import modelos
from codigo.mapa_brasil import predict_window, create_outputs, output_paths


class Constant:
    def __init__(self, value):
        self.value = value
        self.frames = []

    def predict(self, frame):
        self.frames.append(frame.copy())
        return np.full(len(frame), self.value)


def development():
    names = [x for x in modelos.FEATURES if x != 'elevation_m'] + ['dem_elevation_m','slope_deg','chelsa_c']
    return pd.DataFrame({name: [-10000., 10000.] for name in names})


def test_mask_offset_annual_dispersion_and_northern_projection():
    data = np.full((15, 2, 2), 20.)
    data[12:14] = 500
    data[14] = 2
    data[0, 0, 1] = np.nan
    inside = np.array([[True, True],[True,False]])
    model = Constant(1)
    arrays, country, valid = predict_window(data, Affine(30,0,499980,0,-30,30000), 'EPSG:32622',
        inside, model, [Constant(0),Constant(2)], development())
    assert (country, valid) == (3,2)
    assert (arrays['temperatura_media'][:,0,0] == 2100).all()
    assert (arrays['temperatura_media'][:,0,1] == -32768).all()
    assert (arrays['fora_faixa_treino'][:,1,1] == 255).all()
    assert arrays['dispersao_modelos'][:,0,0] == pytest.approx(np.sqrt(2))
    assert model.frames[0].latitude.gt(0).all()
    assert model.frames[0].longitude.between(-52,-50).all()


def test_all_missing_never_calls_model():
    model = Constant(0)
    arrays, country, valid = predict_window(np.full((15,2,2),np.nan), Affine(30,0,0,0,-30,60),
        'EPSG:32722', np.ones((2,2),bool), model, [model,model], development())
    assert country == 4 and valid == 0 and not model.frames
    assert np.all(arrays['temperatura_media'] == -32768)


def test_unwritten_windows_are_nodata_and_resume_rejects_foreign_files(tmp_path):
    tile = dict(tile_id='sample',width=32,height=32,crs='EPSG:32722',transform=[30,0,0,0,-30,960])
    paths = output_paths(tmp_path,'sample')
    create_outputs(paths,tile,'signature')
    with rasterio.open(paths['temperatura_media'][0]) as source:
        assert source.read(1,masked=True).mask.all()
        assert source.scales == (.01,)
    create_outputs(paths,tile,'signature')
    with pytest.raises(ValueError):
        create_outputs(paths,tile,'different')
