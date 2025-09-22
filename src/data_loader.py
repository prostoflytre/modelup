import json
import random

class DataProcessor:
    def __init__(self, config: dict):
        self.config = config
        self.max_tokens = config['data']['max_tokens_per_sample']
    
    def load_dataset(self, filepath: str) -> list:
        """Загрузка датасета"""
        data = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    data.append(json.loads(line.strip()))
        except FileNotFoundError:
            print(f"File {filepath} not found.")
        
        return data
    
    def prepare_training_data(self, data: list) -> list:
        """Подготовка данных для обучения"""
        processed_data = []
        
        for item in data:
            prompt = self._create_prompt(item)
            
            processed_data.append({
                'prompt': prompt,
                'instruction': item.get('instruction', ''),
                'input': item.get('input', ''),
                'output': item.get('output', ''),
                'system': item.get('system', ''),
                'full_text': f"{prompt}{item.get('output', '')}"
            })
        
        return processed_data
    
    def _create_prompt(self, item: dict) -> str:
        """Создание промпта из данных"""
        prompt_parts = []
        
        if item.get('system'):
            prompt_parts.append(f"System: {item['system']}")
        
        prompt_parts.append(f"Instruction: {item.get('instruction', '')}")
        
        if item.get('input'):
            prompt_parts.append(f"Input: {item.get('input', '')}")
        
        prompt = "\n".join(prompt_parts) + "\nResponse:"
        return prompt
    
    def train_test_split(self, data: list, test_size: float = 0.1):
        """Разделение на train/test"""
        random.seed(42)
        random.shuffle(data)
        
        split_idx = int(len(data) * (1 - test_size))
        train_data = data[:split_idx]
        test_data = data[split_idx:]
        
        return train_data, test_data
    
    def save_dataset(self, data: list, filepath: str):
        """Сохранение датасета"""
        with open(filepath, 'w', encoding='utf-8') as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')