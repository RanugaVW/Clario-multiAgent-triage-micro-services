import os
import json
import pandas as pd
from sklearn.metrics import classification_report, accuracy_score, precision_recall_fscore_support
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import torch

def load_model():
    base_model_id = "unsloth/Llama-3.2-3B-Instruct-bnb-4bit"

    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_id)
    
    print("Loading base model in 4-bit (Zero-Shot, NO LoRA adapter)...")
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        device_map="auto"
    )
    base_model.eval()
    
    return base_model, tokenizer

def extract_json_from_text(text):
    try:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            json_str = text[start:end+1]
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    return None

def evaluate():
    model, tokenizer = load_model()
    
    test_csv = "/home/ranuga-weerasekara/Desktop/clario/ml_finetuning/data/curated_synthetic_lms/test_split.csv"
    print(f"Loading test data from {test_csv}...")
    df = pd.read_csv(test_csv)
    
    y_true_category = []
    y_pred_category = []
    
    y_true_priority = []
    y_pred_priority = []
    
    y_true_sentiment = []
    y_pred_sentiment = []
    
    system_prompt = "You are an expert IT Support Triage Analyst. Your task is to analyze a customer support ticket based on the 'Product' and 'Issue Description', and classify it.\n\nBefore providing the final labels, you must provide a step-by-step logical reasoning process (Chain-of-Thought). Your output must be in valid JSON with keys 'category', 'priority', 'sentiment'."
    
    print(f"Evaluating {len(df)} samples...")
    for index, row in df.iterrows():
        product = row['product']
        issue = row['issue_description']
        
        user_prompt = f"Product: {product}\nIssue Description: {issue}"
        text = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{user_prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.1,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )
            
        generated_text = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
        
        parsed_json = extract_json_from_text(generated_text)
        
        if parsed_json:
            # Sometime keys are inside 'labels', sometimes they are at the top level
            labels = parsed_json.get("labels", parsed_json)
            
            y_pred_category.append(labels.get("category", "UNKNOWN"))
            y_pred_priority.append(labels.get("priority", "UNKNOWN"))
            y_pred_sentiment.append(labels.get("sentiment", "UNKNOWN"))
        else:
            y_pred_category.append("PARSE_ERROR")
            y_pred_priority.append("PARSE_ERROR")
            y_pred_sentiment.append("PARSE_ERROR")
            
        y_true_category.append(row['category'])
        y_true_priority.append(row['priority'])
        y_true_sentiment.append(row['sentiment'])
        
        if (index + 1) % 10 == 0:
            print(f"Processed {index + 1}/{len(df)}")
            
        # periodically save intermediate results so we have something before it finishes
        if (index + 1) % 500 == 0:
            with open("/home/ranuga-weerasekara/Desktop/clario/ml_finetuning/src/evaluation/zero_shot_intermediate.json", "w") as f:
                json.dump({
                    "processed": index + 1,
                    "y_pred_category": y_pred_category,
                    "y_pred_priority": y_pred_priority,
                    "y_pred_sentiment": y_pred_sentiment
                }, f)

    # Function to print reports
    def get_report_str(target_name, y_true, y_pred):
        report = "\n" + "="*80 + "\n"
        report += f"*** {target_name.upper()}\n"
        report += "="*80 + "\n"
        
        acc = accuracy_score(y_true, y_pred)
        precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='macro', zero_division=0)
        
        report += f"Accuracy: {acc:.4f}\n"
        report += f"Macro F1: {f1:.4f}\n"
        report += f"Macro Precision: {precision:.4f}\n"
        report += f"Macro Recall: {recall:.4f}\n\n"
        
        report += classification_report(y_true, y_pred, zero_division=0) + "\n"
        return report

    full_report = get_report_str("CATEGORY", y_true_category, y_pred_category)
    full_report += get_report_str("PRIORITY", y_true_priority, y_pred_priority)
    full_report += get_report_str("SENTIMENT", y_true_sentiment, y_pred_sentiment)
    
    print(full_report)
    with open("/home/ranuga-weerasekara/Desktop/clario/ml_finetuning/src/evaluation/zero_shot_results.txt", "w") as f:
        f.write(full_report)

if __name__ == "__main__":
    evaluate()
