import csv
from collections import Counter

file_path = r'c:\Users\ranug\Clario\clario\ml_finetuning\data\curated_synthetic_lms\train_split.csv'

categories = Counter()
priorities = Counter()
sentiments = Counter()

with open(file_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        categories[row.get('category', 'N/A')] += 1
        priorities[row.get('priority', 'N/A')] += 1
        sentiments[row.get('sentiment', 'N/A')] += 1

print("--- CATEGORY BALANCE (TRAIN) ---")
for k, v in categories.most_common(): print(f"{k}: {v}")
print("\n--- PRIORITY BALANCE (TRAIN) ---")
for k, v in priorities.most_common(): print(f"{k}: {v}")
print("\n--- SENTIMENT BALANCE (TRAIN) ---")
for k, v in sentiments.most_common(): print(f"{k}: {v}")
