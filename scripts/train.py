#!/usr/bin/env python3

import os, sys
import argparse
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import setup_logging, load_config
from src.data_loader import DataProcessor
from src.trainer import APITrainer



def main():
    parser = argparse.ArgumentParser(description='Fine-tune DeepSeek model via LM Studio API')
    parser.add_argument('--config', type=str, default='config/training_config.yaml', 
                       help='Path to config file')
    parser.add_argument('--data_path', type=str, default=None,
                       help='Path to training data')
    
    args = parser.parse_args()
    
    # Настройка логирования
    logger = setup_logging()
    
    # Загрузка конфигурации
    config = load_config(args.config)
    
    # Создание выходной директории
    os.makedirs(config['training']['output_dir'], exist_ok=True)
    
    # Обработчик данных
    data_processor = DataProcessor(config)

    
    # Проверка пути к данным
    if not args.data_path:
        raise ValueError("Please provide data_path or use --create_sample")
    
    # Загрузка данных
    logger.info("Loading data...")
    raw_data = data_processor.load_dataset(args.data_path)
    
    if not raw_data:
        raise ValueError(f"No data found in {args.data_path}")
    
    logger.info(f"Loaded {len(raw_data)} samples")
    
    # Подготовка данных
    processed_data = data_processor.prepare_training_data(raw_data)
    
    # Разделение на train/test
    train_data, eval_data = data_processor.train_test_split(
        processed_data, 
        config['data']['test_size']
    )
    
    logger.info(f"Train samples: {len(train_data)}, Eval samples: {len(eval_data)}")
    
    # Обучение
    trainer = APITrainer(config)
    results = trainer.train(train_data, eval_data)
    
    logger.info(f"Training completed. Processed {len(results)} samples")

if __name__ == "__main__":
    main()