# Clario System VRAM Requirements & Hosting Feasibility

If we want to host the full Clario ML Sidecar in the cloud **with all local AI models running purely on GPU hardware** (bypassing the Gemini API completely), here is the exact breakdown of the VRAM (Video RAM) calculations required.

## 1. Local LLM: Classification & Sentiment (`google/gemma-3-1b-it`)
*   **Parameter Count:** 1 Billion parameters
*   **Precision:** Loaded in native `bfloat16` (16-bit precision)
*   **Weight Memory:** 1 Billion × 2 bytes = **2.0 GB**
*   **KV Cache & Context Memory:** ~0.5 GB (during inference)
*   **Total VRAM:** **~2.5 GB**

## 2. Vision-Language Model: OCR Extraction (`Qwen/Qwen2-VL-2B-Instruct`)
*   **Parameter Count:** 2 Billion parameters
*   **Precision:** 4-bit Quantization (`bitsandbytes` NF4 double-quantization)
*   **Weight Memory:** 2 Billion × 0.5 bytes = **1.0 GB**
*   **Vision Encoder & Activation Memory:** ~0.8 GB (Vision Transformers require higher activation memory for image patches)
*   **Total VRAM:** **~1.8 GB**

## 3. RAG Embedding Model (`all-MiniLM-L6-v2`)
*   **Parameter Count:** 22 Million parameters
*   **Precision:** `float32` (default)
*   **Weight Memory:** ~90 MB
*   **Total VRAM:** **~0.1 GB** (Can also be easily offloaded to CPU RAM with 0 latency hit)

## 4. CUDA Context Overhead
*   Initializing PyTorch and reserving memory blocks for the CUDA environment universally requires overhead per GPU process.
*   **Total VRAM:** **~0.8 GB**

---

## 🧮 Total VRAM Calculation
**2.5 GB (Gemma) + 1.8 GB (Qwen) + 0.1 GB (Embeddings) + 0.8 GB (CUDA Overhead) = 5.2 GB Total VRAM.**

### Conclusion for Hosting:
To host the Clario backend with all local models running concurrently in memory without thrashing (offloading to slower CPU RAM), the cloud server requires a GPU with an absolute minimum of **6 GB of VRAM**. 

A standard **8 GB VRAM GPU** (such as an NVIDIA RTX 3060, RTX 4060, or a cloud-based NVIDIA T4 which has 16GB) is the highly recommended baseline for production stability. 

### Why the Free Tier Fails:
Cloud providers like Render or Heroku offer 0 GB of VRAM and only 512MB of standard CPU RAM on their free tiers. Attempting to load even a 4-bit quantized 2B parameter model will instantly crash the container due to out-of-memory (OOM) exceptions.

---

## 💰 Cloud Hosting Cost Analysis (Per Month)
If you deploy this architecture to a cloud provider, you must provision an instance with a dedicated GPU (e.g., an NVIDIA T4 16GB or RTX 4000 series 8GB). Here is the estimated 24/7 monthly cost across major platforms:

1. **Amazon Web Services (AWS) — ~$384 / month**
   *   **Instance:** `g4dn.xlarge` (NVIDIA T4 16GB VRAM, 4 vCPU, 16GB RAM)
   *   **Cost:** ~$0.526 per hour.

2. **Google Cloud Platform (GCP) — ~$394 / month**
   *   **Instance:** `n1-standard-4` + 1x NVIDIA T4 GPU attached.
   *   **Cost:** ~$0.35 (GPU) + ~$0.19 (Compute) = ~$0.54 per hour.

3. **DigitalOcean (Paperspace) — ~$365 / month**
   *   **Instance:** Core VM with NVIDIA Quadro P4000 (8GB VRAM).
   *   **Cost:** ~$0.51 per hour.

4. **RunPod / Vast.ai (Best for ML Startups) — ~$146 / month**
   *   **Instance:** Community Cloud / Serverless with RTX 3060 (12GB) or T4.
   *   **Cost:** ~$0.20 per hour.
   *   *Note: Using RunPod Serverless, you only pay per second of execution. If your support volume is low, actual costs could drop to **under $20/month**.*

---

## 🚀 The API Pivot Strategy (How to drop costs to $12/month)

During the viva, a great architectural point to bring up is the **API Pivot Strategy**. 

If you decide to replace the local `Gemma-3-1b` (Classification) and local `Qwen2-VL` (OCR) entirely with **Gemini API calls** (like `gemini-3.1-flash-lite`), the system architecture fundamentally changes:

1.  **VRAM Requirement drops to 0 GB:** The only local ML model left would be the RAG embedding model (`all-MiniLM-L6-v2`), which is so small (~90MB) that it runs perfectly on a standard CPU.
2.  **No GPU Server Needed:** You no longer need to pay for an AWS `g4dn.xlarge` or a RunPod GPU.
3.  **New Hosting Cost:** You can now host the Python ML Sidecar on a standard, cheap CPU Virtual Private Server (VPS) with 2GB of RAM.
    *   **DigitalOcean Droplet (2GB RAM):** ~$12 / month
    *   **AWS t3.small (2GB RAM):** ~$15 / month
    *   **Render Standard (2GB RAM):** ~$25 / month
4.  **Gemini API Cost:** Gemini 1.5 Flash / 3.1 Flash-Lite has an extremely generous Free Tier (1 million tokens per day). Even if you exceed it, the cost is fractions of a cent per ticket.

**The Trade-off:** 
By switching to APIs, your monthly hosting cost drops from **~$384** down to **~$12**. However, you sacrifice data privacy (since customer tickets are now being sent to Google's servers for classification and OCR, rather than being processed 100% locally on your own hardware).
