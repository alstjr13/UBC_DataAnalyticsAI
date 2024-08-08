# TODO
# Make 5 figures of epoch = 1,2,3 and test of the following criterias:
# 1. Accuracy
# 2. Precision
# 3. Recall
# 4. F1 Score
# 5. AUC

# TODO
# sample_6k_reviews_for_RA_updated.csv -- Regex - incentivized sentence "filtering"
# Training : Test --> 80 : 20
# Training -- K-cross validation: k=5
# validation result --> plot --> matplotlib

# Training loss   -->  PLOT
# Validation loss -->  PLOT
# for epoch1, epoch2, epoch3, test (as x-axis)
# for accuracy, precision, recall, f1 score, auc (as y-axis)

# ex. 100, 200개로 돌렸을때 잘 돌아가는지 확인  --> 잘 돌아가면 6000 --> ~~~


import os
os.environ['PYTORCH_MPS_HIGH_WATERMARK_RATIO'] = '0.0'

#TODO
from sklearn.model_selection import cross_val_score

import pandas as pd
from torch.utils.data import Dataset
from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments
import torch
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score, precision_recall_fscore_support, precision_score, \
    recall_score, f1_score
import matplotlib.pyplot as plt


# Load sample data set with incentivized reviews as pd.DataFrame
df = pd.read_csv('../data/cleaned_reviews_with_labels.csv')

# Randomly select 100 incentivized reviews (Labelled with 1)
#                 100 not incentivized reviews (Labelled with 0)
notIncentivized = df[df["incentivized_999"] == 0].sample(n=100, random_state=42)
incentivized = df[df["incentivized_999"] == 1].sample(n=100, random_state=42)


hasNaText = incentivized['cleanedReviewText'].isna().any()
hasNaLabel = incentivized['incentivized_999'].isna().any()
print(hasNaText)
print(hasNaLabel)

hasNaText = notIncentivized['cleanedReviewText'].isna().any()
hasNaLabel = notIncentivized['incentivized_999'].isna().any()
print(hasNaText)
print(hasNaLabel)

newdf = pd.concat([notIncentivized, incentivized])
newdf = newdf.sample(frac=1, random_state=42).reset_index(drop=True)

#print(newdf)
# Split the data
X = newdf["cleanedReviewText"]
y = newdf["incentivized_999"]

# Default = 8:2
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)


print(X_train.shape)  # --> k = 5, 또 나눠서
print(X_test.shape)
print(y_train.shape)
print(y_test.shape)

# Create a ReviewDataset with inputs:
# 1. texts:  reviews of the users (either incentivized or unincentivized - labelled with 0 or 1)
# 2. labels: corresponding label value --> 0 or 1
# 3. tokenizer: BERT-Large Tokenizer
# 4. max_length: set default to 512
class ReviewsDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
    def __len__(self):
        return len(self.texts)
    def __getitem__(self, idx):
        text = self.texts[idx]
        label = self.labels[idx]
        encoding = self.tokenizer.encode_plus(
            text,
            max_length=self.max_length,
            return_token_type_ids=False,
            padding='max_length',
            truncation=True,
            return_attention_mask=True,
            return_tensors='pt',
        )
        return {
            'text': text,
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }

# Initialize BERT-large Tokenizer with maxlength = 512
tokenizer = BertTokenizer.from_pretrained('bert-large-cased')
max_length = 512

# Datasets to feed into BERT-Large: ReviewDataset(Dataset) -->
train_dataset = ReviewsDataset(X_train.tolist(), y_train.tolist(), tokenizer, max_length)
test_dataset = ReviewsDataset(X_test.tolist(), y_test.tolist(), tokenizer, max_length)

# Initialize BERT-large
model = BertForSequenceClassification.from_pretrained('bert-large-cased', num_labels=2)

#optimizer: Default --> AdamW
training_args = TrainingArguments(
    output_dir='./results/bert',
    overwrite_output_dir= True,
    do_train= True,
    do_eval= True,

    # Alter
    adam_beta1=0.9,
    adam_beta2=0.999,
    learning_rate=3e-5,
    num_train_epochs=3,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    warmup_steps=500,
    weight_decay=0.01,
    logging_dir='./logs/bert',
    logging_steps=10,
    eval_strategy="epoch"
)
def compute_metrics(p):
    pred = p.predictions.argmax(-1)
    clf = LogisticRegression(solver="liblinear", random_state=0).fit(X, y)

    accuracy = accuracy_score(p.label_ids, pred, normalize=True)
    precision = precision_score(p.label_ids, pred, average='weighted')
    recall = recall_score(p.label_ids, pred, average='weighted')
    f1 = f1_score(p.label_ids, pred, average='weighted')
    roc_auc = roc_auc_score(p.label_ids, clf.decision_function(X))
    #precision, recall, f1, _ = precision_recall_fscore_support(p.label_ids, pred, average='binary')
    #accuracy = accuracy_score(p.label_ids, pred)
    #roc_auc = roc_auc_score(p.label_ids, p.predictions[:, 1])
    return {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'roc_auc': roc_auc
    }

# Initialize the Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=test_dataset,
    compute_metrics=compute_metrics
)

# TODO:
# k-cross validation

# Initialize empty list to store the metrics for each epoch
metrics_per_epoch = []

# Train, evaluate, append
for epoch in range(training_args.num_train_epochs):
    print("Training the trainer")
    trainer.train()
    print("Evaluating the trainer")
    eval_metrics = trainer.evaluate()
    print("Storing the output into metrics_per_epoch")
    metrics_per_epoch.append(eval_metrics)
    print(f"Epoch {epoch+1} - {eval_metrics}")

# Final evaluation on the test set
print("Evaluating the model on test set")
test_metrics = trainer.evaluate(eval_dataset=test_dataset)
metrics_per_epoch.append(test_metrics)
print(f"Test: {test_metrics}")


# Plot the results
def plot_metrics(metrics_per_epoch):
    epochs = list(range(1, len(metrics_per_epoch)))
    epochs.append('Test')

    accuracy = [metrics['eval_accuracy'] for metrics in metrics_per_epoch]
    precision = [metrics['eval_precision'] for metrics in metrics_per_epoch]
    recall = [metrics['eval_recall'] for metrics in metrics_per_epoch]
    f1 = [metrics['eval_f1'] for metrics in metrics_per_epoch]
    auc = [metrics['eval_roc_auc'] for metrics in metrics_per_epoch]

    x_axis = ["epoch1", "epoch2", "epoch3", "test"]

    plt.figure(figsize=(20, 10))

    plt.subplot(4, 2, 1)
    plt.plot(epochs, accuracy)

    plt.title('Accuracy')

    plt.subplot(4, 2, 2)
    plt.plot(epochs, precision)
    plt.title('Precision')

    plt.subplot(4, 2, 3)
    plt.plot(epochs, recall)
    plt.title('Recall')

    plt.subplot(4, 2, 4)
    plt.plot(epochs, f1)
    plt.title('F1 Score')

    plt.subplot(4, 2, 5)
    plt.plot(epochs, auc)
    plt.title('AUC')

    plt.tight_layout()
    plt.show()

plot_metrics(metrics_per_epoch)
