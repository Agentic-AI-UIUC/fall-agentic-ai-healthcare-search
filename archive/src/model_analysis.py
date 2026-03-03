from benchmark import test_model
import pandas as pd

models = ["sentence-transformers/LaBSE","sentence-transformers/all-MiniLM-L12-v2","sentence-transformers/all-mpnet-base-v2"]


model_stats = {model:0 for model in models}
for model in models:
    model_stats = pd.DataFrame(columns=["Encoding Time", "Similarity Time"])
    for _ in range(30):
        data = pd.DataFrame(test_model(model, verbose=0),index=[0])
        model_stats = pd.concat([model_stats,data])
    print(model_stats.describe())
    model_stats[model] = [model, model_stats.mean(),model_stats.median(),model_stats.std()]

print("-" * 20)

for row in sorted(model_stats.values(),key = lambda x: x[0]):
    print(row)