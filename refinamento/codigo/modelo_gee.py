"""Leva os modelos congelados para dentro do GEE, para calcular o Brasil inteiro sem processamento local.

Cada LightGBM (temperatura: modelo principal + 5 membros; chuva: 12 meses × (principal + 5 membros)) é convertido
para o formato de árvores de `ee.Classifier.decisionTreeEnsemble` e salvo como asset de classificador
(`Export.classifier.toAsset`). O GEE, em modo REGRESSION, tira a média das árvores; por isso cada folha é
multiplicada pelo número de árvores, e a média vira a soma que o LightGBM usa. O script do GEE
`gee/brasil_30m.js` carrega esses assets e monta as imagens com as mesmas covariáveis do Paraná.

Subcomandos (de dentro de refinamento/):
  python -B -m codigo.modelo_gee exportar --project ID     # cria os 78 assets de classificador
  python -B -m codigo.modelo_gee conferir --project ID     # compara GEE × Python em pontos sorteados
"""
import argparse
import json
import time

import joblib
import numpy as np
import pandas as pd

from codigo.dados_temperatura import safe_path

PREP = "dados/parana/preparo.joblib"
FOLDER = "refinamento_30m/modelos"


def tree_strings(booster, features):
    dump = booster.dump_model()
    trees = dump["tree_info"]
    n = len(trees)

    def walk(node, idx, depth, cond, lines):
        pad = "  " * depth
        if "leaf_value" in node:
            lines.append(f"{pad}{idx}) {cond} 1 1 {node['leaf_value'] * n:.12g} *")
            return
        lines.append(f"{pad}{idx}) {cond} 1 1 0")
        name, threshold = features[node["split_feature"]], node["threshold"]
        walk(node["left_child"], 2 * idx, depth + 1, f"{name}<={threshold:.12g}", lines)
        walk(node["right_child"], 2 * idx + 1, depth + 1, f"{name}>{threshold:.12g}", lines)

    out = []
    for tree in trees:
        root = tree["tree_structure"]
        if "leaf_value" in root:
            out.append(f"1) root 1 1 {root['leaf_value'] * n:.12g} *")
            continue
        lines = ["1) root 1 1 0"]
        name, threshold = features[root["split_feature"]], root["threshold"]
        walk(root["left_child"], 2, 1, f"{name}<={threshold:.12g}", lines)
        walk(root["right_child"], 3, 1, f"{name}>{threshold:.12g}", lines)
        out.append("\n".join(lines))
    return out


def models(prep):
    """(nome, booster, features, smearing) de todos os modelos, na ordem do script."""
    t = prep["temperatura"]
    out = [("temp_principal", t["model"].booster_, t["features"], None)]
    out += [(f"temp_membro{i}", m.booster_, t["features"], None) for i, m in enumerate(t["members"])]
    for month in range(1, 13):
        unit = prep["chuva"]["months"][month]
        feats = prep["chuva"]["features"]
        out.append((f"chuva_{month:02d}_principal", unit["model"].estimator_.booster_, feats, unit["model"].smearing_))
        out += [(f"chuva_{month:02d}_membro{i}", m.estimator_.booster_, feats, m.smearing_)
                for i, m in enumerate(unit["members"])]
    return out


def constants(prep, project):
    t, c = prep["temperatura"], prep["chuva"]
    smearing = {}
    for month in range(1, 13):
        unit = c["months"][month]
        smearing[f"{month:02d}"] = [unit["model"].smearing_] + [m.smearing_ for m in unit["members"]]
    return {"pasta": f"projects/{project}/assets/{FOLDER}", "temp_features": t["features"],
            "chuva_features": c["features"], "temp_k90": t["k90_monthly"], "temp_q90_anual": t["q90_annual"],
            "chuva_k90": c["k90_monthly"], "chuva_q90_anual": c["q90_annual"], "chuva_smearing": smearing,
            "pesos_mes": [float(w) for w in __import__("codigo.mapa_piloto", fromlist=["x"]).month_weights()]}


