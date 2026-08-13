install.packages("Hmisc")




Test <- read.csv("C:/Users/enoch/OneDrive/文件/GIthub/Output/merged_output.csv")
View (Test)
attach (Test)

cor(placement, board.value, method = "spearman")
cor.test (placement, board.value, method = "spearman", exact = FALSE, alternative = "two.sided", conf.level = .95)
cor.test (placement, board.value, method = "kendall", exact = FALSE)
