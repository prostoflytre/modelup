import requests
import time
import threading
import sys
import json
import subprocess
import os
from urllib.parse import urljoin
from dotenv import load_dotenv

# ---------- Конфигурация ----------
# Загрузка переменных окружения из .env файла
load_dotenv()
BEARER_TOKEN = os.getenv("VAST_AI_TOKEN")

if not BEARER_TOKEN:
    print("⚠ VAST_AI_TOKEN не найден в .env файле")
    print("Для получения токена:")
    print("  1. Перейдите на https://console.vast.ai/")
    print("  2. Войдите в аккаунт")
    print("  3. Перейдите в Account -> API Key")
    print("  4. Скопируйте ваш API токен")
    print()
    
    token_input = input("Введите ваш Vast.ai API токен (или нажмите Enter для выхода): ").strip()
    
    if not token_input:
        print("❌ Токен не указан. Выход.")
        sys.exit(1)
    
    # Создаём .env файл с токеном
    env_path = os.path.join(os.getcwd(), ".env")
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"VAST_AI_TOKEN={token_input}\n")
        print(f"✓ Токен сохранён в {env_path}")
        BEARER_TOKEN = token_input
    except Exception as e:
        print(f"❌ Ошибка при сохранении токена: {e}")
        sys.exit(1)
BASE_URL = "https://console.vast.ai/api/v0"
HEADERS = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
LIFETIME_SECONDS = 36000


def print_safe(*args, **kwargs):
    text = " ".join(str(a) for a in args)
    enc = sys.stdout.encoding or "utf-8"
    safe = text.encode(enc, errors="replace").decode(enc)
    print(safe, **kwargs)

def make_api_request(endpoint, method="GET", params=None, json_data=None, retry_count=3):
    """Улучшенная функция запросов с ретраями"""
    url = urljoin(BASE_URL + "/", endpoint + "/")
    
    for attempt in range(retry_count):
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=HEADERS, params=params, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=HEADERS, json=json_data, timeout=30)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=HEADERS, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=HEADERS, json=json_data, timeout=30)
            else:
                return None
                
            print_safe(f"HTTP {method} {endpoint}: {response.status_code}")
            
            # Пробуем распарсить как JSON независимо от Content-Type
            if response.content:
                try:
                    json_data = response.json()
                    return json_data
                except json.JSONDecodeError:
                    # Если не JSON, возвращаем текст для анализа
                    return {"_raw_html": response.text[:2000], "_status_code": response.status_code}
            else:
                return {"_empty_response": True, "_status_code": response.status_code}
                
        except requests.exceptions.RequestException as e:
            print_safe(f"Попытка {attempt + 1} не удалась: {e}")
            if attempt < retry_count - 1:
                time.sleep(2)
            else:
                return None

def check_api_connection():
    """Проверка доступности API и прав токена"""
    print_safe("Проверяю соединение с API...")
    
    # Проверка базового доступа
    try:
        test_response = requests.get("https://console.vast.ai", timeout=10)
        if test_response.status_code == 200:
            print_safe("✓ Базовый доступ к Vast.ai есть")
        else:
            print_safe(f"✗ Проблемы с доступом к Vast.ai: HTTP {test_response.status_code}")
            return False
    except Exception as e:
        print_safe(f"✗ Нет доступа к Vast.ai: {e}")
        return False
    
    # Проверка API с токеном
    result = make_api_request("bundles", params={"limit": 1})
    
    if result and "offers" in result:
        print_safe("✓ API доступен и токен работает для чтения")
        return True
    else:
        print_safe("✗ Не удалось получить данные от API")
        return False


def validate_bundle(bundle_id):
    """Проверяет доступность bundle"""
    print_safe(f"Проверяю bundle {bundle_id}...")
    
    # Получаем детальную информацию о bundle
    result = make_api_request("bundles", params={"q": f"id={bundle_id}"})
    
    if result and "offers" in result and result["offers"]:
        offer = result["offers"][0]
        print_safe(f"✓ Bundle найден: {offer.get('gpu_name')} - ${offer.get('dph_total')}/ч")
        print_safe(f"  Доступность: {offer.get('onstart', 'unknown')}")
        print_safe(f"  Min Bid: ${offer.get('min_bid', 'unknown')}")
        return True
    else:
        print_safe("✗ Bundle не найден или недоступен")
        return False

