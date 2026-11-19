# Etapas 3-4 dos mapas de 1 km: modelo final de cada cenário (ranger da produção com a matriz inteira, resposta
# carbono_gm2_qmap direta) e predição do SOC 0-30 cm (t/ha) na grade de 1 km, ano a ano.
#
# Covariáveis: climas/dados_mapas_1km/estaticas/<bloco>.parquet + dinamicas/<ano>/<bloco>.parquet (pixel central de
# 30 m de cada pixel de 1 km; ver covariaveis_1km.py). Junção interna por (col, lin). Na predição, profundidade = 30
# e IFN_index = YEAR_index = PSEUDOROCK_index = PSEUDOSAND_index = 0, como no mapa da produção. Pixels com alguma
# covariável ausente (ex.: textura fora da cobertura) ficam sem predição.
#
# Saídas (fora do git):
#   climas/dados_mapas_1km/modelos/<cenario>.rds
#   climas/dados_mapas_1km/predicoes/<cenario>/<ano>.parquet  (col, lin, lulc, soc em 0,1 t/ha, int16)
#   climas/mapas_1km/resultados/tempos_predicao.csv  (versionado)
#
# Uso: Rscript prever_1km.R <cenario[,cenario...]> <ano0> [ano1]
#      cenários de cenarios.json da análise espaço-tempo (por enquanto: koppen_ipef, sem_clima)
# Retomável: pula modelo e anos que já existem.

.libPaths(c(Sys.getenv("R_LIBS_USER"), .libPaths()))
suppressPackageStartupMessages({
  library(data.table)
  library(ranger)
  library(arrow)
  library(jsonlite)
})

args_all <- commandArgs(trailingOnly = FALSE)
script_dir <- dirname(normalizePath(sub("^--file=", "", args_all[grep("^--file=", args_all)])))
raiz <- normalizePath(file.path(script_dir, "..", "..", ".."))
dados <- file.path(raiz, "climas", "dados_mapas_1km")
matriz_arq <- file.path(raiz, "climas", "dados_espaco_tempo", "matriz_soc_c3_fabricio.parquet")
cfg <- fromJSON(file.path(raiz, "climas", "analise_espaco_tempo", "codigo", "cenarios.json"))
res_dir <- file.path(script_dir, "..", "resultados")
dir.create(res_dir, showWarnings = FALSE, recursive = TRUE)

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) stop("uso: Rscript prever_1km.R <cenario[,...]> <ano0> [ano1]")
cenarios <- strsplit(args[1], ",")[[1]]
anos <- seq(as.integer(args[2]), as.integer(if (length(args) > 2) args[3] else args[2]))
stopifnot(all(cenarios %in% names(cfg$cenarios)))
nthreads <- parallel::detectCores()
LOTE <- 25L                                    # blocos por lote (~280 mil pixels; 100 estoura os 9 GB do Mac)
FIXAS <- c(profundidade = 30, IFN_index = 0, YEAR_index = 0, PSEUDOROCK_index = 0, PSEUDOSAND_index = 0)

colunas <- function(cen) c(cfg$base, unlist(cfg$cenarios[[cen]]))

modelo <- function(cen) {
  arq <- file.path(dados, "modelos", paste0(cen, ".rds"))
  if (file.exists(arq)) return(readRDS(arq))
  dir.create(dirname(arq), showWarnings = FALSE, recursive = TRUE)
  m <- as.data.table(read_parquet(matriz_arq))
  cols <- colunas(cen)
  t0 <- Sys.time()
  fit <- ranger(x = m[, ..cols], y = m$carbono_gm2_qmap, num.trees = 300L, mtry = 24L, min.node.size = 2L,
                max.depth = 40L, num.threads = nthreads, seed = 1984L)
  cat(sprintf("modelo %s: %d linhas, %d covariáveis, OOB R² %.4f, %s\n", cen, nrow(m), length(cols),
              fit$r.squared, format(Sys.time() - t0, digits = 3)))
  saveRDS(fit, arq)
  fit
}

blocos <- sub("\\.parquet$", "", list.files(file.path(dados, "estaticas"), pattern = "\\.parquet$"))
lotes <- split(blocos, ceiling(seq_along(blocos) / LOTE))
ler <- function(pasta, bs) rbindlist(lapply(bs, function(b) read_parquet(file.path(pasta, paste0(b, ".parquet")))))

modelos <- setNames(lapply(cenarios, modelo), cenarios)
tempos_arq <- file.path(res_dir, "tempos_predicao.csv")

for (ano in anos) {
  saidas <- setNames(file.path(dados, "predicoes", cenarios, paste0(ano, ".parquet")), cenarios)
  falta <- cenarios[!file.exists(saidas)]
  if (!length(falta)) { cat(ano, "já feito\n"); next }
  t0 <- Sys.time()
  partes <- setNames(vector("list", length(falta)), falta)
  for (lt in lotes) {
    x <- merge(as.data.table(ler(file.path(dados, "estaticas"), lt)),
               as.data.table(ler(file.path(dados, "dinamicas", ano), lt)), by = c("col", "lin"))
    for (v in names(FIXAS)) set(x, j = v, value = FIXAS[[v]])
    for (cen in falta) {
      cols <- colunas(cen)
      ok <- complete.cases(x[, ..cols])
      p <- predict(modelos[[cen]], x[ok, ..cols], num.threads = nthreads, verbose = FALSE)$predictions / 100   # t/ha
      partes[[cen]][[length(partes[[cen]]) + 1]] <- data.table(col = x$col[ok], lin = x$lin[ok],
                                                               lulc = as.integer(x$lulc[ok]),
                                                               soc = as.integer(round(p * 10)))
    }
    rm(x); invisible(gc())
    message(sprintf("  %d lote %s, %.1f min", ano, lt[1], as.numeric(difftime(Sys.time(), t0, units = "mins"))))
  }
  for (cen in falta) {
    dir.create(dirname(saidas[[cen]]), showWarnings = FALSE, recursive = TRUE)
    out <- rbindlist(partes[[cen]])
    write_parquet(out, saidas[[cen]])
  }
  dt <- as.numeric(difftime(Sys.time(), t0, units = "mins"))
  cat(sprintf("%d: %s, %d pixels, %.1f min\n", ano, paste(falta, collapse = "+"), nrow(out), dt))
  fwrite(data.table(ano = ano, cenarios = paste(falta, collapse = "+"), pixels = nrow(out), minutos = round(dt, 1),
                    threads = nthreads, quando = format(Sys.time())), tempos_arq, append = file.exists(tempos_arq))
}
