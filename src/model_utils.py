import logging
import time
from tqdm import tqdm
from .utils import make_api_request, generate_with_retry

logger = logging.getLogger(__name__)

class LMStudioClient:
    def __init__(self, config: dict):
        self.config = config
        self.base_url = config['api']['base_url']
        self.model_name = config['api']['model_name']
        self.api_key = config['api']['api_key']
    
    def generate(self, prompt: str, max_tokens: int = 2048):
        """Генерация текста через API"""
        return generate_with_retry(self.config, prompt, max_tokens)
    
    def evaluate(self, prompts: list, references: list = None):
        """Оценка модели на наборе промптов"""
        results = []
        
        for i, prompt in enumerate(tqdm(prompts, desc="Evaluating")):
            response = self.generate(prompt)
            
            result = {
                "prompt": prompt,
                "generated_response": response,
                "reference": references[i] if references and i < len(references) else None
            }
            
            results.append(result)
            
            if (i + 1) % 10 == 0:
                logger.info(f"Processed {i + 1}/{len(prompts)} prompts")
        
        return results
    
    def fine_tune_simulation(self, examples: list, num_epochs: int = 3):
        """
        Симуляция дообучения через few-shot learning
        """
        results = []
        
        for epoch in range(num_epochs):
            logger.info(f"Starting epoch {epoch + 1}/{num_epochs}")
            epoch_results = []
            
            for example in tqdm(examples, desc=f"Epoch {epoch + 1}"):
                # Создаем few-shot промпт
                few_shot_prompt = self._create_few_shot_prompt(examples, example)
                response = self.generate(few_shot_prompt)
                
                result = {
                    "epoch": epoch + 1,
                    "input": example.get('input', ''),
                    "instruction": example.get('instruction', ''),
                    "expected_output": example.get('output', ''),
                    "generated_output": response
                }
                
                epoch_results.append(result)
            
            results.extend(epoch_results)
            logger.info(f"Completed epoch {epoch + 1}")
        
        return results
    
    def _create_few_shot_prompt(self, examples: list, current_example: dict, num_shots: int = 2):
        """Создание few-shot промпта"""
        prompt = "Ты - помощник, дообученный на следующих примерах:\n\n"
        
        # Добавляем примеры
        shot_count = 0
        for example in examples:
            if example != current_example and shot_count < num_shots:
                prompt += f"Пример {shot_count + 1}:\n"
                prompt += f"Инструкция: {example.get('instruction', '')}\n"
                if example.get('input'):
                    prompt += f"Вход: {example.get('input', '')}\n"
                prompt += f"Ответ: {example.get('output', '')}\n\n"
                shot_count += 1
        
        # Добавляем текущий запрос
        prompt += "Новый запрос:\n"
        prompt += f"Инструкция: {current_example.get('instruction', '')}\n"
        if current_example.get('input'):
            prompt += f"Вход: {current_example.get('input', '')}\n"
        prompt += "Ответ:"
        
        return prompt