def find_cheapest_offers(gpu_name="RTX 5090", limit=20, max_price=None):
    """Находит несколько самых дешёвых офферов
    
    Args:
        gpu_name: Название GPU для поиска
        limit: Максимальное количество офферов для возврата
        max_price: Максимальная цена в час (USD). Если None, нет ограничения
    """
    params = {
        "gpu_name": gpu_name,
        "limit": limit * 2 
    }
    resp = requests.get(f"{BASE_URL}/bundles/", params=params, headers=HEADERS)
    if resp.status_code != 200:
        print_safe("Ошибка получения списка офферов:", resp.status_code)
        print_safe(resp.text[:500])
        return []
    data = resp.json()
    offers = data.get("offers", [])


    result = []
    for offer in offers:
        price = offer.get("dph_total", float('inf'))
        
        # Если установлена максимальная цена, пропускаем более дорогие офферы
        if max_price is not None and price > max_price:
            continue

        if offer.get("gpu_name") != gpu_name:
            continue
        
        print_safe(f"Найден оффер: {offer.get('gpu_name')} — ${price:.4f}/ч (id={offer.get('id')})")
        result.append({
            "id": offer.get("id"),
            "ask_contract_id": offer.get("ask_contract_id"),
            "bundle_id": offer.get("bundle_id"),
            "gpu_name": offer.get("gpu_name"),
            "price": price
        })
        
        if len(result) >= limit:
            break
    
    if max_price is not None:
        print_safe(f"Найдено {len(result)} офферов в пределах ${max_price}/ч")
    
    return result
    

def create_instance(offer_ids, image="python:3.10", disk=10, label="auto-instance", runtype="ssh"):

    if isinstance(offer_ids, dict):
        bundle_id = offer_ids.get("bundle_id")
        ask_id = offer_ids.get("id")  # это же ask_contract_id
    else:
        ask_id = offer_ids
        bundle_id = offer_ids
    
    print_safe(f"Создаю инстанс: ask_id={ask_id}, bundle_id={bundle_id}…")
    
    # Подготовка payload — попробуем разные варианты
    payloads_to_try = [
        {
            "image": image,
            "label": label,
            "disk": disk,
            "runtype": runtype,
        },
        {
            "bundle_id": bundle_id,
            "image": image,
            "label": label,
            "disk": disk,
            "runtype": runtype,
        },
    ]
    
    # Попробуем разные endpoints и методы
    endpoints_to_try = [
        ("put", f"asks/{ask_id}"),
        ("put", f"asks/{bundle_id}"),
        ("post", f"instances"),
    ]
    
    result = None
    for endpoint_method, endpoint in endpoints_to_try:
        for payload in payloads_to_try:
            print_safe(f"Пытаюсь {endpoint_method.upper()} на /{endpoint}...")
            result = make_api_request(endpoint, method=endpoint_method, json_data=payload)
            
            if result:
                # Проверяем на ошибку "no_such_ask"
                if result.get("error") == "invalid_args" and "no_such_ask" in result.get("msg", ""):
                    print_safe(f"⚠ Оффер недоступен (no_such_ask): {result.get('msg')}")
                    return None
            
            if result and "_raw_html" not in result and result.get("success") is not None:
                if result.get("success") or "id" in result or "new_contract" in result:
                    print_safe(f"✓ Получен обещающий ответ от /{endpoint}")
                    break
        
        if result and "_raw_html" not in result and result.get("success") is not None:
            if result.get("success") or "id" in result or "new_contract" in result:
                break
    
    if not result:
        print_safe("✗ Пустой ответ от сервера")
        return None
        
    if "_raw_html" in result:
        print_safe("✗ Сервер вернул HTML вместо JSON")
        return None
    
    print_safe(f"DEBUG: Ответ на создание инстанса: {json.dumps(result, indent=2)[:500]}")
    
    # Проверка успешного ответа
    if result.get("success"):
        # Попробуем разные возможные поля с ID инстанса
        instance_id = result.get("new_contract") or result.get("id") or result.get("contract_id") or result.get("instance_id")
        if instance_id:
            print_safe(f"✓ Инстанс создан, ID = {instance_id}")
            return instance_id
    
    # Если нет success, пробуем просто вернуть ID если он есть
    if "id" in result:
        instance_id = result.get("id")
        print_safe(f"✓ Инстанс создан(?), ID = {instance_id}")
        return instance_id
    
    print_safe("✗ Не удалось получить ID инстанса. Ответ сервера:")
    print_safe(json.dumps(result, indent=2))
    return None

