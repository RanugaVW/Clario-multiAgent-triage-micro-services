import os
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

# Base model ID
model_id = "meta-llama/Llama-3.2-3B-Instruct"

# Output directory for the LoRA adapters
output_dir = r"C:\Users\ranug\Clario\clario\ml_finetuning\models\llama3_2_qlora_triage"
data_path = r"C:\Users\ranug\Clario\clario\ml_finetuning\data\curated_synthetic_lms\distilled_train.jsonl"

def format_instruction(example):
    # Llama 3 Chat Template formatting
    # The teacher (Gemini) generated the reasoning and labels. Llama needs to learn to predict this.
    
    system_prompt = "You are an expert IT Support Triage Analyst. Your task is to analyze a customer support ticket based on the 'Product' and 'Issue Description', and classify it.\n\nBefore providing the final labels, you must provide a step-by-step logical reasoning process (Chain-of-Thought)."
    
    user_prompt = f"Product: {example['input_product']}\nIssue Description: {example['input_issue_description']}"
    
    # Reconstruct the JSON string that Gemini produced
    import json
    assistant_response = json.dumps({
        "reasoning": example["reasoning"],
        "labels": example["labels"]
    }, indent=2)
    
    # Format according to Llama-3 instruction format
    text = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{user_prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n{assistant_response}<|eot_id|>"
    
    return {"text": text}

def main():
    print(f"Loading dataset from {data_path}...")
    dataset = load_dataset("json", data_files=data_path, split="train")
    
    # Apply chat template
    print("Formatting dataset...")
    dataset = dataset.map(format_instruction)

    print("Configuring QLoRA...")
    # 4-bit Quantization Config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16
    )

    print(f"Loading model {model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto"
    )
    
    # Prepare model for LoRA
    model = prepare_model_for_kbit_training(model)
    
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # Training arguments
    training_arguments = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        optim="paged_adamw_32bit",
        save_steps=100,
        logging_steps=10,
        learning_rate=2e-4,
        weight_decay=0.001,
        fp16=True, # Set to bf16=True if your GPU supports it (RTX 40 series does)
        max_grad_norm=0.3,
        max_steps=500, # Adjust based on dataset size (epochs)
        warmup_ratio=0.03,
        group_by_length=True,
        lr_scheduler_type="cosine",
        report_to="none"
    )

    print("Starting SFTTrainer...")
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        peft_config=peft_config,
        dataset_text_field="text",
        max_seq_length=1024,
        tokenizer=tokenizer,
        args=training_arguments,
    )

    trainer.train()
    
    print(f"Saving final model to {output_dir}")
    trainer.model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print("Fine-tuning complete!")

if __name__ == "__main__":
    main()
