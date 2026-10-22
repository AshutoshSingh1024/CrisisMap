"""Lazy local inference with the bundled Qwen2.5-0.5B instruction model."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal


class AssistantWorker(QThread):
    answered = Signal(str)

    def __init__(self, question: str, facts: str, parent=None) -> None:
        super().__init__(parent)
        self.question = question
        self.facts = facts

    def run(self) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            model_dir = Path(__file__).parent / "resources" / "model" / "qwen2.5-0.5b-instruct"
            if not hasattr(AssistantWorker, "_model"):
                AssistantWorker._tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
                # The bundled checkpoint is BF16; FP32 is the safest CPU format on Windows.
                AssistantWorker._model = AutoModelForCausalLM.from_pretrained(
                    model_dir, local_files_only=True, torch_dtype=torch.float32
                )
                AssistantWorker._model.eval()
            tokenizer = AssistantWorker._tokenizer
            model = AssistantWorker._model
            instruction = (
                "You are CrisisMap's disaster-assessment assistant. Answer only the user's question, in at most "
                "two short sentences (35 words total). Use only explicit facts in the application context; do "
                "not guess, extrapolate, or add general advice. If the answer is absent, say 'The current app "
                "data does not specify.' Clearly distinguish scenario inputs from a completed assessment. "
                "Never invent risk scores, places, shelters, routes, contacts, or live conditions. For immediate "
                "danger, tell the user to follow local authorities.\n\nApplication context:\n"
            )
            context_tokens = tokenizer.encode(self.facts, add_special_tokens=False)
            messages = [
                {"role": "system", "content": instruction},
                {"role": "user", "content": self.question[:800]},
            ]
            base_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            base_tokens = len(tokenizer.encode(base_prompt, add_special_tokens=False))
            context_budget = max(0, 3800 - base_tokens)
            context = tokenizer.decode(context_tokens[:context_budget], skip_special_tokens=True)
            messages[0]["content"] += context
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
            with torch.inference_mode():
                output = model.generate(
                    **inputs, max_new_tokens=160, do_sample=False,
                    repetition_penalty=1.2, no_repeat_ngram_size=3,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )
            answer = tokenizer.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
            answer = " ".join(answer.strip().split())
            answer = answer.split("\n", 1)[0].strip()
            if any(phrase in answer.casefold() for phrase in ("study tip", "homework", "school assignment")):
                answer = "I couldn't find a grounded answer in the current map and assessment data. Try asking about the selected location, risk scores, scenario, factors, or recommendations."
            self.answered.emit(answer[:1000] or "The current app data does not specify.")
        except ImportError:
            self.answered.emit("Model runtime missing. Install it with: python -m pip install -r requirements.txt")
        except Exception as exc:
            self.answered.emit(f"Local model could not answer: {exc}")
