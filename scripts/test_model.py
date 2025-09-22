#!/usr/bin/env python3

import argparse
import json
import os
import sys

# Добавляем корневую директорию в путь Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import load_config, setup_logging
from src.model_utils import LMStudioClient

def test_with_dataset_samples(config_path, dataset_path, num_samples=5):
    """Тестирование модели на примерах из датасета"""
    
    logger = setup_logging()
    config = load_config(config_path)
    client = LMStudioClient(config)
    
    # Загрузка датасета
    with open(dataset_path, 'r', encoding='utf-8') as f:
        samples = []
        for i, line in enumerate(f):
            if i >= num_samples:
                break
            samples.append(json.loads(line))
    
    print(f"Testing with {len(samples)} samples from dataset:")
    print("=" * 80)
    
    for i, sample in enumerate(samples, 1):
        print(f"\nSample {i}:")
        print(f"Instruction: {sample.get('instruction', '')}")
        
        if sample.get('input'):
            print(f"Input: {sample.get('input', '')}")
        
        print(f"Expected: {sample.get('output', '')}")
        
        # Создаем промпт
        prompt_parts = []
        if sample.get('system'):
            prompt_parts.append(f"System: {sample['system']}")
        prompt_parts.append(f"Instruction: {sample.get('instruction', '')}")
        if sample.get('input'):
            prompt_parts.append(f"Input: {sample.get('input', '')}")
        prompt = "\n".join(prompt_parts) + "\nResponse:"
        
        print("Generated:")
        response = client.generate(prompt)
        print(f"{response}")
        print("-" * 80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test model with dataset samples')
    parser.add_argument('--config', type=str, default='config/training_config.yaml')
    parser.add_argument('--dataset', type=str, required=True)
    parser.add_argument('--samples', type=int, default=3)
    
    args = parser.parse_args()
    
    # Проверяем существование файлов
    if not os.path.exists(args.config):
        print(f"Config file not found: {args.config}")
        print("Please make sure the config file exists or provide correct path with --config")
        sys.exit(1)
    
    if not os.path.exists(args.dataset):
        print(f"Dataset file not found: {args.dataset}")
        print("Please make sure the dataset file exists")
        sys.exit(1)
    
    test_with_dataset_samples(args.config, args.dataset, args.samples)