def wait_for_instance(instance_id, timeout=120, interval=10):
    print_safe(f"Ожидание запуска инстанса {instance_id}...")
    
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(interval)
        
        result = make_api_request(f"instances/{instance_id}")
        if not result:
            print_safe("⚠ Пустой ответ от сервера")
            continue
        
        
        # Пробуем разные возможные структуры ответа
        instance = result.get("instances") or result.get("contract") or result
        
        if isinstance(instance, dict):
            status = instance.get("actual_status") or instance.get("cur_state") or instance.get("status", "unknown")
            print_safe(f"DEBUG: Статус = {status}, доступные ключи инстанса: {list(instance.keys())}")
            
            # Проверка на ошибку запуска контейнера
            if status == "exited" or status == "error" or "error" in str(status).lower():
                print_safe(f"✗ Инстанс завершился с ошибкой: {status}")
                print_safe("  Возможно проблема с CDI/GPU на этом хосте")
                return False
            
            # Ищем SSH параметры в разных возможных местах
            ssh_host = instance.get("ssh_host") or instance.get("public_ipaddr") or instance.get("ip_now")
            
            if ssh_host:
                ssh_user = instance.get("ssh_user", "root")
                ssh_port = instance.get("ssh_port", 22)
                ssh_command = f"ssh {ssh_user}@{ssh_host} -p {ssh_port}"
                
                print_safe("\n" + "="*50)
                print_safe("✓ ИНСТАНС ГОТОВ К РАБОТЕ!")
                print_safe(f"Команда SSH: {ssh_command}")
                print_safe("="*50)
                return True
                
            print_safe(f"Статус: {status}...")
        else:
            print_safe("⚠ Не удалось получить статус инстанса")
            print_safe(f"  Полный ответ: {json.dumps(result, indent=2)[:500]}")
    
    print_safe("✗ Инстанс не запустился в отведённое время")
    return False

def stop_and_delete(instance_id):
    """Остановка и удаление инстанса"""
    print_safe(f"Останавливаю и удаляю инстанс {instance_id}...")
    
    # Остановка
    stop_result = make_api_request(f"instances/{instance_id}/stop", method="POST")
    if stop_result:
        print_safe("✓ Инстанс остановлен")
    else:
        print_safe("✗ Не удалось остановить инстанс")
    
    time.sleep(5)
    
    # Удаление
    delete_result = make_api_request(f"instances/{instance_id}", method="DELETE")
    if delete_result:
        print_safe("✓ Инстанс удалён")
    else:
        print_safe("✗ Не удалось удалить инстанс")

def run_ssh_command(ssh_host, ssh_user, ssh_port, command):
    """Выполнить команду на инстансе через SSH"""
    # Используем список аргументов для правильной обработки в PowerShell
    # Порядок важен: ssh [опции] [user@]hostname [command]
    ssh_args = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=nul", 
        "-o", "ConnectTimeout=10",
        "-p", str(ssh_port),
        f"{ssh_user}@{ssh_host}",
        command
    ]
    try:
        result = subprocess.run(ssh_args, capture_output=True, text=True, timeout=600)
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return None, "Command timeout", -1
    except Exception as e:
        return None, str(e), -1

