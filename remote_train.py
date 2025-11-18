#!/usr/bin/env python3
import os
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from datasets import load_dataset
from transformers import TrainingArguments, Trainer
import sys

# Параметры
model_name = "mistralai/Mistral-7B-v0.1"
output_dir = "/root/training/Mistral-lora-output"
data_path = "/root/training/data.jsonl"
epochs = 3
batch_size = 16

print(f"Loading model {model_name}...")

# Инициализация BitsAndBytes для квантизации
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16
)

# Загрузка модели
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True
)

# Подготовка модели для LoRA
model = prepare_model_for_kbit_training(model)

# Конфиг LoRA
lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)

# Применение LoRA
model = get_peft_model(model, lora_config)
print(f"Added LoRA adapters to model")

# Загрузка токенайзера
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
tokenizer.pad_token = tokenizer.eos_token

# Загрузка данных
print(f"Loading data from {data_path}...")
dataset = load_dataset("json", data_files=data_path)

# Функция форматирования
def formatting_func(example):
    text = example.get("text", "") or example.get("content", "")
    return {"text": text}

# Применение форматирования
dataset = dataset.map(formatting_func, remove_columns=[col for col in dataset["train"].column_names if col != "text"])

# Токенизация
def tokenize_func(examples):
    result = tokenizer(examples["text"], padding="max_length", max_length=512, truncation=True)
    result["labels"] = result["input_ids"].copy()
    return result

tokenized_dataset = dataset.map(tokenize_func, batched=True, remove_columns=["text"])

# Параметры обучения
training_args = TrainingArguments(
    output_dir=output_dir,
    overwrite_output_dir=True,
    num_train_epochs=epochs,
    per_device_train_batch_size=batch_size,
    save_steps=50,
    save_total_limit=3,
    logging_steps=10,
    learning_rate=2e-4,
    weight_decay=0.001,
    warmup_steps=10,
    gradient_accumulation_steps=2, # Эффективный батч = batch_size * 2
    fp16=True,
    gradient_checkpointing=True,
    report_to="none",  # Отключаем WandB и другие логгеры
)

# Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
    tokenizer=tokenizer
)

print("Starting training...")
trainer.train()

# Сохранение LoRA адаптера
model.save_pretrained(output_dir)
tokenizer.save_pretrained(output_dir)

print(f"Training completed! Model saved to {output_dir}")
print(f"To use this model:")
print(f"  from peft import AutoPeftModelForCausalLM")
print(f"  model = AutoPeftModelForCausalLM.from_pretrained('{output_dir}')")
