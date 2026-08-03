import pandas as pd
from sklearn.model_selection import train_test_split

# Load dataset
csv_path = r'c:\Users\ranug\Clario\clario\ml_finetuning\data\curated_synthetic_lms\curated_lms_tickets.csv'
df_raw = pd.read_csv(csv_path)

# Split
df_train, df_test = train_test_split(
    df_raw, 
    test_size=0.3, 
    random_state=42, 
    stratify=df_raw['category']
)

# Save
train_path = r'c:\Users\ranug\Clario\clario\ml_finetuning\data\curated_synthetic_lms\train_split.csv'
test_path = r'c:\Users\ranug\Clario\clario\ml_finetuning\data\curated_synthetic_lms\test_split.csv'

df_train.to_csv(train_path, index=False)
df_test.to_csv(test_path, index=False)
print("Splits created successfully!")
