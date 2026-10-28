# Convert curatedMetagenomicData .rda matrices to TSV (base R + Matrix only; no Bioconductor needed).
# Usage: Rscript scripts/cmd_rda_to_tsv.R in.rda out.tsv
args <- commandArgs(trailingOnly = TRUE)
env <- new.env()
obj <- get(load(args[1], envir = env)[1], envir = env)
if (inherits(obj, "Matrix")) obj <- as.matrix(obj)
out <- data.frame(feature = rownames(obj), obj, check.names = FALSE)
write.table(out, args[2], sep = "\t", quote = FALSE, row.names = FALSE)
cat(sprintf("%s: %d features x %d samples\n", basename(args[2]), nrow(obj), ncol(obj)))