def tabela(nome):
    return "arvores_temp" if nome.startswith("temp") else "arvores_chuva_" + nome.split("_")[1]


def exportar(args):
    """Grava as árvores de cada modelo como tabela no GEE (o classificador é montado no script a partir delas).

    Classificadores exportados com Export.classifier.toAsset voltam vazios ao carregar
    ("Classifier has no training data"); a tabela de árvores é lida com aggregate_array no script.
    """
    import ee
    ee.Initialize(project=args.project)
    prep = joblib.load(safe_path(PREP))
    root = f"projects/{args.project}/assets/{FOLDER}"
    try:
        ee.data.getAsset(root)
    except ee.EEException:
        ee.data.createAsset({"type": "FOLDER"}, root)
    for item in ee.data.listAssets({"parent": root}).get("assets", []):
        if item["type"] == "CLASSIFIER":
            ee.data.deleteAsset(item["name"])
    grupos = {}
    for name, booster, feats, _ in models(prep):
        grupos.setdefault(tabela(name), []).extend(
            ee.Feature(ee.Geometry.Point([0, 0]), {"modelo": name, "arvore": t}) for t in tree_strings(booster, feats))
    tasks = []
    for nome, features in grupos.items():
        task = ee.batch.Export.table.toAsset(collection=ee.FeatureCollection(features), description=nome,
                                             assetId=f"{root}/{nome}")
        task.start()
        tasks.append(task)
    print(f"{len(tasks)} tabelas em exportação", flush=True)
    gerar_script(prep, args.project)


def gerar_script(prep, project):
    """Escreve gee/brasil_30m.js a partir do modelo do script, com as constantes do preparo."""
    template = safe_path("gee/brasil_30m_modelo.js").read_text(encoding="utf-8")
    text = template.replace("__CONSTANTES__", json.dumps(constants(prep, project), indent=2))
    safe_path("gee/brasil_30m.js").write_text(text, encoding="utf-8")


def conferir(args):
    """Compara no GEE e em Python, nos mesmos valores de covariáveis, todos os modelos."""
    import ee
    ee.Initialize(project=args.project)
    prep = joblib.load(safe_path(PREP))
    root = f"projects/{args.project}/assets/{FOLDER}"
    rng = np.random.default_rng(5)
    worst = 0.0
    for name, booster, feats, _ in models(prep):
        pts = pd.DataFrame({f: rng.uniform(*{"latitude": (-33, 5), "longitude": (-73, -35), "chelsa_c": (8, 29),
                                             "dem_elevation_m": (0, 2000), "slope_deg": (0, 30), "elevation_30": (0, 2000),
                                             "slope_30": (0, 30), "chelsa_mm": (np.log1p(5), np.log1p(500))}.get(f, (-1, 1)), 25)
                            for f in feats})
        if "latitude_sin" in feats:
            pts["latitude_sin"], pts["latitude_cos"] = pts.latitude * pts.month_sin, pts.latitude * pts.month_cos
        fc = ee.FeatureCollection([ee.Feature(None, {k: float(v) for k, v in r.items()}) for r in pts.to_dict("records")])
        arvores = ee.FeatureCollection(f"{root}/{tabela(name)}").filter(ee.Filter.eq("modelo", name)).aggregate_array("arvore")
        clf = ee.Classifier.decisionTreeEnsemble(arvores).setOutputMode("REGRESSION")
        gee = np.array(fc.classify(clf, "p").aggregate_array("p").getInfo())
        diff = float(np.abs(gee - booster.predict(pts[feats])).max())
        worst = max(worst, diff)
    print(f"{len(models(prep))} modelos conferidos; maior diferença GEE − Python: {worst:.2e}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("exportar", "conferir", "script"):
        sub.add_parser(name).add_argument("--project", required=True)
    args = parser.parse_args()
    {"exportar": exportar, "conferir": conferir,
     "script": lambda a: gerar_script(joblib.load(safe_path(PREP)), a.project)}[args.command](args)


if __name__ == "__main__":
    main()
