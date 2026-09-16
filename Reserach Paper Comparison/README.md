# Research Paper Evaluation — Support Ticket Categorization & Prioritization

Reproduction of the methodology from **"Customer Support Ticket Categorization and Prioritization Using
Natural Language Processing"** (C. S Kanimozhi Selvi, S. Jyothi Shri, R. Prasshanthini, Neelamegan,
R. Sanjay — Department of Artificial Intelligence, Kongu Engineering College, Erode, Tamilnadu, India;
INCOFT 2025), applied to **our own LMS support-ticket dataset** instead of the paper's 78,313 financial
complaint records.

The goal is not to beat the paper. It is to run the paper's exact model line-up on our data, under
documented settings, so we know which of its claims transfer to our domain and which do not.

* Paper PDF: [136404.pdf](136404.pdf)
* 10 models × 2 tasks = **20 trained models** (7 ML + 3 DL, each trained for category and for priority)

---

## Table of Contents

1. [Repository Structure](#1-repository-structure)
2. [Dataset](#2-dataset)
3. [Tasks](#3-tasks)
4. [What the Notebooks Do](#4-what-the-notebooks-do)
5. [Preprocessing](#5-preprocessing)
6. [Feature Extraction / Tokenization](#6-feature-extraction--tokenization)
7. [Train–Test Split](#7-traintest-split)
8. [Class Imbalance Handling](#8-class-imbalance-handling)
9. [Model Configurations](#9-model-configurations)
10. [Results — Category Classification](#10-results--category-classification)
11. [Results — Priority Classification](#11-results--priority-classification)
12. [Overall Leaderboard](#12-overall-leaderboard)
13. [Per-Class Reports and Confusion Matrices](#13-per-class-reports-and-confusion-matrices)
14. [Training Loss Logs](#14-training-loss-logs)
15. [Comparison with the Paper](#15-comparison-with-the-paper)
16. [Observations](#16-observations)
17. [Reproduction](#17-reproduction)
18. [Known Deviations from the Paper](#18-known-deviations-from-the-paper)

---

## 1. Repository Structure

```
Research Paper Evaluation/
├── 136404.pdf                              # The source research paper
├── data/
│   └── curated_lms_tickets.csv             # 20,000 LMS support tickets
├── Research_paper_evaluation_ML.ipynb      # 7 classical ML models (TF-IDF)
├── Research_paper_evaluation_Bert.ipynb    # BERT fine-tuning
├── Research_paper_evaluation_RNN.ipynb     # BiLSTM from scratch
├── Research_paper_evaluation_CNN.ipynb     # TextCNN from scratch
├── models/
│   ├── cnn/
│   │   ├── category_classification/        # cnn_category_model.pt + vocab.json
│   │   └── priority_classification/        # cnn_priority_model.pt + vocab.json
│   └── rnn/
│       ├── category_classification/        # rnn_category_model.pt + vocab.json
│       └── priority_classification/        # rnn_priority_model.pt + vocab.json
└── results/
    ├── ML/
    │   ├── category_classification_results.csv
    │   └── priority_classification_results.csv
    ├── DL/
    │   ├── cnn/evaluation_results_cnn.csv
    │   └── rnn/evaluation_results_rnn.csv
    └── Bert.zip                            # evaluation_results_bert.csv + saved BERT models
```

The BERT artefacts live inside `results/Bert.zip` (the fine-tuned weights are ~436 MB each, so they were
archived rather than committed loose). The zip contains:

```
evaluation_results_bert.csv
models/bert/category_classification/bert_category_model/{config.json, model.safetensors}
models/bert/category_classification/bert_category_tokenizer/{tokenizer.json, tokenizer_config.json}
models/bert/priority_classification/bert_priority_model/{config.json, model.safetensors}
models/bert/priority_classification/bert_priority_tokenizer/{tokenizer.json, tokenizer_config.json}
```

---

## 2. Dataset

**`data/curated_lms_tickets.csv`** — 20,000 rows × 13 columns, synthetic LMS (Learning Management System)
support tickets for the "Rysera STEM LMS" platform, generated with Gemini (`source = gemini_synthetic_lms`).

### Columns

| Column | Type | Notes |
|---|---|---|
| `ticket_id` | string | `LMS-SYN-00001` … `LMS-SYN-20000` |
| `category` | string | **Target 1** — 8 classes |
| `issue_description` | string | **The only input feature used by every model** |
| `priority` | string | **Target 2** — 4 ordinal classes |
| `sentiment` | string | Negative / Neutral / Strongly Negative / Positive (unused) |
| `product` | string | 10 distinct LMS products (unused) |
| `resolution_notes` | string | Free text (unused) |
| `status` | string | Resolved / Closed / In Progress / Open / Pending Customer (unused) |
| `channel` | string | Email / Chat / Web Form / Phone / Social Media (unused) |
| `language` | string | English (constant) |
| `issue_complexity_score` | int | 1–10, mean 4.04, std 1.90 (unused) |
| `platform` | string | Rysera STEM LMS (constant) |
| `source` | string | gemini_synthetic_lms (constant) |

Only `issue_description` is fed to the models. Everything else is metadata, matching the paper's setup of
classifying from free-text complaint content alone.

### Data quality checks (run in every notebook)

| Check | Result |
|---|---|
| Total records | 20,000 |
| Duplicated records | 0 |
| Missing values (all columns) | 0 |
| Rows with `XXX`-style masks (`[xX]{3,}`) | 0 |
| Rows with bracket/tag placeholders (`<…>`, `{…}`, `[…]`) | 0 |
| Rows matching masked-number regex (`\b[0-9X-]{5,}\b`) | 1 — inspected, it is a **real** transaction ID (`LMS-SYN-14040`), not a mask → kept |
| Rows containing any number | 663 (raw text) / 643 (after ML notebook's punctuation stripping) |

**No rows were dropped.** All 20,000 records survive into training.

### Label distributions

**`category` — perfectly balanced (2,500 each):**

| Category | Count | Share |
|---|---:|---:|
| Account Suspension | 2,500 | 12.5% |
| Bug Report | 2,500 | 12.5% |
| Feature Request | 2,500 | 12.5% |
| Login Issue | 2,500 | 12.5% |
| Payment Problem | 2,500 | 12.5% |
| Performance Issue | 2,500 | 12.5% |
| Refund Request | 2,500 | 12.5% |
| Subscription Cancellation | 2,500 | 12.5% |

**`priority` — imbalanced:**

| Priority | Count | Share |
|---|---:|---:|
| Medium | 8,271 | 41.4% |
| High | 5,909 | 29.5% |
| Low | 4,365 | 21.8% |
| Urgent | 1,455 | 7.3% |

This imbalance is the reason class weights are applied to the priority task only (see §8).

### Text length statistics (after cleaning/tokenization)

| Statistic | Tokens |
|---|---:|
| count | 20,000 |
| mean | 12.00 |
| std | 4.34 |
| min | 3 |
| 25% | 9 |
| 50% (median) | 11 |
| 75% | 15 |
| max | 45 |
| 90th percentile | 18 |
| 95th percentile | 20 |
| Truncated at `MAX_LEN=128` | **0.00%** |

`MAX_LEN = 128` was verified against this distribution rather than guessed — nothing is truncated.

---

## 3. Tasks

| Task | Target | Classes | Encoder | Class order |
|---|---|---|---|---|
| **Category classification** | `category` | 8 | `LabelEncoder` | alphabetical |
| **Priority classification** | `priority` | 4 | `OrdinalEncoder` | `['Low', 'Medium', 'High', 'Urgent']` |

`OrdinalEncoder` with an explicit `categories=` list is used for priority so that the encoding preserves
the real severity ordering (Low=0 → Urgent=3), rather than the alphabetical order `LabelEncoder` would
have produced (High=0, Low=1, Medium=2, Urgent=3).

---

## 4. What the Notebooks Do

All four notebooks follow the same skeleton so results stay comparable:

```
1.  Imports & hyperparameter constants
2.  Device selection (CUDA / CPU)                       [DL notebooks only]
3.  Load dataset
4.  Dataset-compatibility check (size, labels, domain)
5.  Preprocessing / data-quality audit
      - duplicates, missing values
      - masked-PII regex sweeps (X-masks, tags, numeric masks)
      - number audit
6.  Label encoding (LabelEncoder + OrdinalEncoder)
7.  Text cleaning                                       [varies per notebook — see §5]
8.  Sequence-length audit → justifies MAX_LEN           [RNN/CNN]
9.  80/20 stratified train-test split (one per task)
10. Feature extraction / vocabulary build               [see §6]
11. Dataset & DataLoader classes                        [DL notebooks]
12. Model definition                                    [DL notebooks]
13. Class-weight computation (priority only)
14. Train → save model → evaluate on test set
15. Write metrics to results CSV
```

### Notebook-by-notebook

| Notebook | Models | Feature representation | Runtime |
|---|---|---|---|
| `Research_paper_evaluation_ML.ipynb` | Logistic Regression, Decision Tree, Random Forest, SVM, Multinomial NB, Gradient Boosting, XGBoost | TF-IDF (uni+bigram) | Local CPU (Python 3.14) |
| `Research_paper_evaluation_Bert.ipynb` | `bert-base-cased` fine-tuned | WordPiece (pretrained, 28,996 tokens) | Kaggle GPU (CUDA) |
| `Research_paper_evaluation_RNN.ipynb` | 2-layer BiLSTM | Custom vocabulary + learned embeddings | Kaggle GPU (CUDA) |
| `Research_paper_evaluation_CNN.ipynb` | TextCNN (Kim, 2014) | Custom vocabulary + learned embeddings | Kaggle GPU (CUDA) |

The DL notebooks load from the Kaggle dataset path
`/kaggle/input/datasets/sinethwickramaratna/curated-lms-tickets/curated_lms_tickets.csv`;
the ML notebook loads from the local `./data/curated_lms_tickets.csv`.

---

## 5. Preprocessing

The paper (Section 3.2) prescribes: drop unnecessary/duplicate fields → remove blank/incomplete rows →
lowercase → strip punctuation with regex → lemmatize → remove masked personal-data placeholders.

We implement this, but **not identically across notebooks** — deliberately, and for a defensible reason.

### 5.1 ML notebook (TF-IDF pipeline) — full paper pipeline

Applied in order, in-place on `issue_description`:

| Step | Implementation |
|---|---|
| Duplicate removal | `df.duplicated().sum()` → 0, nothing dropped |
| Blank/incomplete removal | `df.isnull().sum().sum()` → 0, nothing dropped |
| Lowercase + trim | `.str.lower().str.strip()` |
| Punctuation strip | `.str.replace(r'[^\w\s]', '', regex=True)` |
| Whitespace collapse | `.str.replace(r'\s+', ' ', regex=True)` |
| Lemmatization | NLTK `WordNetLemmatizer`, applied token-wise after `.split()` |
| Masked-PII sweep | 3 regex checks (see §2) → nothing to remove |

### 5.2 RNN & CNN notebooks — same paper pipeline, plus number normalization

These two notebooks share a **byte-identical** `clean_text` / `tokenize` implementation, so any difference
between the RNN and CNN scores comes from architecture, not preprocessing.

```python
def clean_text(text):
    """Lowercase, normalise numbers, strip punctuation (paper Section 3.2)."""
    text = str(text).lower()
    text = re.sub(r'\b[0-9]+([.,][0-9]+)?\b', ' <num> ', text)   # pure numbers -> placeholder
    text = re.sub(r'[^a-z0-9<>\s]', ' ', text)                   # drop punctuation
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def tokenize(text):
    tokens = clean_text(text).split()
    if _lemmatizer is not None:
        tokens = [t if t.startswith('<') else _lemmatizer.lemmatize(t) for t in tokens]
    return tokens
```

Two design decisions worth recording:

* **Numbers become `<num>` rather than being deleted.** Deleting them loses the signal that a number was
  present; keeping them raw fills a 20k-cap vocabulary with one-off transaction and account IDs. The
  placeholder keeps the signal at a cost of one vocabulary slot.
* **`<num>` is protected from lemmatization** via the `t.startswith('<')` guard, so the placeholder and
  the `<PAD>` / `<UNK>` specials survive intact.

Example of the transform:

```
BEFORE: Account is suspended but I am just a student trying to buy new courses.
AFTER : account is suspended but i am just a student trying to buy new course
```

### 5.3 BERT notebook — deliberately *no* text cleaning

BERT is fed the **raw, unmodified `issue_description`**. This is an intentional departure from the paper's
Section 3.2, on the grounds that:

* WordPiece and the pretrained `bert-base-cased` weights expect ordinary English — casing, punctuation and
  inflection all carry information the pretrained representation already knows how to use.
* Lowercasing text for a **cased** checkpoint destroys signal the model was pretrained on.
* Lemmatizing before WordPiece produces token sequences unlike anything seen during pretraining.

The RNN and CNN, by contrast, learn embeddings **from scratch on our vocabulary**, where every surface
variant (`Payment`, `payment`, `payment,`, `payments`) would otherwise occupy its own row in the embedding
matrix. That is exactly the problem the paper's preprocessing solves, so it is applied there.

### 5.4 Preprocessing matrix

| Step | ML | BERT | RNN | CNN |
|---|:--:|:--:|:--:|:--:|
| Duplicate / null audit | ✅ | ✅ | ✅ | ✅ |
| Masked-PII regex sweep | ✅ | ✅ | ✅ | ✅ |
| Lowercase | ✅ | ❌ | ✅ | ✅ |
| Punctuation strip | ✅ | ❌ | ✅ | ✅ |
| Whitespace collapse | ✅ | ❌ | ✅ | ✅ |
| Lemmatization (WordNet) | ✅ | ❌ | ✅ | ✅ |
| Number → `<num>` | ❌ | ❌ | ✅ | ✅ |
| Sequence-length audit | ❌ | ❌ | ✅ | ✅ |

---

## 6. Feature Extraction / Tokenization

### 6.1 TF-IDF (ML notebook)

```python
vectorizer = TfidfVectorizer(
    min_df=5,                # a term must appear in >= 5 documents
    stop_words='english',    # sklearn's built-in English stop-word list
    ngram_range=(1, 2)       # unigrams + bigrams
)
X = vectorizer.fit_transform(df['issue_description'])
```

| Parameter | Value | Rationale |
|---|---|---|
| `min_df` | 5 | Drops hapax/near-hapax noise terms |
| `max_df` | default (1.0) | Not restricted |
| `max_features` | default (None) | No vocabulary cap |
| `stop_words` | `'english'` | Paper does not specify; documented as a divergence |
| `ngram_range` | `(1, 2)` | Bigrams capture phrases like `"not working"`, `"cannot login"` |
| `norm` / `sublinear_tf` | defaults (`l2`, `False`) | |

> ⚠️ **Known leakage caveat:** TF-IDF is fitted on the **full corpus** before the train/test split. This
> leaks test-set document frequencies into the vectorizer. The effect on TF-IDF is small (it is an
> unsupervised term-weighting fit, no labels involved), but it is a real methodological wart and the ML
> numbers should be read with it in mind. The RNN/CNN vocabularies do **not** have this problem — they are
> fitted on the training split only (see §6.3).

### 6.2 WordPiece (BERT notebook)

```python
tokenizer = BertTokenizer.from_pretrained('google-bert/bert-base-cased')
encoding = tokenizer(
    text,
    add_special_tokens=True,   # [CLS] ... [SEP]
    max_length=128,
    padding='max_length',
    truncation=True,
    return_tensors='pt'
)
```

Fixed 28,996-token cased WordPiece vocabulary, inherited from pretraining. Produces `input_ids` +
`attention_mask`.

### 6.3 Custom vocabulary (RNN & CNN notebooks)

```python
def build_vocab(texts, max_size=MAX_VOCAB_SIZE, min_freq=MIN_FREQ):
    counter = Counter()
    for t in texts:
        counter.update(tokenize(t))
    vocab = {PAD_TOKEN: PAD_IDX, UNK_TOKEN: UNK_IDX}
    for word, freq in counter.most_common():
        if freq < min_freq or len(vocab) >= max_size:
            break
        vocab[word] = len(vocab)
    return vocab
```

Two rules enforced here:

1. **Fitted on the training split only** — building the vocabulary over the full dataset would leak
   test-set information into training.
2. **One vocabulary per task** — the category and priority splits use different `stratify` arguments, so
   their training sets are not identical. Each task gets its own vocabulary from its own training rows.

| Vocabulary | Size | Cap | `min_freq` |
|---|---:|---:|---:|
| Category (RNN & CNN) | **2,091** | 20,000 | 2 |
| Priority (RNN & CNN) | **2,078** | 20,000 | 2 |

Both land far below the 20,000 cap — the ticket language is narrow and repetitive, which is itself a useful
finding about this dataset. Special tokens: `<PAD>` = index 0, `<UNK>` = index 1.

---

## 7. Train–Test Split

Identical across all four notebooks:

```python
train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
```

| Setting | Value |
|---|---|
| Train / test ratio | 80 / 20 |
| Train size | 16,000 |
| Test size | 4,000 |
| `random_state` | 42 |
| Stratification | on the task's own label |
| Validation split | **none** |

**Two separate splits are made**, one per task, because they stratify on different label vectors:

* Category split → stratified on `y_category_encoded` → test set has exactly 500 of each of 8 categories.
* Priority split → stratified on `y_priority_encoded` → test set has 873 Low / 1,654 Medium / 1,182 High /
  291 Urgent.

No validation split was carved out because the paper does not report using cross-validation or a held-out
validation set, and adding one would have made the comparison less direct. The consequence is that there
is **no early stopping** — epoch counts are fixed (see §18).

---

## 8. Class Imbalance Handling

Category labels are perfectly balanced (2,500 each), so **no class weighting is applied to the category
task** in any notebook.

Priority labels are imbalanced (Urgent is only 7.3%), so all three DL notebooks compute balanced class
weights:

```python
unique_classes_priority = np.unique(y_priority_encoded)
class_weights_priority = compute_class_weight(
    class_weight='balanced',
    classes=unique_classes_priority,
    y=y_priority_encoded.flatten()
)
criterion = nn.CrossEntropyLoss(
    weight=torch.tensor(class_weights_priority, dtype=torch.float).to(device)
)
```

Resulting weights (`n_samples / (n_classes × n_class_samples)`):

| Class | Count | Weight |
|---|---:|---:|
| Low | 4,365 | ≈ 1.145 |
| Medium | 8,271 | ≈ 0.605 |
| High | 5,909 | ≈ 0.846 |
| Urgent | 1,455 | ≈ 3.436 |

> Note: weights are computed on the **full** label vector, not the training split. With stratified
> splitting the class proportions are essentially identical, so the practical difference is negligible.

The classical ML models use **no** class weighting (`class_weight` left at default `None`) — which shows
up clearly in their weak Urgent recall (see §11).

---

## 9. Model Configurations

### 9.1 Classical ML — `Research_paper_evaluation_ML.ipynb`

All seven models take the same TF-IDF matrix as input and use scikit-learn defaults except where noted.
`random_state=42` everywhere it is accepted.

| # | Model | Class | Configuration | Notable defaults |
|---|---|---|---|---|
| 1 | Logistic Regression | `LogisticRegression` | `random_state=42` | `penalty='l2'`, `C=1.0`, `solver='lbfgs'`, `max_iter=100`, multinomial |
| 2 | Decision Tree | `DecisionTreeClassifier` | `random_state=42` | `criterion='gini'`, `max_depth=None` (grown to purity), `min_samples_split=2` |
| 3 | Random Forest | `RandomForestClassifier` | `n_estimators=100, random_state=42` | `criterion='gini'`, `max_depth=None`, `max_features='sqrt'`, `bootstrap=True` |
| 4 | SVM | `SVC` | `random_state=42` | `C=1.0`, `kernel='rbf'`, `gamma='scale'`, one-vs-one |
| 5 | Multinomial Naive Bayes | `MultinomialNB` | *(no args)* | `alpha=1.0` (Laplace), `fit_prior=True` |
| 6 | Gradient Boosting | `GradientBoostingClassifier` | `random_state=42` | `n_estimators=100`, `learning_rate=0.1`, `max_depth=3`, `subsample=1.0` |
| 7 | XGBoost | `XGBClassifier` | `random_state=42` | `n_estimators=100`, `learning_rate=0.3`, `max_depth=6`, `objective='multi:softprob'` |

Each is trained twice — once on the category split, once on the priority split — for **14 ML models**.

**Metrics:** `accuracy_score`, and `f1_score` / `precision_score` / `recall_score` all with
`average='weighted'`.

### 9.2 BERT — `Research_paper_evaluation_Bert.ipynb`

```python
MODEL_NAME          = 'google-bert/bert-base-cased'
NUM_LABELS_CATEGORY = 8
NUM_LABELS_PRIORITY = 4
MAX_LEN             = 128
BATCH_SIZE          = 16
EPOCHS_CATEGORY     = 10
EPOCHS_PRIORITY     = 25
LEARNING_RATE       = 2e-5
```

| Setting | Value |
|---|---|
| Checkpoint | `google-bert/bert-base-cased` |
| Head | `BertForSequenceClassification` (linear head over pooled `[CLS]`) |
| Encoder layers | 12 |
| Hidden size | 768 |
| Attention heads | 12 |
| Intermediate size | 3,072 |
| Vocabulary | 28,996 (cased WordPiece) |
| Position embeddings | 512 |
| Internal dropout | 0.1 (embeddings, attention, output, classifier) |
| Activation | GELU |
| Optimizer | `torch.optim.AdamW` |
| Learning rate | 2e-5 |
| LR schedule | **none** (constant) |
| Weight decay | AdamW default (0.01) |
| Warmup | none |
| Gradient clipping | none |
| Max sequence length | 128 (`padding='max_length'`, `truncation=True`) |
| Batch size | 16 |
| Epochs (category) | 10 |
| Epochs (priority) | 25 |
| Loss — category | `outputs.loss` from `BertForSequenceClassification` (unweighted CE) |
| Loss — priority | explicit `nn.CrossEntropyLoss(weight=class_weights_priority)` over `outputs.logits` |
| Fine-tuning scope | full model (no frozen layers) |
| Device | CUDA |
| Seed | not explicitly set in this notebook |

On load, `classifier.weight` / `classifier.bias` are newly initialized (expected — the pretraining head is
discarded) and the seven `cls.*` MLM/NSP tensors are reported UNEXPECTED and dropped (also expected).

### 9.3 RNN (BiLSTM) — `Research_paper_evaluation_RNN.ipynb`

```python
NUM_LABELS_CATEGORY = 8
NUM_LABELS_PRIORITY = 4
MAX_LEN             = 128
BATCH_SIZE          = 32
EPOCHS_CATEGORY     = 10
EPOCHS_PRIORITY     = 25

LEARNING_RATE       = 1e-3     # RNNs train from scratch, so 2e-5 is far too small
MAX_VOCAB_SIZE      = 20000
MIN_FREQ            = 2
EMBEDDING_DIM       = 200
HIDDEN_DIM          = 128
NUM_LAYERS          = 2
BIDIRECTIONAL       = True
DROPOUT             = 0.3
CLIP                = 5.0      # gradient clipping guards against exploding gradients

PAD_TOKEN, PAD_IDX  = '<PAD>', 0
UNK_TOKEN, UNK_IDX  = '<UNK>', 1
SEED                = 42       # torch.manual_seed + np.random.seed
```

**Architecture:**

```
Embedding(vocab_size, 200, padding_idx=0)
  → Dropout(0.3)
  → pack_padded_sequence(enforce_sorted=False)
  → LSTM(200, 128, num_layers=2, bidirectional=True, dropout=0.3, batch_first=True)
  → concat(h[-2], h[-1])                    # final forward + backward hidden states → 256-dim
  → Dropout(0.3)
  → Linear(256, num_labels)
```

Instantiated shapes:

```
RNNClassifier(                                    RNNClassifier(
  (embedding): Embedding(2091, 200, padding_idx=0)  (embedding): Embedding(2078, 200, padding_idx=0)
  (rnn): LSTM(200, 128, num_layers=2,               (rnn): LSTM(200, 128, num_layers=2,
              batch_first=True, dropout=0.3,                    batch_first=True, dropout=0.3,
              bidirectional=True)                               bidirectional=True)
  (dropout): Dropout(p=0.3)                         (dropout): Dropout(p=0.3)
  (fc): Linear(256 → 8)                             (fc): Linear(256 → 4)
)   # category                                    )   # priority
```

| Setting | Value |
|---|---|
| Cell type | `nn.LSTM` (swappable to `nn.RNN` / `nn.GRU` via the `RNN_CELL` constant) |
| Optimizer | `torch.optim.Adam` |
| Learning rate | 1e-3 |
| Gradient clipping | `clip_grad_norm_(..., 5.0)` |
| Padding handling | `pack_padded_sequence` with true per-sample `lengths` |
| Batch size | 32 |
| Loss — category | `nn.CrossEntropyLoss()` |
| Loss — priority | `nn.CrossEntropyLoss(weight=class_weights_priority)` |
| Device | CUDA |

**Why LSTM and not vanilla RNN:** a plain `nn.RNN` matches the paper's wording literally but suffers badly
from vanishing gradients. `nn.LSTM` is the standard practical realisation of "RNN" in this literature; the
notebook exposes `RNN_CELL` so the strict reading can be run for comparison.

### 9.4 CNN (TextCNN) — `Research_paper_evaluation_CNN.ipynb`

```python
NUM_LABELS_CATEGORY = 8
NUM_LABELS_PRIORITY = 4
MAX_LEN             = 128
BATCH_SIZE          = 32
EPOCHS_CATEGORY     = 10
EPOCHS_PRIORITY     = 25

LEARNING_RATE       = 1e-3     # shared with the RNN notebook so the two are comparable
MAX_VOCAB_SIZE      = 20000
MIN_FREQ            = 2
EMBEDDING_DIM       = 200
DROPOUT             = 0.5      # TextCNN is usually run with heavier dropout than an RNN

N_FILTERS           = 100      # feature maps per filter size
FILTER_SIZES        = [3, 4, 5]  # n-gram widths the convolutions scan for

PAD_TOKEN, PAD_IDX  = '<PAD>', 0
UNK_TOKEN, UNK_IDX  = '<UNK>', 1
SEED                = 42       # torch.manual_seed + np.random.seed

assert MAX_LEN >= max(FILTER_SIZES)
```

**Architecture** (standard TextCNN, Kim 2014 — what the paper describes in Section 3.4.3):

```
Embedding(vocab_size, 200, padding_idx=0)     → (batch, 128, 200)
  → permute to (batch, 200, 128)              # embed dim becomes the channel dim
  → 3 parallel Conv1d(200 → 100, kernel_size ∈ {3,4,5}) + ReLU
  → max_pool1d over the time axis             # "did this n-gram appear anywhere?"
  → concat → (batch, 300)
  → Dropout(0.5)
  → Linear(300, num_labels)
```

| Setting | Value |
|---|---|
| Filter widths | 3, 4, 5 (trigram / 4-gram / 5-gram detectors) |
| Feature maps per width | 100 → 300 pooled features total |
| Pooling | max-over-time |
| Optimizer | `torch.optim.Adam` |
| Learning rate | 1e-3 |
| Dropout | 0.5 |
| Gradient clipping | none |
| Batch size | 32 |
| Loss — category | `nn.CrossEntropyLoss()` |
| Loss — priority | `nn.CrossEntropyLoss(weight=class_weights_priority)` |
| Device | CUDA |

**Why no `lengths` / mask:** the CNN convolves over the fixed-width sequence and then max-pools. Because
the `<PAD>` embedding is held at zero and the conv outputs pass through ReLU, padded positions contribute
non-negative values that lose the max to any genuine feature — so a fixed-width input is fine and no mask
is required. (The RNN *does* need `lengths`, since it steps through the sequence one token at a time.)

### 9.5 Shared-hyperparameter comparison

| Hyperparameter | BERT | RNN (BiLSTM) | CNN (TextCNN) |
|---|---|---|---|
| `MAX_LEN` | 128 | 128 | 128 |
| `BATCH_SIZE` | 16 | 32 | 32 |
| `EPOCHS_CATEGORY` | 10 | 10 | 10 |
| `EPOCHS_PRIORITY` | 25 | 25 | 25 |
| `LEARNING_RATE` | 2e-5 | 1e-3 | 1e-3 |
| Optimizer | AdamW | Adam | Adam |
| Embedding dim | 768 (pretrained) | 200 (learned) | 200 (learned) |
| Dropout | 0.1 | 0.3 | 0.5 |
| Gradient clipping | — | 5.0 | — |
| Seed | not set | 42 | 42 |
| Parameters (approx.) | ~108M | ~1.3M | ~0.6M |

---

## 10. Results — Category Classification

8 classes · 16,000 train / 4,000 test · balanced (500 per class in test).
All metrics are **weighted** averages. Source: `results/ML/category_classification_results.csv`,
`results/DL/*/evaluation_results_*.csv`, `results/Bert.zip → evaluation_results_bert.csv`.

### 10.1 Machine Learning models

| Model | Accuracy | F1 (weighted) | Precision (weighted) | Recall (weighted) |
|---|---:|---:|---:|---:|
| **SVM** | **0.94175** | **0.94190** | **0.94225** | **0.94175** |
| Logistic Regression | 0.93475 | 0.93476 | 0.93503 | 0.93475 |
| XGBoost | 0.92375 | 0.92449 | 0.92585 | 0.92375 |
| Random Forest | 0.91625 | 0.91666 | 0.91804 | 0.91625 |
| Naive Bayes | 0.90700 | 0.90513 | 0.90564 | 0.90700 |
| Gradient Boosting | 0.90600 | 0.90828 | 0.91327 | 0.90600 |
| Decision Tree | 0.88850 | 0.88890 | 0.88979 | 0.88850 |

### 10.2 Deep Learning models

| Model | Accuracy | F1 (weighted) | Precision (weighted) | Recall (weighted) |
|---|---:|---:|---:|---:|
| **BERT** | **0.95350** | **0.95314** | **0.95303** | **0.95350** |
| RNN (BiLSTM) | 0.95000 | 0.94988 | 0.95002 | 0.95000 |
| CNN (TextCNN) | 0.93750 | 0.93782 | 0.93870 | 0.93750 |

### 10.3 All 10 models, ranked

| Rank | Model | Family | Accuracy | F1 (weighted) |
|---:|---|---|---:|---:|
| 1 | BERT | DL | 0.95350 | 0.95314 |
| 2 | RNN (BiLSTM) | DL | 0.95000 | 0.94988 |
| 3 | SVM | ML | 0.94175 | 0.94190 |
| 4 | CNN (TextCNN) | DL | 0.93750 | 0.93782 |
| 5 | Logistic Regression | ML | 0.93475 | 0.93476 |
| 6 | XGBoost | ML | 0.92375 | 0.92449 |
| 7 | Random Forest | ML | 0.91625 | 0.91666 |
| 8 | Naive Bayes | ML | 0.90700 | 0.90513 |
| 9 | Gradient Boosting | ML | 0.90600 | 0.90828 |
| 10 | Decision Tree | ML | 0.88850 | 0.88890 |

**Spread: 6.5 accuracy points from best to worst.** Every model clears 88%. BERT's edge over a 1.3M-param
BiLSTM is 0.35 points, and over TF-IDF + SVM it is 1.2 points — for ~108M parameters and GPU fine-tuning.

---

## 11. Results — Priority Classification

4 ordinal classes · 16,000 train / 4,000 test · imbalanced (873 Low / 1,654 Medium / 1,182 High /
291 Urgent). All metrics are **weighted** averages.

### 11.1 Machine Learning models

| Model | Accuracy | F1 (weighted) | Precision (weighted) | Recall (weighted) |
|---|---:|---:|---:|---:|
| **SVM** | **0.58225** | 0.57634 | **0.60335** | **0.58225** |
| Logistic Regression | 0.58075 | **0.57733** | 0.59397 | 0.58075 |
| Naive Bayes | 0.56500 | 0.55446 | 0.59366 | 0.56500 |
| XGBoost | 0.55900 | 0.55092 | 0.57943 | 0.55900 |
| Random Forest | 0.55475 | 0.54964 | 0.56914 | 0.55475 |
| Gradient Boosting | 0.53025 | 0.50370 | 0.57629 | 0.53025 |
| Decision Tree | 0.48650 | 0.48539 | 0.48692 | 0.48650 |

### 11.2 Deep Learning models

| Model | Accuracy | F1 (weighted) | Precision (weighted) | Recall (weighted) |
|---|---:|---:|---:|---:|
| **BERT** | **0.61150** | **0.61153** | **0.61156** | **0.61150** |
| RNN (BiLSTM) | 0.57850 | 0.57831 | 0.57940 | 0.57850 |
| CNN (TextCNN) | 0.56075 | 0.56075 | 0.56155 | 0.56075 |

### 11.3 All 10 models, ranked

| Rank | Model | Family | Accuracy | F1 (weighted) |
|---:|---|---|---:|---:|
| 1 | BERT | DL | 0.61150 | 0.61153 |
| 2 | SVM | ML | 0.58225 | 0.57634 |
| 3 | Logistic Regression | ML | 0.58075 | 0.57733 |
| 4 | RNN (BiLSTM) | DL | 0.57850 | 0.57831 |
| 5 | Naive Bayes | ML | 0.56500 | 0.55446 |
| 6 | CNN (TextCNN) | DL | 0.56075 | 0.56075 |
| 7 | XGBoost | ML | 0.55900 | 0.55092 |
| 8 | Random Forest | ML | 0.55475 | 0.54964 |
| 9 | Gradient Boosting | ML | 0.53025 | 0.50370 |
| 10 | Decision Tree | ML | 0.48650 | 0.48539 |

**Majority-class baseline is 41.4%** (always predict Medium). The best model reaches 61.2% — real signal,
but every model is far below its own category-task score. See §16.

### 11.4 The class-weighting effect on Urgent

The clearest structural difference between the ML and DL priority models. Urgent is 7.3% of the data; the
DL models were class-weighted, the ML models were not.

| Model | Class weights? | Urgent precision | Urgent recall | Urgent F1 |
|---|:--:|---:|---:|---:|
| BERT | ✅ | 0.64 | **0.64** | **0.64** |
| RNN | ✅ | 0.55 | **0.67** | 0.61 |
| CNN | ✅ | 0.52 | **0.59** | 0.55 |
| Logistic Regression | ❌ | 0.79 | 0.38 | 0.52 |
| SVM | ❌ | 0.83 | 0.37 | 0.52 |
| Random Forest | ❌ | 0.79 | 0.43 | 0.56 |
| XGBoost | ❌ | 0.78 | 0.47 | 0.58 |
| Gradient Boosting | ❌ | 0.81 | 0.43 | 0.56 |
| Decision Tree | ❌ | 0.58 | 0.44 | 0.50 |
| Naive Bayes | ❌ | **0.88** | **0.21** | 0.33 |

The unweighted ML models buy high Urgent precision by almost never predicting Urgent — Naive Bayes finds
only 60 of 291 urgent tickets. For a ticket-triage system, missing 79% of urgent tickets is the failure
mode that actually matters, so the weighted DL recall is the more useful behaviour even at lower precision.

---

## 12. Overall Leaderboard

| Model | Family | Category Acc. | Category F1 | Priority Acc. | Priority F1 | Mean Acc. |
|---|---|---:|---:|---:|---:|---:|
| **BERT** | DL | **0.95350** | **0.95314** | **0.61150** | **0.61153** | **0.78250** |
| RNN (BiLSTM) | DL | 0.95000 | 0.94988 | 0.57850 | 0.57831 | 0.76425 |
| SVM | ML | 0.94175 | 0.94190 | 0.58225 | 0.57634 | 0.76200 |
| Logistic Regression | ML | 0.93475 | 0.93476 | 0.58075 | 0.57733 | 0.75775 |
| CNN (TextCNN) | DL | 0.93750 | 0.93782 | 0.56075 | 0.56075 | 0.74913 |
| XGBoost | ML | 0.92375 | 0.92449 | 0.55900 | 0.55092 | 0.74138 |
| Random Forest | ML | 0.91625 | 0.91666 | 0.55475 | 0.54964 | 0.73550 |
| Naive Bayes | ML | 0.90700 | 0.90513 | 0.56500 | 0.55446 | 0.73600 |
| Gradient Boosting | ML | 0.90600 | 0.90828 | 0.53025 | 0.50370 | 0.71813 |
| Decision Tree | ML | 0.88850 | 0.88890 | 0.48650 | 0.48539 | 0.68750 |

**Best model overall: BERT**, winning both tasks. **Best cost/benefit: SVM on TF-IDF** — third overall, no
GPU, seconds of training, within 1.2 points of BERT on category.

---

## 13. Per-Class Reports and Confusion Matrices

Confusion matrix rows = true class, columns = predicted class.

### 13.1 Category — class index order

`LabelEncoder` produces alphabetical order:

| Idx | Class |
|---:|---|
| 0 | Account Suspension |
| 1 | Bug Report |
| 2 | Feature Request |
| 3 | Login Issue |
| 4 | Payment Problem |
| 5 | Performance Issue |
| 6 | Refund Request |
| 7 | Subscription Cancellation |

### 13.2 Priority — class index order

`OrdinalEncoder(categories=[['Low','Medium','High','Urgent']])`:

| Idx | Class | Test support |
|---:|---|---:|
| 0 | Low | 873 |
| 1 | Medium | 1,654 |
| 2 | High | 1,182 |
| 3 | Urgent | 291 |

---

### 13.3 BERT

**Category — accuracy 0.9535**

```
                           precision    recall  f1-score   support

       Account Suspension       0.99      1.00      0.99       500
               Bug Report       0.87      0.83      0.85       500
          Feature Request       0.99      0.99      0.99       500
              Login Issue       0.94      0.96      0.95       500
          Payment Problem       0.94      0.98      0.96       500
        Performance Issue       0.90      0.89      0.89       500
           Refund Request       0.99      0.98      0.99       500
Subscription Cancellation       0.99      1.00      1.00       500

                 accuracy                           0.95      4000
                macro avg       0.95      0.95      0.95      4000
             weighted avg       0.95      0.95      0.95      4000

Confusion Matrix:
[[498   0   0   1   0   0   0   1]
 [  1 415   1  21  24  38   0   0]
 [  0   2 497   0   1   0   0   0]
 [  2   9   0 482   1   5   1   0]
 [  1   2   1   1 489   4   2   0]
 [  0  49   0   5   2 444   0   0]
 [  0   0   1   1   2   3 491   2]
 [  0   0   0   0   0   0   2 498]]
```

**Priority — accuracy 0.6115**

```
              precision    recall  f1-score   support

         Low       0.63      0.62      0.62       873
      Medium       0.60      0.60      0.60      1654
        High       0.61      0.61      0.61      1182
      Urgent       0.64      0.64      0.64       291

    accuracy                           0.61      4000
   macro avg       0.62      0.62      0.62      4000
weighted avg       0.61      0.61      0.61      4000

Confusion Matrix:
[[542 305  25   1]
 [296 998 347  13]
 [ 24 348 720  90]
 [  2   8  95 186]]
```

### 13.4 RNN (BiLSTM)

**Category — accuracy 0.9500**

```
                           precision    recall  f1-score   support

       Account Suspension       0.98      0.98      0.98       500
               Bug Report       0.87      0.83      0.85       500
          Feature Request       0.99      0.98      0.98       500
              Login Issue       0.93      0.95      0.94       500
          Payment Problem       0.95      0.95      0.95       500
        Performance Issue       0.90      0.93      0.91       500
           Refund Request       0.99      0.98      0.98       500
Subscription Cancellation       0.99      0.99      0.99       500

                 accuracy                           0.95      4000
                macro avg       0.95      0.95      0.95      4000
             weighted avg       0.95      0.95      0.95      4000

Confusion Matrix:
[[492   0   0   6   2   0   0   0]
 [  0 416   2  23  13  46   0   0]
 [  1   4 490   1   3   1   0   0]
 [  4  14   0 476   2   4   0   0]
 [  3  13   1   3 475   3   1   1]
 [  0  28   1   2   2 467   0   0]
 [  1   3   2   1   2   0 489   2]
 [  0   0   1   0   1   0   3 495]]
```

**Priority — accuracy 0.5785**

```
              precision    recall  f1-score   support

         Low       0.60      0.59      0.59       873
      Medium       0.59      0.56      0.57      1654
        High       0.56      0.58      0.57      1182
      Urgent       0.55      0.67      0.61       291

    accuracy                           0.58      4000
   macro avg       0.58      0.60      0.59      4000
weighted avg       0.58      0.58      0.58      4000

Confusion Matrix:
[[511 312  46   4]
 [293 919 411  31]
 [ 40 331 690 121]
 [  3   8  86 194]]
```

### 13.5 CNN (TextCNN)

**Category — accuracy 0.9375**

```
                           precision    recall  f1-score   support

       Account Suspension       0.99      0.97      0.98       500
               Bug Report       0.82      0.83      0.82       500
          Feature Request       0.99      0.95      0.97       500
              Login Issue       0.93      0.94      0.94       500
          Payment Problem       0.88      0.96      0.92       500
        Performance Issue       0.92      0.89      0.90       500
           Refund Request       0.99      0.98      0.98       500
Subscription Cancellation       0.98      0.99      0.99       500

                 accuracy                           0.94      4000
                macro avg       0.94      0.94      0.94      4000
             weighted avg       0.94      0.94      0.94      4000

Confusion Matrix:
[[486   2   0   6   6   0   0   0]
 [  1 415   1  18  31  32   1   1]
 [  0  12 477   3   7   1   0   0]
 [  3  19   0 469   5   3   0   1]
 [  0  15   1   1 478   2   1   2]
 [  0  43   1   4   7 443   0   2]
 [  0   3   1   1   4   0 489   2]
 [  0   0   1   0   3   1   2 493]]
```

**Priority — accuracy 0.56075**

```
              precision    recall  f1-score   support

         Low       0.60      0.60      0.60       873
      Medium       0.57      0.54      0.55      1654
        High       0.54      0.56      0.55      1182
      Urgent       0.52      0.59      0.55       291

    accuracy                           0.56      4000
   macro avg       0.55      0.57      0.56      4000
weighted avg       0.56      0.56      0.56      4000

Confusion Matrix:
[[520 306  44   3]
 [316 888 417  33]
 [ 34 360 662 126]
 [  1  17 100 173]]
```

### 13.6 Logistic Regression

**Category — accuracy 0.93475**

```
                           precision    recall  f1-score   support

       Account Suspension       1.00      0.98      0.99       500
               Bug Report       0.81      0.80      0.81       500
          Feature Request       0.96      0.95      0.95       500
              Login Issue       0.91      0.94      0.92       500
          Payment Problem       0.92      0.95      0.94       500
        Performance Issue       0.91      0.90      0.90       500
           Refund Request       0.99      0.97      0.98       500
Subscription Cancellation       0.98      0.99      0.99       500

                 accuracy                           0.93      4000
                macro avg       0.94      0.93      0.93      4000
             weighted avg       0.94      0.93      0.93      4000

Confusion Matrix:
[[488   0   0   8   2   0   1   1]
 [  0 400  13  26  27  34   0   0]
 [  0  12 473   6   2   5   0   2]
 [  2  20   1 471   3   2   0   1]
 [  0  14   3   0 477   4   2   0]
 [  0  39   1   6   3 451   0   0]
 [  0   7   0   1   5   0 483   4]
 [  0   0   1   1   0   1   1 496]]
```

**Priority — accuracy 0.58075**

```
              precision    recall  f1-score   support

         Low       0.64      0.49      0.56       873
      Medium       0.55      0.68      0.61      1654
        High       0.57      0.55      0.56      1182
      Urgent       0.79      0.38      0.52       291

    accuracy                           0.58      4000
   macro avg       0.64      0.53      0.56      4000
weighted avg       0.59      0.58      0.58      4000

Confusion Matrix:
[[ 429  402   41    1]
 [ 199 1131  322    2]
 [  35  469  651   27]
 [   6   37  136  112]]
```

### 13.7 Decision Tree

**Category — accuracy 0.8885**

```
                           precision    recall  f1-score   support

       Account Suspension       0.99      0.97      0.98       500
               Bug Report       0.71      0.72      0.71       500
          Feature Request       0.91      0.87      0.89       500
              Login Issue       0.86      0.90      0.88       500
          Payment Problem       0.87      0.92      0.89       500
        Performance Issue       0.83      0.84      0.83       500
           Refund Request       0.97      0.96      0.97       500
Subscription Cancellation       0.98      0.94      0.96       500

                 accuracy                           0.89      4000
                macro avg       0.89      0.89      0.89      4000
             weighted avg       0.89      0.89      0.89      4000

Confusion Matrix:
[[483   1   0  11   4   1   0   0]
 [  1 358  15  30  35  58   2   1]
 [  1  31 436   8   7  11   2   4]
 [  5  26   5 448   4   9   0   3]
 [  0  19   3   9 460   3   4   2]
 [  0  60   6  10   4 419   0   1]
 [  0   5   3   0   9   1 481   1]
 [  0   2  11   4   6   2   6 469]]
```

**Priority — accuracy 0.4865**

```
              precision    recall  f1-score   support

         Low       0.46      0.42      0.44       873
      Medium       0.51      0.55      0.53      1654
        High       0.46      0.45      0.46      1182
      Urgent       0.58      0.44      0.50       291

    accuracy                           0.49      4000
   macro avg       0.50      0.47      0.48      4000
weighted avg       0.49      0.49      0.49      4000

Confusion Matrix:
[[368 381 122   2]
 [316 913 407  18]
 [108 465 537  72]
 [  9  47 107 128]]
```

### 13.8 Random Forest

**Category — accuracy 0.91625**

```
Confusion Matrix:
[[ ... ]
 [  2  15   1 476   4   1   0   1]
 [  0  15   3   0 476   4   1   1]
 [  0  38   0   5   0 457   0   0]
 [  0   4   1   2   3   0 488   2]
 [  0   1   0   0   0   1   1 497]]
```

*(The Random Forest category confusion matrix is partially truncated in the stored notebook output; the
aggregate metrics in §10.1 are complete and come from `results/ML/category_classification_results.csv`.)*

**Priority — accuracy 0.55475**

```
              precision    recall  f1-score   support

         Low       0.60      0.42      0.50       873
      Medium       0.52      0.69      0.60      1654
        High       0.56      0.49      0.52      1182
      Urgent       0.79      0.43      0.56       291

    accuracy                           0.55      4000
   macro avg       0.62      0.51      0.54      4000
weighted avg       0.57      0.55      0.55      4000

Confusion Matrix:
[[ 370  456   47    0]
 [ 209 1142  299    4]
 [  41  529  582   30]
 [   0   51  115  125]]
```

### 13.9 SVM

**Category — accuracy 0.94175**

```
                           precision    recall  f1-score   support

       Account Suspension       0.99      0.97      0.98       500
               Bug Report       0.82      0.83      0.82       500
          Feature Request       0.98      0.95      0.96       500
              Login Issue       0.92      0.95      0.94       500
          Payment Problem       0.94      0.95      0.94       500
        Performance Issue       0.91      0.91      0.91       500
           Refund Request       0.99      0.98      0.98       500
Subscription Cancellation       0.98      0.99      0.99       500

                 accuracy                           0.94      4000
                macro avg       0.94      0.94      0.94      4000
             weighted avg       0.94      0.94      0.94      4000

Confusion Matrix:
[[487   2   0   7   2   0   1   1]
 [  1 413   7  23  23  32   0   1]
 [  0  14 473   5   1   5   0   2]
 [  2  15   1 476   4   1   0   1]
 [  0  15   3   0 476   4   1   1]
 [  0  38   0   5   0 457   0   0]
 [  0   4   1   2   3   0 488   2]
 [  0   1   0   0   0   1   1 497]]
```

**Priority — accuracy 0.58225**

```
              precision    recall  f1-score   support

         Low       0.67      0.45      0.54       873
      Medium       0.55      0.72      0.62      1654
        High       0.58      0.54      0.56      1182
      Urgent       0.83      0.37      0.52       291

    accuracy                           0.58      4000
   macro avg       0.66      0.52      0.56      4000
weighted avg       0.60      0.58      0.58      4000

Confusion Matrix:
[[ 390  451   31    1]
 [ 161 1195  296    2]
 [  25  502  635   20]
 [   3   40  139  109]]
```

### 13.10 Multinomial Naive Bayes

**Category — accuracy 0.907**

```
                           precision    recall  f1-score   support

       Account Suspension       0.93      0.98      0.96       500
               Bug Report       0.83      0.69      0.75       500
          Feature Request       0.96      0.92      0.94       500
              Login Issue       0.89      0.88      0.88       500
          Payment Problem       0.89      0.95      0.92       500
        Performance Issue       0.86      0.91      0.88       500
           Refund Request       0.94      0.93      0.94       500
Subscription Cancellation       0.94      1.00      0.97       500

                 accuracy                           0.91      4000
                macro avg       0.91      0.91      0.91      4000
             weighted avg       0.91      0.91      0.91      4000

Confusion Matrix:
[[492   0   0   4   0   1   1   2]
 [  4 346  13  37  35  42  17   6]
 [  2  14 460   4   2   9   3   6]
 [ 24  10   5 440   7  11   0   3]
 [  4   4   2   3 475   4   5   3]
 [  0  36   1   5   3 453   1   1]
 [  1   8   0   3  11   3 463  11]
 [  0   0   0   0   0   1   0 499]]
```

**Priority — accuracy 0.565**

```
              precision    recall  f1-score   support

         Low       0.67      0.44      0.53       873
      Medium       0.54      0.70      0.61      1654
        High       0.54      0.55      0.55      1182
      Urgent       0.88      0.21      0.33       291

    accuracy                           0.56      4000
   macro avg       0.66      0.48      0.51      4000
weighted avg       0.59      0.56      0.55      4000

Confusion Matrix:
[[ 384  454   35    0]
 [ 160 1163  331    0]
 [  27  494  653    8]
 [   4   45  182   60]]
```

### 13.11 Gradient Boosting

**Category — accuracy 0.906**

```
                           precision    recall  f1-score   support

       Account Suspension       1.00      0.97      0.98       500
               Bug Report       0.67      0.80      0.73       500
          Feature Request       0.96      0.84      0.90       500
              Login Issue       0.90      0.91      0.90       500
          Payment Problem       0.91      0.93      0.92       500
        Performance Issue       0.90      0.86      0.88       500
           Refund Request       0.98      0.97      0.98       500
Subscription Cancellation       0.99      0.96      0.98       500

                 accuracy                           0.91      4000
                macro avg       0.91      0.91      0.91      4000
             weighted avg       0.91      0.91      0.91      4000

Confusion Matrix:
[[486   8   1   5   0   0   0   0]
 [  0 402   6  24  29  37   1   1]
 [  0  62 420  11   4   3   0   0]
 [  1  34   3 453   4   4   0   1]
 [  0  27   1   0 465   3   3   1]
 [  0  55   2   6   5 431   1   0]
 [  0   7   0   1   4   0 485   3]
 [  0   4   5   4   1   0   4 482]]
```

**Priority — accuracy 0.53025**

```
              precision    recall  f1-score   support

         Low       0.70      0.23      0.35       873
      Medium       0.49      0.81      0.61      1654
        High       0.55      0.39      0.46      1182
      Urgent       0.81      0.43      0.56       291

    accuracy                           0.53      4000
   macro avg       0.64      0.46      0.49      4000
weighted avg       0.58      0.53      0.50      4000

Confusion Matrix:
[[ 202  637   33    1]
 [  70 1333  244    7]
 [  16  684  460   22]
 [   2   65   98  126]]
```

### 13.12 XGBoost

**Category — accuracy 0.92375**

```
                           precision    recall  f1-score   support

       Account Suspension       0.99      0.97      0.98       500
               Bug Report       0.76      0.81      0.79       500
          Feature Request       0.96      0.90      0.93       500
              Login Issue       0.91      0.92      0.91       500
          Payment Problem       0.92      0.95      0.93       500
        Performance Issue       0.90      0.89      0.90       500
           Refund Request       0.99      0.97      0.98       500
Subscription Cancellation       0.98      0.97      0.98       500

                 accuracy                           0.92      4000
                macro avg       0.93      0.92      0.92      4000
             weighted avg       0.93      0.92      0.92      4000

Confusion Matrix:
[[486   2   0   9   2   1   0   0]
 [  0 406   6  26  25  36   0   1]
 [  0  40 449   5   1   4   0   1]
 [  3  22   1 460   6   5   1   2]
 [  0  10   4   1 476   4   4   1]
 [  0  46   2   3   3 446   0   0]
 [  0   5   1   1   5   0 485   3]
 [  0   3   5   2   1   0   2 487]]
```

**Priority — accuracy 0.559**

```
              precision    recall  f1-score   support

         Low       0.64      0.38      0.48       873
      Medium       0.52      0.73      0.61      1654
        High       0.56      0.48      0.52      1182
      Urgent       0.78      0.47      0.58       291

    accuracy                           0.56      4000
   macro avg       0.63      0.51      0.55      4000
weighted avg       0.58      0.56      0.55      4000

Confusion Matrix:
[[ 332  506   34    1]
 [ 147 1202  299    6]
 [  36  548  566   32]
 [   0   51  104  136]]
```

### 13.13 The dominant category error, across every model

**Bug Report ↔ Performance Issue** is the single largest confusion in all ten models, in both directions.

| Model | Bug Report → Performance Issue | Performance Issue → Bug Report |
|---|---:|---:|
| BERT | 38 | 49 |
| RNN | 46 | 28 |
| CNN | 32 | 43 |
| Logistic Regression | 34 | 39 |
| SVM | 32 | 38 |
| XGBoost | 36 | 46 |
| Gradient Boosting | 37 | 55 |
| Naive Bayes | 42 | 36 |
| Decision Tree | 58 | 60 |

Bug Report is the weakest category for every model (F1 0.71–0.85). This is a **label-definition problem,
not a model problem** — "the video player keeps crashing" is genuinely both a bug and a performance issue,
and no amount of model capacity resolves an ambiguity that exists in the annotation itself. BERT, with
108M parameters and full pretraining, still gets Bug Report F1 = 0.85.

---

## 14. Training Loss Logs

### 14.1 BERT — category (10 epochs, batch 16, lr 2e-5, AdamW)

| Epoch | Avg. Loss |
|---:|---:|
| 1 | 0.3768 |
| 2 | 0.1209 |
| 3 | 0.0846 |
| 4 | 0.0648 |
| 5 | 0.0541 |
| 6 | 0.0387 |
| 7 | 0.0311 |
| 8 | 0.0334 |
| 9 | 0.0248 |
| 10 | 0.0166 |

### 14.2 BERT — priority (25 epochs, batch 16, lr 2e-5, AdamW, weighted CE)

| Epoch | Loss | Epoch | Loss | Epoch | Loss |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.9801 | 10 | 0.1371 | 19 | 0.0695 |
| 2 | 0.7406 | 11 | 0.1217 | 20 | 0.0583 |
| 3 | 0.5952 | 12 | 0.1095 | 21 | 0.0556 |
| 4 | 0.4581 | 13 | 0.0967 | 22 | 0.0531 |
| 5 | 0.3589 | 14 | 0.0891 | 23 | 0.0522 |
| 6 | 0.2770 | 15 | 0.0875 | 24 | 0.0484 |
| 7 | 0.2223 | 16 | 0.0799 | 25 | 0.0455 |
| 8 | 0.1776 | 17 | 0.0678 | | |
| 9 | 0.1553 | 18 | 0.0709 | | |

Training loss falls to 0.046 while test accuracy is 0.61 — **severe overfitting**, unsurprising with no
validation split, no early stopping, no LR schedule and 25 epochs on a task with a noisy label.

### 14.3 RNN — category (10 epochs, batch 32, lr 1e-3, Adam, clip 5.0)

| Epoch | Avg. Loss | Throughput |
|---:|---:|---|
| 1 | 0.4875 | 500 batches @ ~64 batch/s |
| 2 | 0.1978 | ~74 batch/s |
| 3 | 0.1474 | ~74 batch/s |
| 4 | 0.1197 | ~74 batch/s |
| 5 | 0.0966 | ~74 batch/s |
| 6 | 0.0839 | ~76 batch/s |
| 7 | 0.0706 | ~75 batch/s |
| 8 | 0.0623 | ~75 batch/s |
| 9 | 0.0557 | ~75 batch/s |
| 10 | 0.0435 | ~75 batch/s |

Roughly 7 seconds per epoch, ~70 s total on a Kaggle GPU. Evaluation: 125 batches at ~111 batch/s.

### 14.4 RNN — priority (25 epochs, batch 32, lr 1e-3, Adam, clip 5.0, weighted CE)

| Epoch | Loss | Epoch | Loss | Epoch | Loss |
|---:|---:|---:|---:|---:|---:|
| 1 | 1.0836 | 10 | 0.4723 | 19 | 0.2810 |
| 2 | 0.8969 | 11 | 0.4442 | 20 | 0.2687 |
| 3 | 0.8086 | 12 | 0.4120 | 21 | 0.2655 |
| 4 | 0.7418 | 13 | 0.3908 | 22 | 0.2602 |
| 5 | 0.6794 | 14 | 0.3721 | 23 | 0.2381 |
| 6 | 0.6248 | 15 | 0.3488 | 24 | 0.2285 |
| 7 | 0.5833 | 16 | 0.3311 | 25 | 0.2233 |
| 8 | 0.5397 | 17 | 0.3160 | | |
| 9 | 0.5006 | 18 | 0.2956 | | |

### 14.5 CNN

The CNN notebook was executed but its cell outputs were **cleared before saving**, so the per-epoch loss
log is not preserved in the `.ipynb`. The final metrics survive in
`results/DL/cnn/evaluation_results_cnn.csv` and the trained weights in `models/cnn/`. Re-running the
notebook regenerates the log.

---

## 15. Comparison with the Paper

### 15.1 Setup differences

| Aspect | Paper | This work |
|---|---|---|
| Domain | Financial complaints (banking) | LMS / EdTech support tickets |
| Dataset size | 78,313 | 20,000 |
| Data origin | Real complaints (Kaggle, CFPB-style) | Gemini-generated synthetic |
| Category labels | **Derived** via NMF topic modeling + manual mapping of top-10 words → 5 departments | **Pre-existing gold labels**, 8 classes |
| Priority labels | **Derived** via urgent-keyword matching + spaCy/negspacy negation detection | **Pre-existing gold labels**, 4 ordinal classes |
| Priority task shape | **Binary** (urgent / not urgent) | **4-class** (Low / Medium / High / Urgent) |
| Categories | 5 (Retail Banking Ops, Credit Card Mgmt, Payment & Billing, Dispute Reporting, Mortgages/Loans) | 8 (see §2) |
| BERT variant | not specified | `bert-base-cased` |
| Hyperparameters | not reported | fully documented in §9 |
| Split / CV | not reported | 80/20 stratified, `random_state=42` |
| NMF topic modeling | ✅ core to the method | ❌ **not reproduced** — our data is already labelled |
| Urgency-keyword extraction | ✅ core to the method | ❌ **not reproduced** — our data is already labelled |

Because our dataset ships with human-meaningful gold labels, the paper's two *label-generation* stages
(NMF and keyword-based urgency) are unnecessary — we evaluate the *classification* half of the pipeline
directly against ground truth, which is the stricter test.

### 15.2 Category classification — paper vs ours

| Model | Paper Acc. | Ours Acc. | Δ |
|---|---:|---:|---:|
| Logistic Regression | 0.9199 | 0.93475 | **+1.5** |
| SVM | 0.9151 | 0.94175 | **+2.7** |
| XGBoost | 0.9117 | 0.92375 | **+1.2** |
| Gradient Boosting | 0.9045 | 0.90600 | +0.2 |
| Random Forest | 0.8113 | 0.91625 | **+10.5** |
| Decision Tree | 0.7844 | 0.88850 | **+10.4** |
| Multinomial Naive Bayes | 0.7187 | 0.90700 | **+18.8** |
| BERT | 0.81 | 0.95350 | **+14.4** |
| RNN | 0.80 | 0.95000 | **+15.0** |
| CNN | 0.80 | 0.93750 | **+13.8** |

**Every model beats the paper on categorization, several by double digits.** The most plausible reason is
label quality, not modelling skill: the paper's categories were induced by NMF and hand-mapped from
top-10 topic words, which produces noisy, overlapping targets. Ours are clean, balanced gold labels on
synthetic text whose category is baked into how each ticket was generated. Our numbers should therefore be
read as an **upper bound**, not as evidence our pipeline is better than theirs.

Note also that the paper's ML/DL ordering is unstable: it reports BERT at 0.81 — *below* six of its own
seven classical models. In our run the ordering is the expected one (BERT > RNN > SVM > CNN > LR > …).

### 15.3 Priority classification — paper vs ours

⚠️ **These numbers are not directly comparable.** The paper's priority task is **binary** (urgent /
not urgent); ours is **4-class ordinal**. Random-guess baselines differ (50% vs 25%), and majority-class
baselines differ (paper's unknown vs our 41.4%).

| Model | Paper Acc. (binary) | Ours Acc. (4-class) | Δ |
|---|---:|---:|---:|
| Decision Tree | 0.9996 | 0.48650 | −51.3 |
| XGBoost | 0.9973 | 0.55900 | −43.8 |
| Gradient Boosting | 0.9884 | 0.53025 | −45.8 |
| SVM | 0.9468 | 0.58225 | −36.5 |
| Random Forest | 0.9003 | 0.55475 | −34.6 |
| Logistic Regression | 0.9011 | 0.58075 | −32.0 |
| Multinomial Naive Bayes | 0.8939 | 0.56500 | −32.9 |
| BERT | 0.92 | 0.61150 | −30.9 |
| RNN | 0.92 | 0.57850 | −34.2 |
| CNN | 0.91 | 0.56075 | −34.9 |

The paper's Decision Tree at **99.96%** and XGBoost at **99.73%** (Table 4: precision 1.00, recall 1.00,
F1 1.00) are the tell. Those labels were produced by **keyword matching on the same text the models then
read**. A decision tree given TF-IDF features simply relearns the keyword rule — it is not predicting
urgency, it is reverse-engineering the labelling script. Near-perfect scores on a text task are a
target-leakage signature, not a performance result.

Our 4-class priority labels carry no such shortcut, and our ~49–61% range reflects a genuinely hard
problem. The two sets of numbers are measuring different things.

---

## 16. Observations

**1. Category classification is solved on this dataset.** Ten out of ten models clear 88%; the top four
sit within 1.6 points of each other. The remaining error is concentrated in one genuinely ambiguous class
pair (Bug Report ↔ Performance Issue), which is a labelling-taxonomy issue rather than a modelling one.

**2. Priority classification is not solved, and probably cannot be from text alone.** Best accuracy is
61.2% against a 41.4% majority baseline. Every confusion matrix shows errors clustered on *adjacent*
severity levels (Low↔Medium, Medium↔High), with almost no Low↔Urgent confusion — e.g. BERT misroutes only
1 Low as Urgent and 2 Urgent as Low out of 4,000. The models learn the ordinal structure correctly; they
just cannot resolve neighbouring boundaries. That is what you would expect when a human assigning
Medium vs High is using context the ticket text does not contain (SLA tier, customer value, current
backlog). The dataset's own `issue_complexity_score` and `sentiment` columns, currently unused, are the
obvious next features to try.

**3. Pretraining pays off exactly where the task is hard.** BERT's margin over the best classical model is
+1.2 points on category (easy task, everything works) but **+2.9 points on priority** (hard task). And
BERT's advantage over the best classical model on priority is more than double its advantage on category.
When the signal is subtle, contextual embeddings help; when it is obvious, TF-IDF is enough.

**4. A 1.3M-parameter BiLSTM matches a 108M-parameter transformer on categorization** (0.9500 vs 0.9535)
after ~70 seconds of training. If category routing is the deliverable, BERT is not worth the cost.

**5. Class weighting is what makes the priority models usable.** The weighted DL models find 59–67% of
Urgent tickets; the unweighted ML models find 21–47%. For triage, Urgent recall is the metric that matters,
and it is a configuration choice — not an architecture choice — that determines it.

**6. Both custom vocabularies came in at ~2,080 tokens against a 20,000 cap.** The ticket language is
extremely narrow. This is characteristic of synthetic data generated from templates and is worth
remembering when interpreting how well these numbers will transfer to real tickets.

**7. All models overfit the priority task.** BERT reaches 0.046 training loss at 61% test accuracy; the
RNN reaches 0.223 at 58%. With no validation split and no early stopping this was inevitable. See §18.

---

## 17. Reproduction

### Requirements

```
pandas
numpy
scikit-learn
xgboost
nltk
torch
transformers
tqdm
```

NLTK data used: `wordnet`, `omw-1.4` (the DL notebooks download these automatically with
`nltk.download(..., quiet=True)` and degrade gracefully to no-lemmatization if unavailable).

### Environment

| | |
|---|---|
| ML notebook | Local, Python 3.14, CPU |
| DL notebooks | Kaggle, CUDA GPU |
| BERT checkpoint | `google-bert/bert-base-cased` from Hugging Face Hub |

> The BERT notebook logs `Warning: You are sending unauthenticated requests to the HF Hub.` — harmless,
> but set `HF_TOKEN` for faster downloads.

### Running

```bash
# 1. Classical ML (CPU, minutes)
jupyter nbconvert --execute --to notebook --inplace Research_paper_evaluation_ML.ipynb

# 2. Deep learning (GPU strongly recommended)
jupyter nbconvert --execute --to notebook --inplace Research_paper_evaluation_RNN.ipynb
jupyter nbconvert --execute --to notebook --inplace Research_paper_evaluation_CNN.ipynb
jupyter nbconvert --execute --to notebook --inplace Research_paper_evaluation_Bert.ipynb
```

### Path notes before re-running

* The three DL notebooks read from the Kaggle path
  `/kaggle/input/datasets/sinethwickramaratna/curated-lms-tickets/curated_lms_tickets.csv`.
  Change `PATH` to `./data/curated_lms_tickets.csv` to run locally.
* The ML notebook writes to `./results/category_classification_results.csv` and
  `./results/priority_classification_results.csv`, but the committed files live in `results/ML/`. They
  were moved after the run — re-running overwrites at the notebook's path, not the committed one.
* The DL notebooks write `evaluation_results_{cnn,rnn,bert}.csv` to the **working directory**; the
  committed copies were moved into `results/DL/…` and `results/Bert.zip` afterwards.
* `results/Bert.zip` must be extracted before the BERT models can be loaded.

### Determinism

`random_state=42` on all splits and all sklearn/XGBoost models; `SEED = 42` (`torch.manual_seed` +
`np.random.seed`) in the RNN and CNN notebooks. **The BERT notebook does not set a seed**, so its numbers
are the least reproducible of the four — expect ±0.5 points on re-run.

### Loading a saved model

```python
# RNN / CNN
import json, torch
vocab = json.load(open('models/rnn/category_classification/rnn_category_vocab.json'))
model = RNNClassifier(vocab_size=len(vocab), num_labels=8)
model.load_state_dict(torch.load('models/rnn/category_classification/rnn_category_model.pt'))
model.eval()

# BERT (after extracting results/Bert.zip)
from transformers import BertTokenizer, BertForSequenceClassification
tok   = BertTokenizer.from_pretrained('models/bert/category_classification/bert_category_tokenizer')
model = BertForSequenceClassification.from_pretrained('models/bert/category_classification/bert_category_model')
```

The RNN and CNN checkpoints are `state_dict`s, so the corresponding model class from the notebook must be
defined before loading, and the vocabulary JSON must be loaded to get the right `vocab_size`.

---

## 18. Known Deviations from the Paper

Recorded honestly so the comparison in §15 can be read correctly.

| # | Deviation | Impact |
|---|---|---|
| 1 | **NMF topic modeling not reproduced.** Our categories are gold labels, not NMF-derived. | Removes the paper's largest source of label noise. A major reason our category scores are higher. |
| 2 | **Urgency-keyword + negspacy pipeline not reproduced.** Our priorities are gold labels, not keyword-derived. | Removes the target leakage that produces the paper's 99.96% Decision Tree. Our priority numbers are lower and more honest. |
| 3 | **Priority is 4-class, not binary.** | Makes §15.3 a non-comparison. Flagged there. |
| 4 | **TF-IDF fitted on the full corpus, before the split.** | Mild optimistic bias in all seven ML results. The DL vocabularies do not have this issue. |
| 5 | **BERT receives raw text; the paper's Section 3.2 preprocessing is skipped for it.** | Deliberate — see §5.3. Helps BERT relative to a strict reading of the paper. |
| 6 | **`nn.LSTM` used where the paper says "RNN".** | Standard practice; a vanilla `nn.RNN` would score lower. `RNN_CELL` is exposed for the strict comparison. |
| 7 | **No validation split, no early stopping, no LR schedule.** Epoch counts are fixed at 10/25. | All models overfit, visibly so on priority. The paper does not report a validation protocol either, so this matches it — but it is a real weakness of both. |
| 8 | **`stop_words='english'` and `min_df=5` chosen by us.** The paper does not report its TF-IDF settings. | Documented divergence; results are sensitive to it. |
| 9 | **BERT notebook sets no random seed.** | Its results are the least reproducible of the four. |
| 10 | **Synthetic (Gemini-generated) data, 20k rows vs the paper's 78k real complaints.** | Narrow ~2,080-token vocabulary. Scores are likely optimistic relative to real ticket text. |
| 11 | **CNN cell outputs cleared before saving.** | Per-epoch loss log lost; final metrics and weights are intact. |
| 12 | **Class weights computed on the full label vector, not the training split.** | Negligible under stratified splitting. |
