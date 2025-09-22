import yaml
import logging
import json
import time
import requests
from tqdm import tqdm

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

def make_api_request(config: dict, messages: list, max_tokens: int = 2048):
    """Выполнение запроса к LM Studio API"""
    url = f"{config['api']['base_url']}/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api']['api_key']}"
    }
    
    payload = {
        "model": config['api']['model_name'],
        "messages": messages,
        "temperature": config['model']['temperature'],
        "top_p": config['model']['top_p'],
        "max_tokens": max_tokens,
        "stream": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"API request failed: {e}")
        return None

def generate_with_retry(config: dict, prompt: str, max_retries: int = 3):
    """Генерация текста с повторными попытками"""
    for attempt in range(max_retries):
        try:
            messages = [{"role": "user", "content": prompt}]
            response = make_api_request(config, messages)
            
            if response and 'choices' in response and len(response['choices']) > 0:
                return response['choices'][0]['message']['content']
            
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2)
    
    return None

def save_checkpoint(data: list, filepath: str):
    """Сохранение чекпоинта"""
    with open(filepath, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

def load_checkpoint(filepath: str) -> list:
    """Загрузка чекпоинта"""
    data = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                data.append(json.loads(line.strip()))
    except FileNotFoundError:
        pass
    return data