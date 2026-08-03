import csv
import random
from collections import defaultdict

random.seed(42)

input_file = r'c:\Users\ranug\Clario\clario\ml_finetuning\data\curated_synthetic_lms\curated_lms_tickets.csv'
train_file = r'c:\Users\ranug\Clario\clario\ml_finetuning\data\curated_synthetic_lms\train_split.csv'
test_file = r'c:\Users\ranug\Clario\clario\ml_finetuning\data\curated_synthetic_lms\test_split.csv'

grouped = defaultdict(list)
with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    cat_idx = header.index('category')
    for row in reader:
        grouped[row[cat_idx]].append(row)

train_rows = []
test_rows = []

for cat, rows in grouped.items():
    random.shuffle(rows)
    split_point = int(len(rows) * 0.7)
    train_rows.extend(rows[:split_point])
    test_rows.extend(rows[split_point:])

random.shuffle(train_rows)
random.shuffle(test_rows)

with open(train_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(train_rows)

with open(test_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(test_rows)

print(f"Success! Train size: {len(train_rows)}, Test size: {len(test_rows)}")
