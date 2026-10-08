# Etapa 5: reproduz o OOB do modelo de SOC do MapBiomas (soildata/30_soc_model_validation.R) na matriz
# reconstruída (matriz_soc_c3_fabricio = trainingFinal), cenário Köppen (as covariáveis da produção).
#
# - modelo padrão: ranger, carbono_gm2_qmap ~ 131 covariáveis, 300 árvores, mtry 24, min.node.size 2,
#   max.depth 40, semente 1984; OOB por linha;
# - "sem vazamento": a mesma coisa com o inbag por grupo (perfil + réplicas trep10/trep20), como no R 30.
# Métricas (error_statistics do MapBiomas) em t/ha, em todas as camadas e só na mais funda de cada perfil.
# Saída: resultados/tabelas/fidelidade_oob.csv, ao lado dos números anotados no R 30.
#
# Uso: Rscript fidelidade_oob.R

.libPaths(c(Sys.getenv("R_LIBS_USER"), .libPaths()))
suppressPackageStartupMessages({
  library(data.table)
  library(ranger)
  library(arrow)
})

args_all <- commandArgs(trailingOnly = FALSE)
script_dir <- dirname(normalizePath(sub("^--file=", "", args_all[grep("^--file=", args_all)])))
raiz <- normalizePath(file.path(script_dir, "..", "..", ".."))
matriz_arq <- file.path(raiz, "climas", "dados_espaco_tempo", "matriz_soc_c3_fabricio.parquet")
saida <- file.path(script_dir, "..", "resultados", "tabelas", "fidelidade_oob.csv")

error_statistics <- function(observed, predicted) {     # 00_helper_functions.r do MapBiomas
  error <- predicted - observed
  residual <- mean(observed) - observed
  mse <- mean(error^2)
  data.frame(n = length(observed), me = mean(error), mae = mean(abs(error)), mse = mse,
             rmse = sqrt(mse), mec = 1 - mse / mean(residual^2),
             slope = unname(coef(lm(observed ~ predicted))[2]))
}

covars <- readLines(file.path(script_dir, "covariaveis_modelo_c3.txt"), encoding = "UTF-8")
covars <- covars[!grepl("^#", covars) & nzchar(covars)]

soildata <- as.data.table(read_parquet(matriz_arq))
stopifnot(length(covars) == 131, all(covars %in% names(soildata)))
soildata <- soildata[, c(covars, "carbono_gm2_qmap", "id"), with = FALSE]
setnames(soildata, "id", "dataset_id")
cat("matriz:", nrow(soildata), "linhas,", length(unique(soildata$dataset_id)), "ids\n")

soildata[, is_deepest_layer := profundidade == max(profundidade), by = dataset_id]
soildata[, group_id := sub("trep10-|trep20-", "", dataset_id)]
soildata[, group_id := as.integer(as.factor(group_id))]
unique_groups <- unique(soildata$group_id)
num_groups <- length(unique_groups)
cat("grupos:", num_groups, "\n")

num_trees <- 300L; mtry <- 24L; min_node_size <- 2L; max_depth <- 40L
dados <- soildata[, c(covars, "carbono_gm2_qmap"), with = FALSE]
nthreads <- max(1L, parallel::detectCores() - 1L)

metricas <- function(pred, rotulo) {
  obs <- soildata$carbono_gm2_qmap / 100
  rbind(
    cbind(modelo = rotulo, camadas = "todas", error_statistics(obs, pred / 100)),
    cbind(modelo = rotulo, camadas = "mais funda",
          error_statistics(obs[soildata$is_deepest_layer], pred[soildata$is_deepest_layer] / 100))
  )
}

# Modelo padrão
t0 <- Sys.time()
m_gee <- ranger(carbono_gm2_qmap ~ ., data = dados, num.trees = num_trees, mtry = mtry,
                min.node.size = min_node_size, max.depth = max_depth, importance = "impurity",
                num.threads = nthreads, seed = 1984)
cat("padrão: R² OOB", round(m_gee$r.squared, 4), "| MSE", round(m_gee$prediction.error), "|",
    format(Sys.time() - t0), "\n")
top_gee <- names(sort(m_gee$variable.importance, decreasing = TRUE))[1:5]
cat("top 5:", top_gee, "\n")

# Sem vazamento: inbag por grupo (igual ao R 30)
n_obs <- nrow(soildata)
group_idx <- split(seq_len(n_obs), soildata$group_id)
custom_inbag <- lapply(seq_len(num_trees), function(i) {
  set.seed(i)
  sampled_groups <- sample(unique_groups, size = num_groups, replace = TRUE)
  group_counts <- tabulate(match(sampled_groups, unique_groups), nbins = num_groups)
  row_weights <- integer(n_obs)
  for (g in which(group_counts > 0L)) row_weights[group_idx[[g]]] <- group_counts[g]
  row_weights
})
m_noleak <- ranger(carbono_gm2_qmap ~ ., data = dados, num.trees = num_trees, mtry = mtry,
                   min.node.size = min_node_size, max.depth = max_depth, inbag = custom_inbag,
                   importance = "impurity", num.threads = nthreads, seed = 1984)
cat("sem vazamento: R² OOB", round(m_noleak$r.squared, 4), "| MSE", round(m_noleak$prediction.error), "\n")

nosso <- rbind(metricas(m_gee$predictions, "padrão"), metricas(m_noleak$predictions, "sem vazamento"))
nosso$fonte <- "matriz_soc_c3_fabricio"
mapbiomas <- data.frame(   # anotado no 30_soc_model_validation.R
  modelo = c("padrão", "padrão", "sem vazamento", "sem vazamento"),
  camadas = c("todas", "mais funda", "todas", "mais funda"),
  n = c(27425, 14752, 27425, NA),
  me = c(0.32, -1.97, 1.04, -1.07), mae = c(11.74, 13.81, 15.63, 17.27),
  mse = c(714.24, 1070.66, 1107.99, 1481.04), rmse = c(26.73, 32.72, 33.29, 38.48),
  mec = c(0.73, 0.67, 0.58, 0.54), slope = c(1.10, 1.24, 1.04, 1.19),
  fonte = "MapBiomas (R 30)")
tab <- rbind(nosso, mapbiomas)
dir.create(dirname(saida), recursive = TRUE, showWarnings = FALSE)
fwrite(tab, saida)
num <- c("me", "mae", "mse", "rmse", "mec", "slope")
tab[num] <- lapply(tab[num], round, 2)
print(tab[order(tab$modelo, tab$camadas, tab$fonte), ], row.names = FALSE)
cat("\nimportância (sem vazamento), top 10:\n")
print(round(head(sort(m_noleak$variable.importance, decreasing = TRUE), 10) / 1e9, 1))