def wait_ssh_ready(ssh_host, ssh_user, ssh_port, timeout=300, interval=5):
    """Дождаться готовности SSH на инстансе"""
    print_safe(f"Жду готовности SSH {ssh_host}:{ssh_port}...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        stdout, stderr, code = run_ssh_command(ssh_host, ssh_user, ssh_port, "echo ok")
        if code == 0:
            print_safe(f"✓ SSH готов (ответ: {stdout.strip()})")
            return True
        else:
            elapsed = int(time.time() - start_time)
            print_safe(f"⏳ SSH не готов... ({elapsed}s) - {stderr}")
            time.sleep(interval)
    
    print_safe(f"❌ SSH не стал доступен за {timeout} секунд")
    return False

def setup_training_environment(ssh_host, ssh_user, ssh_port):
    """Установить зависимости для дообучения на инстансе"""
    print_safe(f"Настраиваю окружение на инстансе {ssh_host}...")
    
    # Команды для установки зависимостей (Debian/Ubuntu базовый образ Vast.ai)
    setup_commands = [
        "apt-get update",
        "apt-get install -y python3 python3-pip git wget curl",
        "pip3 install --upgrade pip",
        "pip3 install torch transformers datasets peft bitsandbytes",
        "pip3 install accelerate scikit-learn wandb",
        "mkdir -p /root/training"
    ]
    
    for cmd in setup_commands:
        print_safe(f"Выполняю: {cmd[:50]}...")
        # Повтор команды при сбое (до 3 попыток)
        for attempt in range(3):
            stdout, stderr, code = run_ssh_command(ssh_host, ssh_user, ssh_port, cmd)
            if code == 0:
                print_safe(f"✓ OK")
                break
            else:
                if attempt < 2:
                    print_safe(f"⚠ Ошибка (попытка {attempt+1}/3), повтор через 5 сек...")
                    time.sleep(5)
                else:
                    print_safe(f"⚠ Ошибка: {stderr[:200]}")
    
    print_safe("✓ Окружение настроено")
    return True

def upload_training_script(ssh_host, ssh_user, ssh_port, script_file="remote_train.py"):
    """Загрузить скрипт дообучения на инстанс"""
    print_safe(f"Загружаю скрипт {script_file} на инстанс...")
    
    if not os.path.exists(script_file):
        print_safe(f"✗ Файл {script_file} не найден")
        return False
    
    # Скопировать через SCP с опциями как в SSH
    scp_args = [
        "scp",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=nul",
        "-P", str(ssh_port),
        script_file,
        f"{ssh_user}@{ssh_host}:/root/training/train.py"
    ]
    result = subprocess.run(scp_args, capture_output=True, text=True)
    
    if result.returncode == 0:
        print_safe("✓ Скрипт загружен на инстанс")
        return True
    else:
        print_safe(f"✗ Ошибка загрузки скрипта: {result.stderr}")
        return False

def upload_training_data(ssh_host, ssh_user, ssh_port, data_file):
    """Загрузить данные для дообучения на инстанс"""
    print_safe(f"Загружаю данные {data_file} на инстанс...")
    
    if not os.path.exists(data_file):
        print_safe(f"✗ Файл {data_file} не найден")
        return False
    
    scp_args = [
        "scp",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=nul",
        "-P", str(ssh_port),
        data_file,
        f"{ssh_user}@{ssh_host}:/root/training/data.jsonl"
    ]
    result = subprocess.run(scp_args, capture_output=True, text=True)
    
    if result.returncode == 0:
        print_safe("✓ Данные загружены на инстанс")
        return True
    else:
        print_safe(f"✗ Ошибка загрузки данных: {result.stderr}")
        return False

def start_training(ssh_host, ssh_user, ssh_port):
    """Запустить дообучение на инстансе"""
    print_safe("Запускаю дообучение на инстансе...")
    
    cmd = "cd /root/training && python3 train.py"
    stdout, stderr, code = run_ssh_command(ssh_host, ssh_user, ssh_port, cmd)
    
    if code == 0:
        print_safe("✓ Дообучение завершено успешно!")
        print_safe(stdout)
        return True
    else:
        print_safe(f"✗ Ошибка при дообучении: {stderr}")
        return False

def download_trained_model(ssh_host, ssh_user, ssh_port, output_dir):
    """Загрузить обученную модель с инстанса"""
    print_safe(f"Проверяю наличие обученной модели на инстансе...")
    
    # Сначала проверяем что директория существует
    check_cmd = "ls -la /root/training/"
    stdout, stderr, code = run_ssh_command(ssh_host, ssh_user, ssh_port, check_cmd)
    
    if code == 0:
        print_safe("Содержимое /root/training/:")
        print_safe(stdout)
    else:
        print_safe(f"✗ Ошибка при проверке директории: {stderr}")
        return None
    
    # Проверяем конкретно выходную директорию
    check_output_cmd = "ls -la /root/training/Mistral-lora-output/ 2>/dev/null || echo 'Directory not found'"
    stdout, stderr, code = run_ssh_command(ssh_host, ssh_user, ssh_port, check_output_cmd)
    print_safe(f"Содержимое выходной директории: {stdout}")
    
    if "Directory not found" in stdout or "No such file" in stdout:
        print_safe("✗ Модель не была сохранена - обучение завершилось с ошибкой")
        return None
    
    print_safe(f"Загружаю обученную модель с инстанса...")
    local_dir = os.path.join(output_dir, "Mistral-lora-model")
    os.makedirs(local_dir, exist_ok=True)
    
    scp_args = [
        "scp",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=nul",
        "-P", str(ssh_port),
        "-r",
        f"{ssh_user}@{ssh_host}:/root/training/Mistral-lora-output/*",
        f"{local_dir}/"
    ]
    result = subprocess.run(scp_args, capture_output=True, text=True)
    
    if result.returncode == 0:
        print_safe(f"✓ Модель загружена в {local_dir}")
        return local_dir
    else:
        print_safe(f"✗ Ошибка загрузки модели: {result.stderr}")
        return None

# ---------- MAIN ----------
if __name__ == "__main__":
    print_safe("Vast.ai Auto Instance Manager")
    print_safe("=" * 40)
    
    if not check_api_connection():
        sys.exit(1)
    
    # Ищем доступные офферы
    # GPUs отсортированы примерно от самых дешёвых к дорогим
    gpu_list = ["RTX 4090", "RTX 5090", "Q RTX 8000", "RTX 6000Ada", "A4000"]
    
    max_price = 0.4  # Максимальная цена в час (USD) - увеличено для поиска на других хостах
    
    all_offers = []
    for gpu in gpu_list:
        print_safe(f"\nПоиск офферов для {gpu}...")
        offers = find_cheapest_offers(gpu_name=gpu, limit=20, max_price=max_price)
        all_offers.extend(offers)
    
    # Сортируем офферы по цене (от дешёвых к дорогим)
    all_offers.sort(key=lambda x: x['price'])
    
    if not all_offers:
        print_safe(f"❌ Не найдено офферов в пределах ${max_price}/ч")
        sys.exit(1)
    
    print_safe(f"\n✓ Найдено {len(all_offers)} офферов для попытки (отсортировано по цене)")
    
    # Пытаемся создать инстанс, перебирая офферы
    instance_id = None
    # Пробуем разные образы, если один не работает
    images_to_try = [
        "nvidia/cuda:12.1.0-base-ubuntu22.04",
        "nvidia/cuda:11.8.0-base-ubuntu22.04",
        "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
    ]
    
    for i, offer_data in enumerate(all_offers, 1):
        print_safe(f"\n--- Попытка {i}/{len(all_offers)}: {offer_data['gpu_name']} @ ${offer_data['price']}/ч ---")
        
        # Пробуем разные образы для этого оффера
        for image_idx, image in enumerate(images_to_try, 1):
            print_safe(f"  Пробую образ {image_idx}/{len(images_to_try)}: {image}")
            
            instance_id = create_instance(
                offer_ids=offer_data,
                image=image,
                disk=40,
                label="test-auto-instance"
            )
            
            if instance_id:
                print_safe(f"✓ Инстанс создан, ID = {instance_id}")
                
                # Ожидаем запуска с проверкой на ошибки (короткий timeout для быстрого обнаружения проблем)
                if wait_for_instance(instance_id, timeout=60, interval=5):
                    print_safe(f"✓ Инстанс успешно запущен: {instance_id}")
                    break
                else:
                    print_safe(f"✗ Инстанс не запустился или завершился с ошибкой")
                    print_safe(f"  Удаляю проблемный инстанс...")
                    stop_and_delete(instance_id)
                    instance_id = None
            else:
                print_safe(f"✗ Не удалось создать инстанс с образом {image}")
        
        # Если нашли рабочий инстанс, выходим из главного цикла
        if instance_id:
            break
        else:
            print_safe(f"✗ Все образы не сработали для этого оффера, пробую следующий...")
    
    if not instance_id:
        print_safe("❌ Не удалось создать рабочий инстанс ни с одним оффером")
        sys.exit(1)
    
    
    # Ожидаем запуска
    if True:  # Инстанс уже запущен в цикле выше
        # Получаем SSH детали
        instance_info = make_api_request(f"instances/{instance_id}")
        instances = instance_info.get("instances") or instance_info.get("contract") or instance_info
        
        if isinstance(instances, list):
            instance = instances[0]
        else:
            instance = instances
        
        # DEBUG: Выводим все доступные поля
        print_safe(f"\nDEBUG: Все доступные поля инстанса:")
        for key, value in instance.items():
            if key in ["ssh_host", "ssh_port", "ssh_user", "public_ipaddr", "ip_now", "ssh_idx", "intended_status"]:
                print_safe(f"  {key}: {value}")
        
        # Приоритет: ssh_host (публичный) -> public_ipaddr -> ip_now
        ssh_host = instance.get("ssh_host") or instance.get("public_ipaddr") or instance.get("ip_now")
        ssh_port = instance.get("ssh_port", 22)
        ssh_user = instance.get("ssh_user", "root")
        
        # Если ssh_host выглядит как внутренний IP (начинается с 10., 172., 192.168.), 
        # пытаемся найти публичный хост
        if ssh_host and (ssh_host.startswith("10.") or ssh_host.startswith("172.") or ssh_host.startswith("192.168.")):
            # Проверяем есть ли ssh_host в формате vast.ai
            if "ssh_host" in instance and "vast.ai" in str(instance.get("ssh_host", "")):
                ssh_host = instance.get("ssh_host")
            else:
                print_safe(f"⚠ Обнаружен внутренний IP {ssh_host}, ищу публичный хост...")
                # Пробуем альтернативные поля
                for field in ["intended_status", "public_ipaddr", "ssh_idx"]:
                    if field in instance:
                        print_safe(f"  DEBUG: {field} = {instance.get(field)}")
        
        if not ssh_host:
            print_safe("❌ Не удалось получить IP адрес инстанса")
            stop_and_delete(instance_id)
            sys.exit(1)
        
        print_safe(f"\n🔌 SSH: {ssh_user}@{ssh_host}:{ssh_port}")
        
        # Ждём готовности SSH
        if not wait_ssh_ready(ssh_host, ssh_user, ssh_port, timeout=300, interval=10):
            print_safe("❌ SSH так и не стал доступен, удаляю инстанс...")
            stop_and_delete(instance_id)
            sys.exit(1)
        
        # ===== НАСТРОЙКА ДООБУЧЕНИЯ =====
        print_safe("\n" + "="*50)
        print_safe("ПОДГОТОВКА К ДООБУЧЕНИЮ МОДЕЛИ")
        print_safe("="*50)
        
        # 1. Установка окружения
        setup_training_environment(ssh_host, ssh_user, ssh_port)
        
        # 2. Загрузка скрипта дообучения
        upload_training_script(ssh_host, ssh_user, ssh_port)
        
        # 3. Загрузка данных (если они есть)
        data_file = "data/sample_training_data.jsonl"  # Укажи путь к своему датасету
        if os.path.exists(data_file):
            upload_training_data(ssh_host, ssh_user, ssh_port, data_file)
        else:
            print_safe(f"⚠ Файл данных {data_file} не найден, пропускаю загрузку")
        
        # 4. Запуск дообучения
        print_safe("\n" + "="*50)
        print_safe("ЗАПУСК ДООБУЧЕНИЯ (это может занять несколько часов)")
        print_safe("="*50)
        start_training(ssh_host, ssh_user, ssh_port)
        
        # 5. Загрузка обученной модели
        print_safe("\n" + "="*50)
        print_safe("ЗАГРУЗКА ОБУЧЕННОЙ МОДЕЛИ")
        print_safe("="*50)
        output_dir = os.path.join(os.getcwd(), "output")
        model_path = download_trained_model(ssh_host, ssh_user, ssh_port, output_dir)
        
        if model_path:
            print_safe(f"\n✓ Дообучение завершено!")
            print_safe(f"✓ Модель сохранена в: {model_path}")
            print_safe(f"✓ Используй для инференса: AutoPeftModelForCausalLM.from_pretrained('{model_path}')")
        
        # 6. Очистка
        t = threading.Timer(30, stop_and_delete, args=(instance_id,))
        print_safe(f"\n⏰ Инстанс будет удалён через 30 секунд...")
        t.start()
        
        try:
            while t.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            print_safe("\n👋 Прерывание пользователем...")
            t.cancel()
            stop_and_delete(instance_id)
    else:
        print_safe("❌ Инстанс не запустился")
        stop_and_delete(instance_id)
        sys.exit(1)