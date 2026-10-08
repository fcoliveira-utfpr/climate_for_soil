# Etapa 7c: modelo final de cada cenário (matriz inteira, ranger da produção, resposta direta) e predição
# do painel local × ano 1985-2024 (profundidade 30 cm, índices 0, como no mapa da produção).
#
# Saídas (restritas): climas/dados_espaco_tempo/painel_predicoes.parquet (ponto_id, year, uma coluna por
# cenário em t/ha) e resultados/tabelas/importancia_cenarios.csv (importância por impureza, versionada).
#
# Uso: Rscript prever_painel.R

.libPaths(c(Sys.getenv("R_LIBS_USER"), .libPaths()))
suppressPackageStartupMessages({
  library(data.table)
  library(ranger)
  library(arrow)
  library(jsonlite)
})

args_all <- commandArgs(trailingOnly = FALSE)
script_dir <- dirname(normalizePath(sub("^--file=", "", args_all[grep("^--file=", args_all)])))
dados_dir <- normalizePath(file.path(script_dir, "..", "..", "dados_espaco_tempo"))
tab_dir <- file.path(script_dir, "..", "resultados", "tabelas")

cfg <- fromJSON(file.path(script_dir, "cenarios.json"))
m <- as.data.table(read_parquet(file.path(dados_dir, "matriz_cenarios.parquet")))
painel <- as.data.table(read_parquet(file.path(dados_dir, "painel_cenarios.parquet")))
nthreads <- max(1L, parallel::detectCores() - 1L)
source(file.path(script_dir, "selecao_continuas.R"))

pred <- painel[, .(ponto_id, year)]
imp <- list()
for (cen in names(cfg$cenarios)) {
  clima <- unlist(cfg$cenarios[[cen]])
  if (cen == "cont_sel") {          # seleção (pares |r| > 0,9) com a matriz inteira
    clima <- selecionar_continuas(m, m$carbono_gm2_qmap, seq_len(nrow(m)), cfg, nthreads, 1984L)
    writeLines(clima, file.path(tab_dir, "selecao_continuas_final.txt"))
  }
  cols <- c(cfg$base, clima)
  t0 <- Sys.time()
  fit <- ranger(x = m[, ..cols], y = m$carbono_gm2_qmap, num.trees = 300L, mtry = 24L, min.node.size = 2L,
                max.depth = 40L, importance = "impurity", num.threads = nthreads, seed = 1984L)
  pred[[cen]] <- predict(fit, painel[, ..cols], num.threads = nthreads)$predictions / 100   # t/ha
  vi <- fit$variable.importance
  imp[[cen]] <- data.table(cenario = cen, covariavel = names(vi), importancia = vi / sum(vi),
                           posicao = rank(-vi, ties.method = "first"), clima = names(vi) %in% clima)
  cat(sprintf("%s: OOB R² %.4f, %s\n", cen, fit$r.squared, format(Sys.time() - t0, digits = 3)))
}
write_parquet(pred, file.path(dados_dir, "painel_predicoes.parquet"))
fwrite(rbindlist(imp), file.path(tab_dir, "importancia_cenarios.csv"))
