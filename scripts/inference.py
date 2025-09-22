#!/usr/bin/env python3

import argparse
import os
import sys

# Добавляем корневую директорию в путь Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import load_config, setup_logging
from src.model_utils import LMStudioClient

def main():
    parser = argparse.ArgumentParser(description='Inference with LM Studio API')
    parser.add_argument('--config', type=str, default='config/training_config.yaml')
    parser.add_argument('--prompt', type=str, required=True)
    parser.add_argument('--max_tokens', type=int, default=2048)
    
    args = parser.parse_args()
    
    # Проверяем существование конфига
    if not os.path.exists(args.config):
        print(f"Config file not found: {args.config}")
        print("Please make sure the config file exists or provide correct path with --config")
        return
    
    # Настройка
    logger = setup_logging()
    config = load_config(args.config)
    
    # Клиент API
    client = LMStudioClient(config)
    
    # Генерация
    logger.info(f"Generating response for prompt: {args.prompt[:100]}...")
    response = client.generate(args.prompt, args.max_tokens)
    
    print("\n" + "="*50)
    print("PROMPT:")
    print(args.prompt)
    print("\n" + "="*50)
    print("RESPONSE:")
    print(response)
    print("="*50)

if __name__ == "__main__":
    main()