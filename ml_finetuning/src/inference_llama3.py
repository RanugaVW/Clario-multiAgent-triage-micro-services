import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
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

def generate_triage(model, tokenizer, product, issue_description):
    system_prompt = "You are an expert IT Support Triage Analyst. Your task is to analyze a customer support ticket based on the 'Product' and 'Issue Description', and classify it.\n\nBefore providing the final labels, you must provide a step-by-step logical reasoning process (Chain-of-Thought)."
    user_prompt = f"Product: {product}\nIssue Description: {issue_description}"
    
    # Format according to Llama-3 instruction format
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
    return generated_text

if __name__ == "__main__":
    model, tokenizer = load_model()
    
    # Test cases
    test_cases = [
        {
            "product": "Course Marketplace",
            "issue_description": "I bought a math course yesterday but my account is suspended and I can't access it. Please help."
        },
        {
            "product": "Payment & Billing",
            "issue_description": "I got charged twice for my subscription this month!"
        }
    ]
    
    print("\n" + "="*50)
    for test in test_cases:
        print(f"Product: {test['product']}")
        print(f"Issue: {test['issue_description']}")
        print("-" * 50)
        
        response = generate_triage(model, tokenizer, test['product'], test['issue_description'])
        print(f"Generated Response:\n{response}")
        print("=" * 50 + "\n")
