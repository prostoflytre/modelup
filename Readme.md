# 📚 Учебная практика 2026
## Документация проекта "Переобучение llm модели для процесса обучения"

---

### 📋 Общая информация
- **Студент:** Удин Дмитрий Максимович
- **Группа:** 21ИС-24
- **Бизнес‑требования:** [Бизнес‑требования к дообучаемой LLM‑модели](./Readme_Бизнес_Требования.md)
- **Дисциплина:** Моделирование программных продуктов
- **Преподаватель:** Бобошко Михаил Николаевич
- **Дата выполнения:** 19 января 2026

---

## 👥 Группа 21ИС-24

| Номер | ФИО студента | Ник-ссылка на репозиторий |
|---------|---------|-------------|
| 1 | **Курносенко Александр Сергеевич** | [Alixandros](https://github.com/Alixandros/PKOvchinnikova_21IS_4semestr_Kyrnosenko.A.C) |
| 2 | **Ларетина Дарья Алексеевна** | [Al-Daria](https://github.com/Al-Daria/PKOvchinnikova_21IS_4semestr_Laretina) |
| 3 | **Малиневский Егор Сергеевич** | [Leendeseqy](https://github.com/Leendeseqy/PKOvchinnikova_21IS_4semestr_Malinevskiy) |
| 4 | **Микштас Артурас Мариусо** | [Mrkirk1](https://github.com/Mrkirk1/PKOvchinnikova_21IS_4semestr_Mikshtas) |
| 5 | **Мирошкин Егор Денисович** | [SWaT-137](https://github.com/SWaT-137/PKOvchinnikova_21IS_4semestr_Miroshkin) |
| 6 | **Поздняков Владимир Романович** | [Voviy-ux](https://github.com/Voviy-ux/PKOvchinnikova_21IS_PozdnyakovVR-main) |
| 7 | **Поздняков Дмитрий Романович** | [Mitya1606](https://github.com/Mitya1606/PKOvchinnikova_21IS_4semestr_PozdnyakovD) |
| 8 | **Полсачев Матвей Анатольевич** | [⏳В Процессе...⏳]() |
| 9 | **Рукас Вероника Олеговна** | [⏳В Процессе...⏳]() |
| 10 | **Силаков Максим Андреевич** | [Grozard](https://github.com/Grozard/PKOvchinnikova_21IS_4semestr_Silakov) |
| 11 | **Тараканова Андрей Андреевич** | [andreitar3](https://github.com/andreitar3/PKOvchinnikova_21IS_4semestr_Tarakanov) |
| 12 | **Удин Дмитрий Максимович** | [prostoflytre](https://github.com/prostoflytre/modelup) |
| 13 | **Фисенко Анна Андреевна** | [Fisai](https://github.com/Fisai/PKOvchinikova_21IS_4semestr_FisenkoAA) |
| 14 | **Шабанов Даниил Алексеевич** | [fertak08](https://github.com/fertak08/PKOvchinnikova_21IS_4semestr_Shabanov) |
| 15 | **Юхин Лавр Юрьевич** | [PananiXX](https://github.com/PananiXX/PKOvchinnikova_21IS_4semestr_Yukhin) |



Репозиторий содержит:

- `vast.ai.check.py` — автоматизация Vast.ai: поиск офферов → создание инстанса → ожидание → SSH/SCP → установка окружения → запуск обучения → скачивание результатов → (опционально) cleanup.
- `remote_train.py` — скрипт обучения, который копируется на инстанс как `/root/training/train.py`.

## Требования

### Локально

- Python 3.10+
- OpenSSH клиент (`ssh`/`scp`; на Windows 10/11 обычно уже есть)
- Доступ к Vast.ai

### Vast.ai

- API token (Account → API Key)
- SSH public key добавлен в аккаунт Vast (скрипт умеет добавлять автоматически — см. ниже)

### Python-зависимости

Установите зависимости локально:

```bash
pip install -r requirements.txt
```

## Быстрый старт

1) Создайте `.env` в корне проекта:

```env
VAST_AI_TOKEN=ваш_токен
```

Если `VAST_AI_TOKEN` не найден, `vast.ai.check.py` попросит ввести токен и сам создаст `.env`.

2) Укажите приватный SSH ключ для подключения:

```bash
python vast.ai.check.py --ssh-key C:/Users/Student/.ssh/id_ed25519
```

Скрипт:
- использует этот приватный ключ для `ssh`/`scp` (`-i ...`)
- по умолчанию попробует автоматически добавить соответствующий public key в Vast аккаунт

Если public key уже есть строкой  можно добавить напрямую:

```bash
python vast.ai.check.py --ssh-pubkey "ssh-ed25519 AAAA... user@host"
```

3) Подготовьте данные для обучения

- локальный пример: `data/sample_training_data.jsonl`
- при запуске скрипт загружает его на инстанс как `/root/training/data.jsonl`

Формат JSONL: 1 строка = 1 JSON объект. В `remote_train.py` берётся поле `text` (или `content`).

Пример строки:

```json
{"text": "Привет! Объясни разницу между GPU и CPU."}
```

## Запуск и режимы

`vast.ai.check.py` имеет 3 режима.

### 1) CREATE mode (по умолчанию)

Полный цикл: поиск офферов  создание инстанса  подготовка  обучение  скачивание  cleanup.

```bash
python vast.ai.check.py --ssh-key C:/Users/Student/.ssh/id_ed25519
```

Полезные флаги:

- `--skip-setup`  не ставить зависимости на инстансе
- `--skip-upload`  не загружать `train.py` и датасет
- `--no-cleanup`  не удалять инстанс после завершения
- `--continue-on-ssh-auth-failure`  продолжать перебор офферов, если SSH вернул `Permission denied (publickey)`

Про CDI/GPU:
- если на одной машине/оффере ловится ошибка вида `failed to inject CDI devices` / `unresolvable CDI devices ... gpu=0 unknown`, скрипт прекращает перебор всех docker image для этой машины и переходит к следующему офферу.

### 2) ATTACH mode

Подключиться к уже запущенному инстансу по `instance_id`.

```bash
python vast.ai.check.py --attach 12345678 --ssh-key C:/Users/Student/.ssh/id_ed25519
```

### 3) DESTROY mode

Остановить и удалить конкретный инстанс:

```bash
python vast.ai.check.py --destroy 12345678
```

## Что делает скрипт на инстансе

### Установка окружения

`vast.ai.check.py` выполняет (в целом):

- `apt-get update`
- `apt-get install -y --no-install-recommends python3 python3-pip git wget curl`
- `python3 -m pip install --upgrade pip`
- `python3 -m pip install -U transformers datasets peft bitsandbytes accelerate scikit-learn wandb`
- `torch` ставится только если его нет (в `pytorch/pytorch:*` образах он обычно уже есть)
- создаёт директорию `/root/training`

### Файлы

- `/root/training/train.py`  загруженная копия `remote_train.py`
- `/root/training/data.jsonl`  загруженный датасет

### Запуск обучения

Запуск:

```bash
cd /root/training && python3 train.py
```

## Про `remote_train.py`

Текущее поведение:

- `model_name = "openai/gpt-oss-20b"`
- `data_path = "/root/training/data.jsonl"`
- 4-bit квантизация (BitsAndBytes)
- LoRA через `peft` (target_modules: `all-linear`)
- токенизация: `max_length=2048`, `padding="max_length"`, `truncation=True`
- обучение через `Trainer`
- сохранение адаптера и токенайзера в `output_dir`

Параметры обучения в коде:

- `epochs = 3`
- `per_device_train_batch_size = 2`
- `gradient_accumulation_steps = 8`
- `save_steps = 50`
- `fp16 = True`, `gradient_checkpointing = True`

### Важно: output_dir и скачивание результата

`vast.ai.check.py` скачивает результаты из директории:

- `/root/training/Mistral-lora-output/*`

А в `remote_train.py` по умолчанию:

- `output_dir = "/root/training/Gpt-QLora-output"`

Чтобы скачивание работало из коробки, сделайте одно из двух:

1) Поменять `output_dir` в `remote_train.py` на:

```python
output_dir = "/root/training/Mistral-lora-output"
```

2) Или поменять путь скачивания в `vast.ai.check.py` (функция `download_trained_model`).

## Настройка поиска GPU и docker image

В create-mode список GPU, лимит цены и список docker image заданы прямо в конце `vast.ai.check.py` (блок `CREATE MODE`).

Обычно меняют:

- `gpu_list`
- `max_price`
- `images_to_try`

## Troubleshooting

### `Permission denied (publickey)`

- В `--ssh-key` должен быть ПРИВАТНЫЙ ключ (не `.pub`).
- Скрипт использует `BatchMode=yes`, поэтому если ключ защищён passphrase, SSH не сможет спросить пароль.

Решение для passphrase-ключа (Windows PowerShell):

```powershell
Start-Service ssh-agent
ssh-add C:\Users\Student\.ssh\id_ed25519
```

### Windows: `UNPROTECTED PRIVATE KEY FILE` / `bad permissions`

Нужно исправить ACL на приватный ключ, чтобы доступ был только у пользователя. Пример (PowerShell):

```powershell
icacls "C:\Users\Student\.ssh\id_ed25519" /inheritance:r
icacls "C:\Users\Student\.ssh\id_ed25519" /grant:r %USERNAME%:F
icacls "C:\Users\Student\.ssh\id_ed25519" /remove:g "BUILTIN\Users" "BUILTIN\Administrators" "NT AUTHORITY\SYSTEM"
```

### CDI/GPU injection error

Сообщения вида:

- `failed to inject CDI devices`
- `unresolvable CDI devices ... gpu=0 unknown`

Это проблема конкретного хоста/рантайма. Скрипт пропускает такой оффер, не перебирая остальные docker image на этой машине.

### DNS до DockerHub (`registry-1.docker.io: no such host`)

Обычно означает проблемы DNS на стороне хоста. Скрипт распознаёт эту ошибку при создании и пробует следующий вариант.
