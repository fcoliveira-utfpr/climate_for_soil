# Seleção aninhada do clima contínuo (§4.3b, passo 1): só com o treino da dobra, ajusta com as 15 contínuas,
# percorre os pares com |r de Spearman| > 0,9 (do maior para o menor) e descarta a menos importante de cada
# par (importância por impureza). Devolve as colunas mantidas.
LIMIAR_R <- 0.9
selecionar_continuas <- function(m, y_g, treino, cfg, nthreads, semente) {
  cont <- unlist(cfg$cenarios$cont_ambos)
  X <- m[treino, c(cfg$base, cont), with = FALSE]
  fit <- ranger(x = X, y = y_g[treino], num.trees = 300L, mtry = 24L, min.node.size = 2L, max.depth = 40L,
                importance = "impurity", num.threads = nthreads, seed = semente)
  imp <- fit$variable.importance[cont]
  r <- abs(cor(m[treino, ..cont], method = "spearman"))
  r[lower.tri(r, diag = TRUE)] <- 0
  pares <- which(r > LIMIAR_R, arr.ind = TRUE)
  pares <- pares[order(-r[pares]), , drop = FALSE]
  manter <- cont
  for (k in seq_len(nrow(pares))) {
    a <- cont[pares[k, 1]]; b <- cont[pares[k, 2]]
    if (a %in% manter && b %in% manter) manter <- setdiff(manter, if (imp[a] >= imp[b]) b else a)
  }
  manter
}
