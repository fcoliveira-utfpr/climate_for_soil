# Etapa 6b: validação dos cenários de clima com o ranger da produção (300 árvores, mtry 24,
# min.node.size 2, max.depth 40), resposta carbono_gm2_qmap direta ou em log.
#
# Esquemas (dobras de cenarios.py; perfil e réplicas sempre juntos):
#   v2  espacial: blocos de 2°, 5 dobras x 3 repetições
#   v3  temporal: deixa um período de 10 anos de fora (4 dobras)
#   v4  espaço-temporal: teste = dobra espacial f (rep. 1) e período p; treino = fora dos dois (20 modelos)
# Resposta 'log': log(qmap + 1) e volta com a correção de Duan (smearing) dos resíduos OOB do treino.
#
# Saída: climas/dados_espaco_tempo/oof/<cenario>_<esquema>_<resposta>.parquet (id, rep, dobra, pred em
# g/m²). Combinações já gravadas são puladas (dá para retomar).
#
# Uso: Rscript validacao.R <cenarios separados por vírgula | todos> <esquemas: v2,v3,v4> <direta|log>

.libPaths(c(Sys.getenv("R_LIBS_USER"), .libPaths()))
suppressPackageStartupMessages({
  library(data.table)
  library(ranger)
  library(arrow)
  library(jsonlite)
})

args_all <- commandArgs(trailingOnly = FALSE)
script_dir <- dirname(normalizePath(sub("^--file=", "", args_all[grep("^--file=", args_all)])))
args <- commandArgs(trailingOnly = TRUE)
dados_dir <- normalizePath(file.path(script_dir, "..", "..", "dados_espaco_tempo"))
oof_dir <- file.path(dados_dir, "oof")
dir.create(oof_dir, showWarnings = FALSE)

cfg <- fromJSON(file.path(script_dir, "cenarios.json"))
cen_nomes <- if (args[1] == "todos") names(cfg$cenarios) else strsplit(args[1], ",")[[1]]
esquemas <- strsplit(args[2], ",")[[1]]
resposta <- args[3]
stopifnot(resposta %in% c("direta", "log"), all(cen_nomes %in% names(cfg$cenarios)))

m <- as.data.table(read_parquet(file.path(dados_dir, "matriz_cenarios.parquet")))
y_g <- m$carbono_gm2_qmap
nthreads <- max(1L, parallel::detectCores() - 1L)

ajustar_prever <- function(X, treino, teste, semente) {
  y <- if (resposta == "log") log(y_g[treino] + 1) else y_g[treino]
  fit <- ranger(x = X[treino], y = y, num.trees = 300L, mtry = min(24L, ncol(X)),
                min.node.size = 2L, max.depth = 40L, num.threads = nthreads, seed = semente)
  p <- predict(fit, X[teste], num.threads = nthreads)$predictions
  if (resposta == "log") {
    smear <- mean(exp(y - fit$predictions), na.rm = TRUE)    # Duan, com os resíduos OOB
    p <- exp(p) * smear - 1
  }
  p
}

particoes <- function(esquema) {   # lista de (rep, dobra, treino, teste)
  out <- list()
  if (esquema == "v2") {
    for (r in 1:3) {
      f_col <- m[[paste0("fold_v2_", r)]]
      for (f in 1:5) out[[length(out) + 1]] <- list(rep = r, dobra = f, treino = f_col != f, teste = f_col == f)
    }
  } else if (esquema == "v3") {
    for (p in 1:4) out[[length(out) + 1]] <- list(rep = 1, dobra = p, treino = m$periodo != p, teste = m$periodo == p)
  } else if (esquema == "v4") {
    for (f in 1:5) for (p in 1:4) {
      out[[length(out) + 1]] <- list(rep = 1, dobra = (f - 1) * 4 + p,
                                     treino = m$fold_v2_1 != f & m$periodo != p,
                                     teste = m$fold_v2_1 == f & m$periodo == p)
    }
  } else stop("esquema desconhecido: ", esquema)
  out
}

for (cen in cen_nomes) {
  cols <- c(cfg$base, unlist(cfg$cenarios[[cen]]))
  X <- m[, ..cols]
  for (esq in esquemas) {
    arq <- file.path(oof_dir, sprintf("%s_%s_%s.parquet", cen, esq, resposta))
    if (file.exists(arq)) { cat("já existe:", basename(arq), "\n"); next }
    t0 <- Sys.time()
    res <- rbindlist(lapply(particoes(esq), function(pt) {
      te <- which(pt$teste)
      data.table(linha = te, id = m$id[te], rep = pt$rep, dobra = pt$dobra,
                 pred = ajustar_prever(X, which(pt$treino), te, 1984L + pt$rep * 100L + pt$dobra))
    }))
    write_parquet(res, arq)
    cat(sprintf("%s %s %s: %d colunas, %d predições, %s\n", cen, esq, resposta, ncol(X), nrow(res),
                format(Sys.time() - t0, digits = 3)))
  }
}
