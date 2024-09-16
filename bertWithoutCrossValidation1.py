import os
import warnings
import numpy as np
import pandas as pd
from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, confusion_matrix, \
    precision_score, recall_score, f1_score
import torch
from torch.nn import CrossEntropyLoss
from torch.utils.data import Dataset
import matplotlib.pyplot as plt
import seaborn as sns

import utils

# Enable memory use
os.environ['PYTORCH_MPS_HIGH_WATERMARK_RATIO'] = '0.0'
warnings.filterwarnings('ignore')

# ---------------------------------------PRE-PROCESSING-DATA---------------------------------------------------------

# Load dataset:
# reviewText                     (column 0): reviews in text... including incentivized and non-incentivized reviews
# incentivized_999               (column 1): - 0 : non-incentivized reviews
#                                            - 1 : incentivized reviews
# incent_bert_highest_score_sent (column 2): sentence with highest probability of being "disclosure sentence" in reviewText
filePath = "../data/updated_review_sample_for_RA.csv"
df = pd.read_csv(filePath)

# Delete any row that has NaN value
df = df.dropna(subset=["reviewText"])

# Take random samples from the dataset
notIncentivized = df[df['incentivized_999'] == 0].sample(n=300, random_state=42)
incentivized =df[df['incentivized_999'] == 1].sample(n=300, random_state=42)

# Combine random samples
df = pd.concat([notIncentivized, incentivized])

# Drop unnecessary column
df = df.drop(['incent_bert_highest_score_sent'], axis=1)

# Reset index and shuffle sample
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

df = df.rename(columns={"reviewText" : "texts", "incentivized_999": "labels"})
X = df["texts"]
y = df["labels"]

# Split data to Train, Validation and Test (0.72 : 0.18 : 0.1 Ratio)
train_texts, train_labels, validation_texts, validation_labels, test_texts, test_labels = utils.data_split(X, y)

# Print number of labels in splited data
print(f"Training Set Distribution: \n {pd.Series(train_labels).value_counts()}")
print(f"Validation Set Distribution: \n {pd.Series(validation_labels).value_counts()}")
print(f"Test Set Distribution: \n {pd.Series(test_labels).value_counts()}")

# Initialize BERT Large Model and BERT Large Tokenizer
model = BertForSequenceClassification.from_pretrained("bert-large-cased", num_labels=2)
tokenizer = BertTokenizer.from_pretrained('bert-large-cased')
max_length = 512

# Create ReviewDataset(Dataset), with encodings
trainDataset = utils.ReviewDataset(train_texts.tolist(), train_labels.tolist(), tokenizer=tokenizer, max_length=max_length)
validationDataset = utils.ReviewDataset(validation_texts.tolist(), validation_labels.tolist(), tokenizer=tokenizer, max_length=max_length)
testDataset = utils.ReviewDataset(test_texts.tolist(), test_labels.tolist(), tokenizer=tokenizer, max_length=max_length)

# --------------------------------------------FINE-TUNING---------------------------------------------------------------
training_args = TrainingArguments(
    output_dir='../results/bert/bertWithoutCrossValidation',
    overwrite_output_dir=True,
    do_train=True,
    do_eval=True,

    # Alter
    learning_rate=3e-5,
    per_device_train_batch_size=32,
    per_device_eval_batch_size=16,
    adam_beta1=0.9,
    adam_beta2=0.99,

    # Fixed
    logging_dir='../logs/bert/bertWithoutCrossValidation',
    num_train_epochs=4,
    eval_strategy='epoch',
    save_strategy='epoch',
    warmup_steps=500,
    weight_decay=0.01,
    logging_steps=5,
    load_best_model_at_end=True,
)

def compute_metrics(p):
    """
    Computes the accuracy, precision, recall, F1, ROC_AUC of the input predictions
    :param p: predictions
    :return: accuracy, precision, recall, f1, roc_auc
    """
    labels = p.label_ids
    preds = p.predictions.argmax(-1)

    # For DEBUGGING
    print(f"Labels: {labels} \n")
    print(f"Predictions: {preds}")

    accuracy = accuracy_score(labels, preds)
    precision = precision_score(labels, preds)
    recall = recall_score(labels, preds)
    f1 = f1_score(labels, preds)
    roc_auc = roc_auc_score(labels, preds)

    tn, fp, fn, tp = confusion_matrix(labels, preds).ravel()

    # For DEBUGGING
    print(f"Accuracy: {accuracy}, \n"
          f"Precision: {precision}, \n"
          f"Recall: {recall}, \n"
          f"F1 Score: {f1}, \n"
          f"AUC: {roc_auc} \n"
          f"True Positives: {tp} \n"
          f"False Positives: {fp} \n"
          f"True Negatives: {tn} \n"
          f"False Negatives: {fn}")
    return {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'roc_auc': roc_auc
    }

# Initialize Trainer to train the pre-trained model
trainer = Trainer(
    model=model,                        # BertForSequenceClassification.from_pretrained('bert-large-cased', num_labels=2)
    args=training_args,
    train_dataset=trainDataset,
    eval_dataset=testDataset,
    tokenizer=tokenizer,                # BertTokenizer.from_pretrained('bert-large-cased')
    compute_metrics=compute_metrics,
)



