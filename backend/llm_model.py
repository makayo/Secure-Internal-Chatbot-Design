# backend/llm_model.py

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import os
import sys

print("[llm_model] sys.executable:", sys.executable)
print("[llm_model] CUDA_VISIBLE_DEVICES:",
      os.environ.get("CUDA_VISIBLE_DEVICES"))
print("[llm_model] torch version:", torch.__version__)
print("[llm_model] torch.version.cuda:", torch.version.cuda)
print("[llm_model] torch.cuda.is_available():", torch.cuda.is_available())


# Small but modern chat model
MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

if torch.cuda.is_available():
    DEVICE = "cuda"
    MODEL_KWARGS = {"torch_dtype": torch.float16}
elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
    DEVICE = "mps"
    MODEL_KWARGS = {"torch_dtype": torch.float16}
else:
    DEVICE = "cpu"
    MODEL_KWARGS = {}

print(f"[llm_model] Using device: {DEVICE}")

# Use fast tokenizer (no sentencepiece python package needed)
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)

# Ensure we have a pad token
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# Load the model in standard precision
# If you have GPU, you can use float16; otherwise default dtype is fine.
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME, **MODEL_KWARGS).to(DEVICE)

model.eval()


def generate_text(
    prompt: str,
    max_new_tokens: int = 60,   # lower default
    temperature: float = 0.4,   # safer default
    top_p: float = 0.9,
    do_sample: bool = True,
    repetition_penalty: float = 1.05,
    wrap_prompt: bool = True,   # when False, use prompt as-is (for chat history)
    strip_after: str | None = None,  # if provided, trim decoded text after this marker
) -> str:
    if not prompt:
        raise ValueError("Prompt must not be empty.")

    if wrap_prompt:
        system_instruction = (
            "You are a helpful, knowledgeable AI assistant. "
            "Answer the following question clearly and concisely."
        )

        full_prompt = (
            system_instruction
            + "\n\nQuestion:\n"
            + prompt.strip()
            + "\n\nAnswer:"
        )
    else:
        full_prompt = prompt.strip()

    inputs = tokenizer(full_prompt, return_tensors="pt").to(DEVICE)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=do_sample,
            repetition_penalty=repetition_penalty,
            pad_token_id=tokenizer.pad_token_id,
        )

    full_text = tokenizer.decode(output_ids[0], skip_special_tokens=True)

    # Only strip by "Answer:" when we used the default QA wrapper
    if wrap_prompt and "Answer:" in full_text:
        full_text = full_text.split("Answer:", 1)[1]
    elif strip_after and strip_after in full_text:
        full_text = full_text.split(strip_after, 1)[1]

    return full_text.strip()
