# Vast.ai Автоматизация для Fine-tuning LLM

Полностью автоматический скрипт для аренды GPU серверов на Vast.ai, дообучения языковых моделей с LoRA и скачивания результатов.

## 📋 Содержание

- [Возможности](#возможности)
- [Требования](#требования)
- [Установка](#установка)
- [Конфигурация](#конфигурация)
- [Использование](#использование)
- [Как это работает](#как-это-работает)
- [Параметры обучения](#параметры-обучения)
- [Структура проекта](#структура-проекта)
- [Troubleshooting](#troubleshooting)

## 🚀 Возможности

- ✅ **Автоматический поиск** самых дешевых GPU предложений на Vast.ai
- ✅ **Фильтрация по цене** - устанавливайте максимальную стоимость в час
- ✅ **Fallback система** - автоматический переход к следующему офферу при недоступности
- ✅ **SSH подключение** с автоматической настройкой окружения
- ✅ **Fine-tuning с LoRA** - эффективное дообучение больших моделей
- ✅ **4-bit квантизация** через BitsAndBytes для экономии VRAM
- ✅ **Автоматическая загрузка** обученной модели на локальный компьютер
- ✅ **Автоочистка** - удаление инстанса после завершения работы

## 📦 Требования

### Локальная машина
- Python 3.10+
- SSH клиент (встроен в Windows 10+/Linux/macOS)
- Доступ к интернету

### Vast.ai аккаунт
- Зарегистрированный аккаунт на [vast.ai](https://vast.ai)
- API токен (получается в [Account Settings](https://cloud.vast.ai/account/))
- SSH ключ добавлен в аккаунт ([SSH Keys Settings](https://cloud.vast.ai/account/ssh-keys/))

### Python зависимости
```bash
pip install -r requirements.txt
```

## 🔧 Установка

1. **Клонируйте репозиторий**
```bash
git clone <your-repo>
cd modelup
```

2. **Установите зависимости**
```bash
pip install -r requirements.txt
```

3. **Настройте SSH ключ**
   - Сгенерируйте SSH ключ (если нет):
     ```bash
     ssh-keygen -t ed25519 -C "your_email@example.com"
     ```
   - Скопируйте публичный ключ:
     ```bash
     cat ~/.ssh/id_ed25519.pub  # Linux/macOS
     type %USERPROFILE%\.ssh\id_ed25519.pub  # Windows
     ```
   - Добавьте в [Vast.ai SSH Keys](https://cloud.vast.ai/account/ssh-keys/)

4. **Подготовьте данные для обучения**
   - Формат JSONL: каждая строка - JSON объект с полем `"text"`
   - Пример: `data/sample_training_data.jsonl`

## ⚙️ Конфигурация

Откройте `vast.ai.check.py` и настройте следующие параметры:

### API токен Vast.ai
```python
BEARER_TOKEN = "ваш_токен_здесь"
```

### Параметры поиска GPU
```python
gpu_list = ["RTX 4090", "RTX 5090", "Q RTX 8000", "RTX 6000Ada", "A4000"]
max_price = 0.4  # Максимальная цена в USD/час
```

### Параметры обучения
```python
# В файле remote_train.py
MODEL_NAME = "mistralai/Mistral-7B-v0.1"  # Модель для дообучения
output_dir = "/root/training/Mistral-lora-output"
epochs = 3
batch_size = 16

LORA_CONFIG = {
    "r": 8,                          # Ранг LoRA
    "lora_alpha": 16,                # Alpha параметр
    "target_modules": ["q_proj", "v_proj"],  # Целевые слои
    "lora_dropout": 0.05,            # Отключение 5% параметров для обучения
    "bias": "none",                  # Настройка bios слоёв
    "task_type": "CAUSAL_LM"         # Способ обучения модели
}
```

### Путь к данным
```python
data_file = "data/sample_training_data.jsonl"
```

### Настройка Docker образов
```python
# В vast.ai.check.py
images_to_try = [
    "nvidia/cuda:12.1.0-base-ubuntu22.04",
    "nvidia/cuda:11.8.0-base-ubuntu22.04",
    "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
]
```

## 🎯 Использование

### Базовый запуск
```bash
python vast.ai.check.py
```

### Что происходит при запуске:

1. **Поиск офферов** - скрипт находит самые дешевые GPU в заданных пределах
2. **Создание инстанса** - автоматическая аренда сервера с самой дешовой видеокартой из доступных
3. **Настройка окружения** - установка Python, PyTorch, Transformers, PEFT
4. **Загрузка данных** - копирование вашего датасета на сервер
5. **Fine-tuning** - запуск обучения модели с LoRA
6. **Скачивание модели** - загрузка обученных весов на локальный компьютер
7. **Очистка** - автоматическое удаление инстанса

### Пример вывода
```
Vast.ai Auto Instance Manager
========================================
✓ API доступен и токен работает для чтения

Поиск офферов для RTX 5090...
Найден оффер: RTX 5090 — $0.0120/ч (id=12345)
✓ Найдено 15 офферов для попытки

--- Попытка 1/15: RTX 5090 @ $0.012/ч ---
✓ Инстанс успешно создан: 27921384

✓ ИНСТАНС ГОТОВ К РАБОТЕ!
Команда SSH: ssh root@ssh5.vast.ai -p 12982

✓ SSH готов
✓ Окружение настроено
✓ Скрипт загружен на инстанс
✓ Данные загружены на инстанс

ЗАПУСК ДООБУЧЕНИЯ (это может занять несколько часов)
...
✓ Дообучение завершено успешно!
✓ Модель загружена в: output/llama3-lora-model
```

## 🔍 Как это работает

### Архитектура скрипта

```
┌─────────────────────────────────────────────┐
│  1. Поиск и фильтрация GPU офферов          │
│     - Запрос к Vast.ai API                  │
│     - Сортировка по цене                    │
│     - Фильтр по max_price                   │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  2. Создание инстанса                       │
│     - PUT /asks/{id} или POST /instances    │
│     - Retry на следующий оффер при неудаче  │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  3. Ожидание запуска                        │
│     - Polling статуса инстанса              │
│     - Получение SSH параметров              │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  4. Настройка окружения (SSH)               │
│     - apt-get install python3 pip git       │
│     - pip install torch transformers peft   │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  5. Загрузка файлов (SCP)                   │
│     - train.py (скрипт обучения)            │
│     - data.jsonl (датасет)                  │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  6. Fine-tuning                             │
│     - Загрузка модели с 4-bit квантизацией  │
│     - Применение LoRA адаптеров             │
│     - Training loop (3 эпохи)               │
│     - Сохранение весов                      │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  7. Скачивание результатов (SCP)            │
│     - LoRA веса (adapter_model.bin)         │
│     - Конфигурация (adapter_config.json)    │
│     - Токенайзер                            │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  8. Очистка                                 │
│     - POST /instances/{id}/stop             │
│     - DELETE /instances/{id}                │
└─────────────────────────────────────────────┘
```

### Технические детали

## 📋 Функции vast.ai.check.py

### 1. API и конфигурация

#### `check_api_connection()`
**Назначение:** Проверка доступности Vast.ai API и валидности токена

**Алгоритм:**
```python
1. Проверка базового HTTP доступа к https://console.vast.ai
2. GET запрос к /api/v0/bundles с limit=1
3. Валидация ответа на наличие поля "offers"
```

**Возвращает:**
- `True` — API доступен, токен валиден
- `False` — Проблемы с доступом или токеном

---

#### `make_api_request(endpoint, method, params, json_data, retry_count=3)`
**Назначение:** Универсальная функция для HTTP запросов к Vast.ai API

**Параметры:**
- `endpoint` — путь API (например, "bundles", "instances/123")
- `method` — HTTP метод (GET, POST, PUT, DELETE)
- `params` — query параметры для GET
- `json_data` — тело запроса для POST/PUT
- `retry_count` — количество попыток при ошибке

**Особенности:**
- Автоматический retry при сетевых ошибках
- Обработка HTML ответов вместо JSON
- Timeout 30 секунд
- Bearer token аутентификация

**Возвращает:** JSON объект или None при ошибке

---

### 2. Поиск и управление офферами

#### `find_cheapest_offers(gpu_name, limit=20, max_price=None)`
**Назначение:** Поиск самых дешевых GPU офферов на Vast.ai

**Параметры:**
- `gpu_name` — название GPU ("RTX 4090", "RTX 5090", и т.д.)
- `limit` — максимальное количество офферов
- `max_price` — максимальная цена USD/час (фильтр)

**Алгоритм:**
```python
1. GET /bundles?gpu_name={gpu_name}&order=price&direction=asc&limit={limit*2}
2. Фильтрация по max_price (если указан)
3. Фильтрация по точному совпадению gpu_name
4. Сортировка по цене (ascending)
5. Возврат первых {limit} офферов
```

**Возвращает:** Список словарей:
```python
[
    {
        "id": 12345,
        "ask_contract_id": 67890,
        "bundle_id": 54321,
        "gpu_name": "RTX 5090",
        "price": 0.012
    },
    ...
]
```

---

#### `validate_bundle(bundle_id)`
**Назначение:** Проверка доступности конкретного bundle

**Алгоритм:**
```python
1. GET /bundles?q=id={bundle_id}
2. Проверка наличия оффера в ответе
3. Вывод информации: gpu_name, цена, доступность, min_bid
```

**Возвращает:**
- `True` — bundle найден и доступен
- `False` — bundle не найден

---

### 3. Создание и управление инстансами

#### `create_instance(offer_ids, image, disk=10, label, runtype="ssh")`
**Назначение:** Создание GPU инстанса на Vast.ai

**Параметры:**
- `offer_ids` — значение id/bundle_id или число
- `image` — Docker образ ("nvidia/cuda:12.1.0-base-ubuntu22.04")
- `disk` — размер диска в GB (по умолчанию 10)
- `label` — метка инстанса
- `runtype` — тип запуска ("ssh" по умолчанию)

**Алгоритм (fallback стратегия):**
```python
1. Формирование payload с параметрами запуска
2. Попытка с разными endpoints:
   - PUT /asks/{ask_id}
   - PUT /asks/{bundle_id}
   - POST /instances
3. Каждый endpoint пробуется с 2 вариантами payload
4. Проверка на ошибку "no_such_ask"
5. Извлечение instance_id из ответа
```

**Возвращает:**
- `instance_id` (int) — ID созданного инстанса
- `None` — не удалось создать

---

#### `wait_for_instance(instance_id, timeout=120, interval=10)`
**Назначение:** Ожидание готовности инстанса к SSH подключению

**Параметры:**
- `instance_id` — ID инстанса
- `timeout` — максимальное время ожидания (секунды)
- `interval` — интервал между проверками (секунды)

**Алгоритм:**
```python
1. Polling GET /instances/{instance_id} каждые {interval} секунд
2. Проверка статуса: actual_status, cur_state, status
3. Детекция ошибок: "exited", "error", CDI runtime errors
4. Извлечение SSH параметров: ssh_host, ssh_port, ssh_user
5. Вывод SSH команды при успехе
```

**Возвращает:**
- `True` — инстанс готов, SSH доступен
- `False` — ошибка запуска или timeout

**Обработка ошибок:**
- CDI (Container Device Interface) ошибки → автоматическая очистка
- Внутренние IP адреса → поиск публичного хоста

---

#### `stop_and_delete(instance_id)`
**Назначение:** Остановка и удаление инстанса

**Алгоритм:**
```python
1. POST /instances/{instance_id}/stop
2. Ожидание 5 секунд
3. DELETE /instances/{instance_id}
```

**Возвращает:** None (выводит статус в консоль)

---

### 4. SSH операции

#### `run_ssh_command(ssh_host, ssh_user, ssh_port, command)`
**Назначение:** Выполнение команды на удалённом сервере через SSH

**Параметры:**
- `ssh_host` — IP или hostname сервера
- `ssh_user` — имя пользователя (обычно "root")
- `ssh_port` — SSH порт (обычно 22)
- `command` — команда для выполнения

**Команда SSH:**
```bash
ssh -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=nul \
    -o ConnectTimeout=10 \
    -p {port} {user}@{host} {command}
```

**Особенности:**
- Отключена проверка host key (автоматическое подключение)
- Timeout 600 секунд (10 минут)
- Список аргументов (совместимость с PowerShell)

**Возвращает:** `(stdout, stderr, returncode)`

---

#### `wait_ssh_ready(ssh_host, ssh_user, ssh_port, timeout=600, interval=5)`
**Назначение:** Ожидание готовности SSH инстанса

**Алгоритм:**
```python
1. Попытка выполнить "echo ok" через SSH
2. Повтор каждые {interval} секунд
3. Вывод причины ошибки
```

**Возвращает:**
- `True` — SSH готов
- `False` — timeout

---

### 5. Настройка окружения и обучение

#### `setup_training_environment(ssh_host, ssh_user, ssh_port)`
**Назначение:** Установка зависимостей для обучения на удалённом сервере

**Команды:**
```bash
1. apt-get update
2. apt-get install -y python3 python3-pip git wget curl
3. pip3 install --upgrade pip
4. pip3 install torch transformers datasets peft bitsandbytes
5. pip3 install accelerate scikit-learn wandb
6. mkdir -p /root/training
```

**Особенности:**
- Каждая команда повторяется до 3 раз при ошибке
- Задержка 5 секунд между попытками
- Вывод сокращённого текста команды (первые 50 символов)

---

#### `upload_training_script(ssh_host, ssh_user, ssh_port, script_file="remote_train.py")`
**Назначение:** Загрузка скрипта обучения на инстанс

**Алгоритм:**
```python
1. Проверка существования локального файла
2. SCP копирование: local/remote_train.py → remote:/root/training/train.py
```

**SCP команда:**
```bash
scp -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=nul \
    -P {port} \
    remote_train.py {user}@{host}:/root/training/train.py
```

**Возвращает:**
- `True` — файл загружен
- `False` — ошибка загрузки

---

#### `upload_training_data(ssh_host, ssh_user, ssh_port, data_file)`
**Назначение:** Загрузка датасета на сервер

**Алгоритм:**
```python
1. Проверка существования локального файла
2. SCP копирование: local/{data_file} → remote:/root/training/data.jsonl
```

**Возвращает:**
- `True` — датасет загружен
- `False` — файл не найден или ошибка

---

#### `start_training(ssh_host, ssh_user, ssh_port)`
**Назначение:** Запуск процесса обучения на сервере

**Команда:**
```bash
cd /root/training && python3 train.py
```

**Особенности:**
- Синхронное выполнение (ждёт завершения)
- Timeout 600 секунд
- Вывод stdout при успехе
- Вывод stderr при ошибке

**Возвращает:**
- `True` — обучение завершено успешно
- `False` — ошибка обучения

---

#### `download_trained_model(ssh_host, ssh_user, ssh_port, output_dir)`
**Назначение:** Скачивание обученной модели с сервера

**Алгоритм:**
```python
1. Проверка содержимого /root/training/ (ls -la)
2. Проверка существования /root/training/Mistral-lora-output/
3. Создание локальной директории output/Mistral-lora-model/
4. SCP рекурсивное копирование всех файлов
```

**SCP команда:**
```bash
scp -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=nul \
    -P {port} -r \
    {user}@{host}:/root/training/Mistral-lora-output/* \
    {local_dir}/
```

**Возвращает:**
- `local_dir` (str) — путь к скачанной модели
- `None` — модель не найдена или ошибка

---

### 6. Главный цикл (main)

**Алгоритм выполнения:**

```python
1. Проверка API соединения
2. Поиск офферов для всех GPU из списка
3. Сортировка всех офферов по цене
4. Цикл по офферам (от дешёвых к дорогим):
   a. Цикл по Docker образам (fallback):
      - Попытка создать инстанс
      - Ожидание запуска (60 сек)
      - При ошибке CDI → удаление и переход к следующему образу
   b. Если инстанс запустился → выход из циклов
5. Получение SSH параметров инстанса
6. Ожидание SSH готовности (5 минут)
7. Настройка окружения
8. Загрузка скрипта и данных
9. Запуск обучения (синхронно)
10. Скачивание модели
11. Таймер на удаление инстанса (30 сек)
```

---

## 📋 Функции remote_train.py

### 1. Инициализация и загрузка модели

#### Параметры скрипта
```python
model_name = "mistralai/Mistral-7B-v0.1"  # HuggingFace модель
output_dir = "/root/training/Mistral-lora-output"  # Путь сохранения
data_path = "/root/training/data.jsonl"  # Путь к данным
epochs = 3  # Количество эпох
batch_size = 16  # Размер батча
```

---

#### BitsAndBytes конфигурация
```python
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,              # 4-bit квантизация (экономия VRAM)
    bnb_4bit_use_double_quant=True, # Двойная квантизация (ещё меньше памяти)
    bnb_4bit_quant_type="nf4",      # NormalFloat4 (лучше качество)
    bnb_4bit_compute_dtype=torch.float16  # Вычисления в FP16
)
```

---

#### Загрузка модели
```python
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    quantization_config=bnb_config,
    device_map="auto",           # Автоматическое распределение по GPU
    trust_remote_code=True       # Доверять коду модели
)
```

---

#### Подготовка для LoRA
```python
model = prepare_model_for_kbit_training(model)
```

**Что делает:**
- Замораживает веса базовой модели
- Настраивает градиенты только для LoRA адаптеров
- Оптимизирует для mixed precision training

---

### 2. Конфигурация LoRA

```python
lora_config = LoraConfig(
    r=8,                              # Ранг декомпозиции (размер адаптера)
    lora_alpha=16,                    # Масштабирующий коэффициент
    target_modules=["q_proj", "v_proj"],  # Применяем к Query и Value
    lora_dropout=0.05,                # Dropout 5% для регуляризации
    bias="none",                      # Не обучаем bias слои
    task_type="CAUSAL_LM"             # Causal Language Modeling
)

model = get_peft_model(model, lora_config)
```

**Что создаётся:**
```
Исходная модель (7B параметров, заморожена)
    ↓
+ LoRA адаптеры (4M параметров, обучаемые)
    ↓
= Обучаемо только 0.06% параметров!
```

---

### 3. Токенайзер

```python
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
tokenizer.pad_token = tokenizer.eos_token
```

**Зачем нужен pad_token:**
- Выравнивание последовательностей разной длины
- Без pad_token батчи не могут быть сформированы
- Используем EOS токен как padding

---

### 4. Загрузка и подготовка данных

#### Загрузка датасета
```python
dataset = load_dataset("json", data_files=data_path)
```

**Формат JSONL:**
```jsonl
{"text": "Пример текста для обучения 1"}
{"text": "Пример текста для обучения 2"}
{"text": "Пример текста для обучения 3"}
```

---

#### Функция форматирования датасета
```python
def formatting_func(example):
    text = example.get("text", "") or example.get("content", "")
    return {"text": text}
```

**Назначение:**
- Унификация поля (поддержка "text" и "content")
- Извлечение только текста

---

#### Токенизация
```python
def tokenize_func(examples):
    result = tokenizer(
        examples["text"],
        padding="max_length",
        max_length=512,
        truncation=True
    )
    result["labels"] = result["input_ids"].copy()
    return result

tokenized_dataset = dataset.map(tokenize_func, batched=True, remove_columns=["text"])
```

**Шаги:**
1. Текст → токены (числа)
2. Padding до 512 токенов (максимум 512 токенов текста)
3. Truncation если больше 512 (безопасное обрезание части текста)
4. Копирование input_ids в labels (для вычисления loss(уровень ошибок модели))

**Результат:**
```python
{
    "input_ids": [1, 234, 5678, ..., 2],  # Токены входа
    "attention_mask": [1, 1, 1, ..., 0],  # Маска (1=реальный, 0=padding)
    "labels": [1, 234, 5678, ..., 2]      # Токены для loss
}
```

---

### 5. Параметры обучения (TrainingArguments)

```python
training_args = TrainingArguments(
    output_dir=output_dir,                    # Путь сохранения
    overwrite_output_dir=True,                # Перезапись
    num_train_epochs=epochs,                  # 3 эпохи
    per_device_train_batch_size=batch_size,   # 16 примеров на GPU
    save_steps=50,                            # Checkpoint каждые 50 шагов
    save_total_limit=3,                       # Хранить 3 последних
    logging_steps=10,                         # Логи каждые 10 шагов
    learning_rate=2e-4,                       # LR = 0.0002 (Скорость обучения модели)
    weight_decay=0.001,                       # L2 регуляризация (Штраф за большие веса)
    warmup_steps=10,                          # Прогрев первые 10 шагов
    gradient_accumulation_steps=2,            # Эффективный батч = 32
    fp16=True,                                # Оптимизация веса (расчёты в 16 бит)
    gradient_checkpointing=True,              # Экономия памяти
    report_to="none",                         # Отключить WandB
)
```

---

### 6. Trainer и обучение

```python
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
    tokenizer=tokenizer
)

trainer.train()
```

**Что происходит внутри:**
```python
for epoch in range(3):
    for batch in dataloader:
        # Forward pass
        outputs = model(batch["input_ids"], labels=batch["labels"])
        loss = outputs.loss
        
        # Backward pass
        loss.backward()
        
        # Gradient accumulation
        if step % gradient_accumulation_steps == 0:
            optimizer.step()  # Обновление весов
            optimizer.zero_grad()  # Очистка градиентов
        
        # Logging
        if step % logging_steps == 0:
            print(f"Step {step}, Loss: {loss:.4f}")
        
        # Checkpointing
        if step % save_steps == 0:
            model.save_pretrained(f"{output_dir}/checkpoint-{step}")
```

---

### 7. Сохранение модели

```python
model.save_pretrained(output_dir)
tokenizer.save_pretrained(output_dir)
```

**Что сохраняется:**

```
/root/training/Mistral-lora-output/
├── adapter_model.safetensors   # LoRA веса (~50 MB)
├── adapter_config.json         # Конфигурация LoRA
├── tokenizer.json              # Токенайзер
├── tokenizer_config.json       # Настройки токенайзера
├── special_tokens_map.json     # Спецтокены
└── trainer_state.json          # Логи обучения
```

**Важно:** Сохраняются только LoRA адаптеры, не вся модель!

---

### 8. Вывод инструкций

```python
print(f"Training completed! Model saved to {output_dir}")
print(f"To use this model:")
print(f"  from peft import AutoPeftModelForCausalLM")
print(f"  model = AutoPeftModelForCausalLM.from_pretrained('{output_dir}')")
```

**Использование:**
```python
from peft import AutoPeftModelForCausalLM

# Загружает базовую модель + LoRA адаптеры
model = AutoPeftModelForCausalLM.from_pretrained(
    "/root/training/Mistral-lora-output"
)
```

---

## 🔄 Полный цикл обучения

```
1. Загрузка модели Mistral-7B-v0.1 (4-bit квантизация)
   ↓
2. Добавление LoRA адаптеров (r=8, только 0.06% параметров)
   ↓
3. Загрузка и токенизация датасета JSONL
   ↓
4. Обучение (3 эпохи, batch=16, accumulation=2)
   - Эффективный батч = 32
   - FP16 mixed precision
   - Gradient checkpointing
   - AdamW оптимизатор (lr=2e-4)
   ↓
5. Сохранение LoRA адаптеров (~50 MB)
   ↓
6. Вывод инструкций по использованию
```

---


### Конфигурация LoRA
| Параметр | Значение | Описание |
|----------|----------|----------|
| `r` | 8 | Ранг декомпозиции (размер адаптера) |
| `lora_alpha` | 16 | Масштабирующий коэффициент |
| `target_modules` | `["q_proj", "v_proj"]` | Слои для адаптации |
| `lora_dropout` | 0.05 | Dropout для регуляризации |

### Параметры Training
| Параметр | Значение | Описание |
|----------|----------|----------|
| `num_train_epochs` | 3 | Количество эпох |
| `per_device_train_batch_size` | 16 | Размер батча |
| `gradient_accumulation_steps` | 2 | Эффективный батч = 8 |
| `learning_rate` | 2e-4 | Скорость обучения |
| `fp16` | True | Mixed precision |
| `gradient_checkpointing` | True | Экономия памяти |
| `report_to` | "none" | Отключен WandB |

### Требования к VRAM
| Модель | VRAM (4-bit) | VRAM (8-bit) | VRAM (FP16) |
|--------|--------------|--------------|-------------|
| Mistral-7B | ~6 GB | ~10 GB | ~16 GB |
| Llama-2-13B | ~10 GB | ~16 GB | ~28 GB |
| Llama-3-8B | ~7 GB | ~12 GB | ~18 GB |

## 📁 Структура проекта

```
modelup/
├── vast.ai.check.py           # Основной скрипт автоматизации
├── remote_train.py            # Скрипт обучения (загружается на сервер)
├── VAST_AI_AUTOMATION.md      # Эта документация
├── Readme.md                  # Общее описание проекта
├── data/
│   ├── sample_training_data.jsonl  # Данные для дообучения
└── output/
    └── Mistral-lora-model/    # Скачанная модель (создаётся автоматически)
        ├── adapter_model.safetensors
        ├── adapter_config.json
        ├── tokenizer.json
        └── другие файлы токенайзера...
```

## 🔧 Troubleshooting

### Проблема: "401 Unauthorized" при запросе к API
**Решение**: Проверьте BEARER_TOKEN в скрипте. Получите новый токен в [Account Settings](https://cloud.vast.ai/account/).

### Проблема: "Permission denied (publickey)" при SSH
**Решение**: 
1. Проверьте, что SSH ключ добавлен в Vast.ai аккаунт
2. Убедитесь, что приватный ключ находится в `~/.ssh/id_ed25519` или `~/.ssh/id_rsa`

### Проблема: "No such file or directory" при скачивании модели
**Решение**: Обучение не завершилось или завершилось с ошибкой. Скрипт теперь автоматически проверяет содержимое директории и показывает:
```
Содержимое /root/training/:
total 12
drwxr-xr-x 2 root root 4096 Nov 18 19:45 .
drwx------ 1 root root 4096 Nov 18 19:30 ..
-rw-r--r-- 1 root root 1234 Nov 18 19:35 data.jsonl
-rw-r--r-- 1 root root 5678 Nov 18 19:35 train.py
```
Если директории `Mistral-lora-output` нет, проверьте логи обучения в секции "ЗАПУСК ДООБУЧЕНИЯ" для диагностики ошибки.

### Проблема: "GatedRepoError: Cannot access gated repo"
**Решение**: 
- Модель требует принятия лицензии на HuggingFace (например, Llama-2, Llama-3)
- Перейдите на страницу модели на HuggingFace и примите условия
- **Рекомендуется**: используйте открытую модель `mistralai/Mistral-7B-v0.1` (по умолчанию в `remote_train.py`)
- Или измените `model_name` в `remote_train.py` на любую открытую модель

### Проблема: CUDA Out of Memory
**Решение**:
- Уменьшите `batch_size` в train.py (с 16 до 4 или 2)
- Уменьшите `max_length` токенизации (с 512 до 256)
- Выберите GPU с большим VRAM

### Проблема: "No offers found"
**Решение**:
- Увеличьте `max_price` (например, до 0.6)
- Добавьте больше GPU в `gpu_list`
- Попробуйте запустить в другое время суток

### Проблема: Training stuck или очень медленный
**Решение**:
- Проверьте использование GPU: `nvidia-smi` через SSH
- Убедитесь, что model загружена на GPU (device_map="auto")
- Проверьте размер датасета - слишком маленький (< 100 примеров) может быть быстрым


## 📝 Использование обученной модели

```python
from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer

# Загрузка модели
model = AutoPeftModelForCausalLM.from_pretrained(
    "output/Mistral-lora-model",
    device_map="auto",
    torch_dtype="auto"
)

tokenizer = AutoTokenizer.from_pretrained("output/Mistral-lora-model")

# Инференс
prompt = "Вопрос: Что такое LoRA?\nОтвет:"
inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
outputs = model.generate(**inputs, max_new_tokens=100)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

## 🔧 Редактирование параметров обучения

Все параметры обучения находятся в файле `remote_train.py`:

```python
# Основные параметры
model_name = "mistralai/Mistral-7B-v0.1"  # Измените на другую модель
output_dir = "/root/training/Mistral-lora-output"
data_path = "/root/training/data.jsonl"
epochs = 3  # Количество эпох
batch_size = 16  # Размер батча

# LoRA параметры
lora_config = LoraConfig(
    r=8,  # Увеличьте для лучшего качества (16, 32)
    lora_alpha=16,
    target_modules=["q_proj", "v_proj"],  # Добавьте "k_proj", "o_proj" для большего охвата
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)

# Training параметры
training_args = TrainingArguments(
    learning_rate=2e-4,  # Уменьшите для более стабильного обучения
    per_device_train_batch_size=batch_size,
    gradient_accumulation_steps=2,  # Увеличьте для больших эффективных батчей
    num_train_epochs=epochs,
    # ... другие параметры
)
```

## 🤝 Contributing

Приветствуются pull requests! Для серьёзных изменений сначала откройте issue.


## 🔗 Полезные ссылки

- [Vast.ai Documentation](https://vast.ai/docs/)
- [PEFT Documentation](https://huggingface.co/docs/peft)
- [Transformers Documentation](https://huggingface.co/docs/transformers)
- [LoRA Paper](https://arxiv.org/abs/2106.09685)
- [BitsAndBytes](https://github.com/TimDettmers/bitsandbytes)

## 📧 Контакты

По вопросам и предложениям создавайте issues в репозитории.

---

**⚠️ Внимание**: Использование Vast.ai требует оплаты. Всегда проверяйте баланс и ограничивайте максимальную цену. Скрипт не несёт ответственности за ваши расходы.
