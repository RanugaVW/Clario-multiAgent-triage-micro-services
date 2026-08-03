import os
import json
import re
import pandas as pd
from sklearn.metrics import classification_report, accuracy_score, precision_recall_fscore_support
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import torch
from peft import PeftModel

def load_model():
    base_model_id = "meta-llama/Llama-3.2-3B-Instruct"
    adapter_dir = r"C:\Users\ranug\Clario\clario\ml_finetuning\models\llama3_2_qlora_triage"

    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_id)
    
    print("Loading base model in 4-bit...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16
    )
    
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        quantization_config=bnb_config,
        device_map="auto"
    )

    print("Loading LoRA adapters...")
    model = PeftModel.from_pretrained(base_model, adapter_dir)
    model.eval()
    
    return model, tokenizer

def extract_json_from_text(text):
    # Sometimes the model might add extra text before or after the JSON.
    # This attempts to extract just the JSON part.
    try:
        # Find the first { and the last }
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
    
    test_csv = r"C:\Users\ranug\Clario\clario\ml_finetuning\data\curated_synthetic_lms\test_split.csv"
    print(f"Loading test data from {test_csv}...")
    df = pd.read_csv(test_csv)
    
    y_true_category = []
    y_pred_category = []
    
    y_true_priority = []
    y_pred_priority = []
    
    y_true_sentiment = []
    y_pred_sentiment = []
    
    system_prompt = "You are an expert IT Support Triage Analyst. Your task is to analyze a customer support ticket based on the 'Product' and 'Issue Description', and classify it.\n\nBefore providing the final labels, you must provide a step-by-step logical reasoning process (Chain-of-Thought)."
    
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
        
        if parsed_json and "labels" in parsed_json:
            labels = parsed_json["labels"]
            
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

    # Function to print reports just like the screenshots
    def print_report(target_name, y_true, y_pred):
        print("\n" + "="*80)
        print(f"*** {target_name.upper()}")
        print("="*80)
        
        acc = accuracy_score(y_true, y_pred)
        precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='macro', zero_division=0)
        
        print(f"Accuracy: {acc:.4f}")
        print(f"Macro F1: {f1:.4f}")
        print(f"Macro Precision: {precision:.4f}")
        print(f"Macro Recall: {recall:.4f}\n")
        
        print(classification_report(y_true, y_pred, zero_division=0))

    print_report("CATEGORY", y_true_category, y_pred_category)
    print_report("PRIORITY", y_true_priority, y_pred_priority)
    print_report("SENTIMENT", y_true_sentiment, y_pred_sentiment)

if __name__ == "__main__":
    evaluate()
