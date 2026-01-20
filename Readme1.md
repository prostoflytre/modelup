## 📋 Оглавление

- [🚀 Быстрый старт](#-быстрый-старт)
- [📁 Структура проекта](#-структура-проекта)
- [🔧 Установка](#-установка)
- [🎯 Использование](#-использование)
- [📊 Формат данных](#-формат-данных)

## 🚀 Быстрый старт

### 1. Клонирование и установка
```bash
git clone https://github.com/prostoflytre/modelup
cd modelup
pip install -r requirements.txt
```

### 2. Настройка LM Studio
1. **Запустите** LM Studio
2. **Загрузите** модель DeepSeek
3. **Включите** сервер API (по умолчанию порт 1234)
4. **Убедитесь**, что модель готова к использованию


## 📁 Структура проекта

```
deepseek-finetune/
├── 📂 config/
│   └── training_config.yaml          # Конфигурация обучения
├── 📂 data/
│   ├── data.json                     # Исходные данные для дообучения
│   └── train_dataset.jsonl           # Преобразованные данные
├── 📂 src/     
│   ├── __init__.py                   
│   ├── utils.py                      # Вспомогательные функции
│   ├── data_loader.py                # Загрузка данных
│   ├── model_utils.py                # Работа с API
│   └── trainer.py                    # Логика обучения
├── 📂 scripts/
│   ├── __init__.py                            
│   ├── train.py                      # Обучение модели
│   ├── inference.py                  # Генерация ответов
│   ├── test_model.py                 # Тестирование
│   └── convert_dataset.py            # Конвертация данных
├── 📂 output/                        # Результаты
├── requirements.txt                  # Зависимости
└── README.md                         # Документация
```

## ⚙️ Конфигурация

### 📄 `config/training_config.yaml`
```yaml
api:
  base_url: "http://localhost:1234/v1"
  model_name: "deepseek-model"
  api_key: "lm-studio"

model:
  temperature: 0.7
  top_p: 0.9
  max_tokens: 2048

data:
  dataset_path: "./data/processed/train_dataset.jsonl"
  max_samples: 1000
  test_size: 0.1
  max_tokens_per_sample: 2048

training:
  num_train_epochs: 3
  output_dir: "./outputs"
  logging_steps: 10
```

## 🔧 Модули проекта

### 🛠️ **src/utils.py**
**Вспомогательные функции и утилиты:**

- `setup_logging()` - настройка логирования
- `load_config()` - загрузка конфигурации модели (формат yaml)
- `make_api_request()` - выполнение запросов к LM Studio API
- `generate_with_retry()` - генерация с повторными попытками при ошибках
- `save_checkpoint()` - сохранение прогресса обучения в файл json
- `load_checkpoint()` - загрузка прогресса обучения из json файла

### 📊 **src/data_loader.py**
**Класс `DataProcessor` - основной обработчик данных:**

- `load_dataset()` - загрузка JSONL датасета (парсит каждую строку из json в Python объект и сохраняет в список data)
- `prepare_training_data()` - подготовка данных для обучения
- `_create_prompt()` - вспомогательный метод, преобразующий данные в определённый формат для обучения
- `train_test_split()` - разделение данных на тестовую и обучающую части
- `save_dataset()` - сохранение обработанных данных

### 🤖 **src/model_utils.py**
**Класс `LMStudioClient` - клиент для взаимодействия с LM моделью:**

- `generate()` - метод для генерации текста используя данные из config
- `evaluate()` - оценка качества результата модели на наборе тест промптов по сравнению с эталонными ответами
- `fine_tune_simulation()` - симуляция дообучения через few-shot, возвращающая результаты по всем эпохам обучения
- `_create_few_shot_prompt()` - создание few-shot промптов, исключая текущий пример из контекста

### 🎓 **src/trainer.py**
**Класс `APITrainer` - основной тренер:**

- `train()` - процесс обучения:
  - Может загрузить чекпоинт, если модель не завершила процесс дообучения, и закончить его
  - Проходит через все эпохи обучения из config
  - Сохраняет чекпоинт после каждой эпохи
  - Проводит оценку данных
  - Рассчитывает общее время обучения
  - Возвращает все результаты

- `_process_epoch()` - обработка одной эпохи:
  - Создаёт промпт с контекстом с помощью `_create_training_prompt()`
  - Отправляет запрос модели
  - Форматирует результат
  - Логирует каждый запрос

- `_create_training_prompt()` - создание обучающего промпта:
  - Исключает текущий элемент
  - Нумерует примеры

- `evaluate()` - оценка модели:
  - Создает промпты для тестовых данных
  - Сохраняет эталонные ответы для сравнения

## 🚀 Скрипты выполнения

### 🏃‍♂️ **scripts/train.py**
**Основной скрипт обучения:**

```bash
python scripts/train.py --data_path data/train_dataset.jsonl
```

**Функциональность:**
- Загрузка конфигурации и настройка (загрузка параметров из yaml файла, инициализация логирования, создание папки для результатов)
- Загрузка и подготовка данных (Загрузка данных из jsonl файла, Проверка успеха загрузки, логирование кол-ва загруженных данных)
- Разделение датасета на данные для обучения и для тестов:
  - `train_data` - данные для обучения
  - `eval_data` - данные для оценки качества
- Запуск процесса обучения

### 💬 **scripts/inference.py**
**Скрипт для генерации по произвольному промпту:**

```bash
python scripts/inference.py --prompt "Ваш вопрос здесь" --max_tokens 1000
```

**Функциональность:**
- Проверка конфигурационного файла
- Инициализация логгера, конфига и клиента LM
- Генерация ответов с помощью `class LMStudioClient.generate()`
- Форматированный вывод результатов

### 🧪 **scripts/test_model.py**
**Тестирование модели:**

```bash
python scripts/test_model.py --dataset data/test.jsonl --samples 5
```

**Функциональность:**
- Тестирование на примерах из датасета
- Сравнение с ожидаемыми ответами
- Настройка количества тестовых примеров

### 🔄 **scripts/convert_dataset.py**
**Конвертация датасетов:**

```bash
python scripts/convert_dataset.py --input data.json --output dataset.jsonl
```

**Функциональность:**
- Конвертация из JSON в JSONL формат
- Создание промптов в едином формате
- Автоматическое создание директорий

## 📊 Формат данных

### 📥 Входные данные (JSON)
```json
{
  "instruction": "Переведи на английский",
  "input": "Привет, как дела?",
  "output": "Hello, how are you?",
  "system": "Ты профессиональный переводчик"
}
```

### 📤 Подготовленные данные (JSONL)
```json
{
  "prompt": "System: Ты переводчик\nInstruction: Переведи на английский\nInput: Привет, как дела?\nResponse:",
  "instruction": "Переведи на английский",
  "input": "Привет, как дела?",
  "output": "Hello, how are you?",
  "system": "Ты переводчик",
  "full_text": "System: Ты переводчик\nInstruction: Переведи на английский\nInput: Привет, как дела?\nResponse:Hello, how are you?"
}
```

## 🎯 Использование

### 🏋️‍♂️ Обучение модели

```bash
# Базовое обучение
python scripts/train.py --data_path data/train_dataset.jsonl

# С кастомным конфигом
python scripts/train.py --config config/my_config.yaml --data_path data/train_dataset.jsonl

```

### 💭 Генерация ответов

```bash
# Простая генерация
python scripts/inference.py --prompt "Объясни квантовую физику"

# Длинные ответы
python scripts/inference.py --prompt "Напиши эссе о ИИ" --max_tokens 4096

# С другим конфигом
python scripts/inference.py --config config/deepseek.yaml --prompt "Ваш промпт"
```

### 🧪 Тестирование

```bash
# Быстрое тестирование
python scripts/test_model.py --dataset data/train_dataset.jsonl --samples 3

# Расширенное тестирование
python scripts/test_model.py --config config/test.yaml --dataset data/test.jsonl --samples 10
```

### 🔄 Конвертация данных

```bash
# Стандартная конвертация
python scripts/convert_dataset.py --input data/data.json --output data/train_dataset.jsonl
```

## 📈 Выходные данные

### 📂 Структура результатов:
```
outputs/
├── 📄 checkpoint.jsonl              # Чекпоинты процесса обучения
├── 📄 eval_results_epoch1.json      # Результаты оценки эпохи 1
├── 📄 eval_results_epoch2.json      # Результаты оценки эпохи 2
└── 📄 eval_results_epoch3.json      # Результаты оценки эпохи 3
```

## 🛠️ Требования

### Системные требования:
- **Python**: 3.8+
- **LM Studio**: с запущенным API сервером
- **Модель**: DeepSeek в LM Studio

### Установка зависимостей:
```bash
pip install -r requirements.txt
```
---

## 🆘 Поддержка

### Частые проблемы:
1. **API недоступен** - проверьте запущен ли LM Studio
2. **Файл конфига не найден** - укажите правильный путь через `--config`
3. **Нет данных** - используйте `--create_sample` для тестового датасета

### Логирование:
Все этапы работы логируются в консоль с временными метками для удобства отладки.

---
