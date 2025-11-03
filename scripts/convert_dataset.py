import json
import argparse
import os
import sys

# Добавляем корневую директорию в путь Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def convert_dataset(input_file, output_file):
    """Конвертирует ваш датасет в формат для обучения"""
    
    # Проверяем существование входного файла
    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        return
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    converted_data = []
    
    for item in data:
        # Создаем промпт в формате для обучения
        prompt_parts = []
        
        if item.get('system'):
            prompt_parts.append(f"System: {item['system']}")
        
        prompt_parts.append(f"Instruction: {item['instruction']}")
        
        if item.get('input'):
            prompt_parts.append(f"Input: {item['input']}")
        
        prompt = "\n".join(prompt_parts) + "\nResponse:"
        
        converted_data.append({
            "instruction": item['instruction'],
            "input": item.get('input', ''),
            "output": item['output'],
            "system": item.get('system', ''),
            "prompt": prompt,
            "full_text": f"{prompt}{item['output']}"
        })
    
    # Создаем директорию если не существует
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Сохраняем в JSONL формат
    with open(output_file, 'w', encoding='utf-8') as f:
        for item in converted_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    
    print(f"Converted {len(converted_data)} samples to {output_file}")
    return converted_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert dataset format')
    parser.add_argument('--input', type=str, required=True, help='Input JSON file')
    parser.add_argument('--output', type=str, default='data/train_dataset.jsonl', help='Output JSONL file')
    
    args = parser.parse_args()
    convert_dataset(args.input, args.output)