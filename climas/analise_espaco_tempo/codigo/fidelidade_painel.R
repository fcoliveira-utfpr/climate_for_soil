# Etapa 7e: por que a trajetória do cenário Köppen difere do SOC oficial da C3? Testa variantes do modelo
# final no painel (só o Köppen, as covariáveis da produção):
#   qmap_300   carbono_gm2_qmap, 300 árvores (o modelo da validação, R 30; é o de prever_painel.R)
#   gm2_400    carbono_gm2, 400 árvores, semente 2021 (o modelo final do R 28 e do script do GEE)
# Saída (restrita): climas/dados_espaco_tempo/painel_fidelidade.parquet (ponto_id, year, uma coluna por
# variante, t/ha).
#
# Uso: Rscript fidelidade_painel.R

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
cfg <- fromJSON(file.path(script_dir, "cenarios.json"))
cols <- c(cfg$base, unlist(cfg$cenarios$koppen_ipef))

m <- as.data.table(read_parquet(file.path(dados_dir, "matriz_cenarios.parquet")))
gm2 <- as.data.table(read_parquet(file.path(dados_dir, "matriz_soc_c3_fabricio.parquet"), col_select = "carbono_gm2"))
stopifnot(nrow(gm2) == nrow(m))
painel <- as.data.table(read_parquet(file.path(dados_dir, "painel_cenarios.parquet")))
nthreads <- max(1L, parallel::detectCores() - 1L)

variantes <- list(qmap_300 = list(y = m$carbono_gm2_qmap, arvores = 300L, semente = 1984L),
                  gm2_400 = list(y = gm2$carbono_gm2, arvores = 400L, semente = 2021L))
pred <- painel[, .(ponto_id, year)]
for (v in names(variantes)) {
  p <- variantes[[v]]
  fit <- ranger(x = m[, ..cols], y = p$y, num.trees = p$arvores, mtry = 24L, min.node.size = 2L,
                max.depth = 40L, num.threads = nthreads, seed = p$semente)
  pred[[v]] <- predict(fit, painel[, ..cols], num.threads = nthreads)$predictions / 100
  cat(sprintf("%s: OOB R² %.4f, média no painel %.2f t/ha\n", v, fit$r.squared, mean(pred[[v]])))
}
write_parquet(pred, file.path(dados_dir, "painel_fidelidade.parquet"))
