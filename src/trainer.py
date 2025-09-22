import logging
import json
import time
from datetime import datetime
from tqdm import tqdm
from .utils import save_checkpoint, load_checkpoint
from .model_utils import LMStudioClient

logger = logging.getLogger(__name__)

class APITrainer:
    def __init__(self, config: dict):
        self.config = config
        self.client = LMStudioClient(config)
        self.checkpoint_path = f"{config['training']['output_dir']}/checkpoint.jsonl"
    
    def train(self, train_data: list, eval_data: list = None):
        """Процесс обучения через API"""
        logger.info("Starting API-based training simulation")
        
        results = []
        start_time = datetime.now()
        
        # Загрузка чекпоинта если есть
        checkpoint_data = load_checkpoint(self.checkpoint_path)
        if checkpoint_data:
            results.extend(checkpoint_data)
            logger.info(f"Loaded checkpoint with {len(checkpoint_data)} samples")
        
        # Обработка данных
        for epoch in range(self.config['training']['num_train_epochs']):
            logger.info(f"Starting epoch {epoch + 1}")
            
            epoch_results = self._process_epoch(epoch + 1, train_data, len(results))
            results.extend(epoch_results)
            
            # Сохранение чекпоинта
            save_checkpoint(results, self.checkpoint_path)
            logger.info(f"Checkpoint saved after epoch {epoch + 1}")
            
            # Оценка если есть eval данные
            if eval_data:
                self.evaluate(eval_data, epoch + 1)
        
        training_time = datetime.now() - start_time
        logger.info(f"Training completed in {training_time}")
        
        return results
    
    def _process_epoch(self, epoch: int, data: list, start_idx: int = 0):
        """Обработка одной эпохи"""
        results = []
        
        for i, item in enumerate(tqdm(data[start_idx:], desc=f"Epoch {epoch}")):
            try:
                # Создаем промпт для few-shot обучения
                prompt = self._create_training_prompt(data, item)
                
                # Генерируем ответ
                response = self.client.generate(prompt)
                
                result = {
                    "epoch": epoch,
                    "index": start_idx + i,
                    "original_instruction": item.get('instruction', ''),
                    "original_input": item.get('input', ''),
                    "original_output": item.get('output', ''),
                    "generated_prompt": prompt,
                    "generated_response": response,
                    "timestamp": datetime.now().isoformat()
                }
                
                results.append(result)
                
                # Логирование прогресса
                if (i + 1) % self.config['training']['logging_steps'] == 0:
                    logger.info(f"Epoch {epoch}: Processed {i + 1}/{len(data)} samples")
                
                # Пауза чтобы не перегружать API
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing sample {i}: {e}")
                continue
        
        return results
    
    def _create_training_prompt(self, data: list, current_item: dict, num_examples: int = 2):
        """Создание обучающего промпта с примерами"""
        prompt = "Ты проходишь дообучение на следующих примерах:\n\n"
        
        # Добавляем примеры из данных (исключая текущий)
        examples = []
        for item in data:
            if item != current_item and len(examples) < num_examples:
                examples.append(item)
        
        for j, example in enumerate(examples):
            prompt += f"Пример {j + 1}:\n"
            prompt += f"Инструкция: {example.get('instruction', '')}\n"
            if example.get('input'):
                prompt += f"Входные данные: {example.get('input', '')}\n"
            prompt += f"Ожидаемый ответ: {example.get('output', '')}\n\n"
        
        # Добавляем текущий запрос
        prompt += "Новый запрос для обучения:\n"
        prompt += f"Инструкция: {current_item.get('instruction', '')}\n"
        if current_item.get('input'):
            prompt += f"Входные данные: {current_item.get('input', '')}\n"
        prompt += "Твой ответ должен быть:"
        
        return prompt
    
    def evaluate(self, eval_data: list, epoch: int = None):
        """Оценка модели"""
        logger.info("Starting evaluation")
        
        eval_prompts = []
        references = []
        
        for item in eval_data:
            prompt = self._create_prompt(item)
            eval_prompts.append(prompt)
            references.append(item.get('output', ''))
        
        eval_results = self.client.evaluate(eval_prompts, references)
        
        # Сохранение результатов оценки
        eval_file = f"{self.config['training']['output_dir']}/eval_results_epoch{epoch}.json"
        with open(eval_file, 'w', encoding='utf-8') as f:
            json.dump(eval_results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Evaluation results saved to {eval_file}")
        return eval_results
    
    def _create_prompt(self, item: dict) -> str:
        """Создание промпта для оценки"""
        prompt = f"Инструкция: {item.get('instruction', '')}\n"
        if item.get('input'):
            prompt += f"Входные данные: {item.get('input', '')}\n"
        prompt += "Ответ:"
        return prompt