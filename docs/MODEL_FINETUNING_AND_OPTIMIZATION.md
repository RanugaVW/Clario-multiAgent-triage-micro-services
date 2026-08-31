# Model Fine-Tuning and Evaluation Strategy
## CS3501 Data Science and Engineering Project

---

## 1. Target Models for Fine-Tuning

As part of our system optimization, we are evaluating the performance of compact, locally deployable open-weight models. We will fine-tune the following six models on our synthetically generated dataset (curated via Teacher-Student Knowledge Distillation):

1.  **Qwen/Qwen2.5-3B-Instruct**
2.  **Llama-3.2-3B-Instruct**
3.  **Gemma-3-1B**
4.  **meta-llama/Llama-3.1-8B-Instruct**
5.  **Mistral-Ministral-3B**
6.  **Gemma-3-4B**

*Rationale for Selection:* These models range from 1B to 8B parameters. As Data Science and Engineering students, evaluating this specific size bracket allows us to experiment with the trade-offs between parameter count, quantization depth (e.g., NF4), VRAM requirements, and reasoning capabilities when adapting models for domain-specific Support Ticket Triage and Resolution.

---

## 2. Recommended Benchmarks

Standardized, generalized benchmarks (like MMLU or GSM8K) are insufficient for evaluating domain-specific enterprise support systems. Instead, we must employ task-specific and RAG-specific evaluation frameworks.

### A. RAGAS (Retrieval Augmented Generation Assessment)
Because our system relies heavily on ChromaDB vector retrieval, we must evaluate how well our fine-tuned models utilize the provided context. RAGAS measures:
*   **Faithfulness:** Does the generated response logically follow from the retrieved chunks? (This directly correlates to mitigating *Logic-based hallucinations*).
*   **Answer Relevance:** Does the response directly address the customer's issue without digressing?
*   **Context Precision / Recall:** While mostly evaluating the retriever, it also tests if the LLM ignores noisy/irrelevant chunks.
*   **Why we use it:** It allows us to mathematically quantify hallucination rates rather than relying on qualitative "vibes".

### B. MT-Bench (Multi-Turn Benchmark) / LLM-as-a-Judge
As identified in the research (*Judging LLM-as-a-Judge with MT-Bench*), we will use a stronger teacher model (like GPT-4 or Gemini 1.5 Pro) to act as a judge comparing the outputs of our six fine-tuned models.
*   **Evaluation Criteria:** We will evaluate the models on **Reference-Guided Grading**, feeding the judge the ground-truth technical documentation alongside the model's draft.
*   **Why we use it:** To eliminate human-in-the-loop bottlenecks during hyperparameter tuning and to test if our fine-tuned models succumb to *Position Bias* or *Verbosity Bias* during multi-turn interactions.

### C. System & Engineering Metrics
*   **Classification F1-Score & Accuracy:** For the Routing/Triage task. Does the model correctly assign the ticket to the Technical or Billing team?
*   **Inference Latency (Tokens per Second - TPS):** Crucial for real-time support operations.
*   **VRAM Utilization (Peak Memory):** We need to quantify the deployment cost of Gemma-3-1B versus Llama-3.1-8B when served with LoRA adapters.

---

## 3. Specific Areas for Optimization

Based on our reviewed academic research, here is how we will specifically optimize our system architecture and fine-tuning pipelines.

### Optimization Area 1: Training Efficiency & Resource Allocation
*   **The Research Link:** *QLoRA: Efficient Finetuning of Quantized LLMs* & *LoRA: Low-Rank Adaptation of Large Language Models*.
*   **What we optimize:** GPU memory constraints during the fine-tuning of the 8B parameter model.
*   **How we do it:** We will not perform Full Parameter Fine-Tuning. We will optimize the training loop by implementing **4-bit NormalFloat (NF4) Quantization** and **Double Quantization**. We will freeze the base weights of our 6 models and inject low-rank adapters ($r=16, \alpha=32$) specifically targeting the query and value attention matrices (`q_proj`, `v_proj`). This allows us to train the Llama-3.1-8B model on a single consumer GPU (like an NVIDIA T4 or RTX 3090) without OOM (Out Of Memory) errors.

### Optimization Area 2: Dataset Quality & Semantic Alignment
*   **The Research Link:** *A Survey on Knowledge Distillation of LLMs* & *Triangle: Empowering Incident Triage*.
*   **What we optimize:** The noise-to-signal ratio in our training data and ticket classification accuracy.
*   **How we do it:** Before feeding our raw support tickets to the student models (Qwen, Llama, Gemma, Mistral), we use a Teacher Model to perform **Semantic Distillation**. We instruct the Teacher to parse the messy natural language of the tickets and extract structured JSON labels: `{"Location": "...", "Symptom": "...", "Capability_Required": "..."}`. We then fine-tune our 6 student models to predict this structured JSON. This optimizes the classification routing node by forcing the models to learn semantic extraction rather than just memorizing lexical ticket patterns.

### Optimization Area 3: Agentic Division of Labor (Routing)
*   **The Research Link:** *Multi-Agent Clinical Decision Support System for KTAS-Based Triage*.
*   **What we optimize:** The problem of "ambiguous range classifications" where a single model gets confused by overlapping contexts (e.g., a ticket mentioning both billing and technical API errors).
*   **How we do it:** We optimize the system topology by decoupling the tasks. Instead of fine-tuning one model to do everything, we utilize our fine-tuned models strictly as specialized agents within a LangGraph state machine. We fine-tune a smaller model (e.g., Gemma-3-1B) purely for the fast Semantic Distillation/Routing task, and we deploy a larger model (e.g., Llama-3.1-8B-Instruct) as the downstream Technical Specialist Agent, giving it a much narrower and more focused context window to operate on.

### Optimization Area 4: Hallucination Detection & Validation Filtering
*   **The Research Link:** *Evidence Graph Consistency in RAG* & *Mitigating Hallucination in LLMs*.
*   **What we optimize:** The false-positive rate of our automated ticket response validation.
*   **How we do it:** The research shows that different model families fail differently (e.g., Llama might structurally detach, while others write fluent lies). We will optimize our **Validation/Judge Node** by implementing **Evidence Graph Consistency (EGC)** checks. After our fine-tuned model generates a draft, the Judge Node will map sentences to the ChromaDB retrieved chunks. If the cosine similarity between a specific claim in the draft and the grounded context falls below a dynamic threshold, the system triggers a programmatic reflection loop, forcing the model to rewrite the unsupported sentence before the draft is presented to the user.
