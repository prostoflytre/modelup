import requests
import time
import threading
import sys
import json
import subprocess
import os, re
import base64
import argparse
from urllib.parse import urljoin
from dotenv import load_dotenv

# ---------- Конфигурация ----------
# Загрузка переменных окружения из .env файла
load_dotenv()

BEARER_TOKEN = os.getenv("VAST_AI_TOKEN")

if not BEARER_TOKEN:
    print("⚠ VAST_AI_TOKEN не найден в .env файле")
    print("Для получения токена:")
    print(" 1. Перейдите на https://console.vast.ai/")
    print(" 2. Войдите в аккаунт")
    print(" 3. Перейдите в Account -> API Key")
    print(" 4. Скопируйте ваш API токен")
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

LIFETIME_SECONDS = 36000

# Optional SSH identity file (private key). Can be set via --ssh-key.
SSH_IDENTITY_FILE = None

# True if the configured SSH private key appears to be encrypted (passphrase-protected).
SSH_KEY_ENCRYPTED = False

# If True, the script will try to upload the corresponding public key to Vast
# before attempting SSH (when --ssh-key is provided).
AUTO_UPLOAD_SSH_KEY = True

# Used to categorize the most recent SSH failure for decision-making.
LAST_SSH_ERROR = None


def print_safe(*args, **kwargs):
    text = " ".join(str(a) for a in args)
    enc = sys.stdout.encoding or "utf-8"
    safe = text.encode(enc, errors="replace").decode(enc)
    print(safe, **kwargs)


def make_api_request(endpoint, method="GET", params=None, json_data=None, retry_count=3):
    """Функция запросов с ретраями"""
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
                    return response.json()
                except json.JSONDecodeError:
                    return {"_raw_html": response.text[:2000], "_status_code": response.status_code}
            else:
                return {"_empty_response": True, "_status_code": response.status_code}

        except requests.exceptions.RequestException as e:
            print_safe(f"Попытка {attempt + 1} не удалась: {e}")
            if attempt < retry_count - 1:
                time.sleep(2)
            else:
                return None


def _normalize_ssh_public_key(key_text: str) -> str:
    """Normalize a public key to the stable '<type> <base64>' form."""
    if not key_text:
        return ""
    parts = str(key_text).strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return str(key_text).strip()


def _read_public_key_for_identity(identity_path: str) -> str:
    """Best-effort: derive/read the public key text for a given private key path."""
    if not identity_path:
        raise ValueError("identity_path is empty")

    path = os.path.expanduser(identity_path)
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    # If user passed a .pub directly
    if path.lower().endswith(".pub"):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    pub_path = path + ".pub"
    if os.path.exists(pub_path):
        with open(pub_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    # Fallback: derive via ssh-keygen
    try:
        proc = subprocess.run(
            ["ssh-keygen", "-y", "-f", path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip().splitlines()[0].strip()
        raise RuntimeError(proc.stderr.strip() or "ssh-keygen failed")
    except FileNotFoundError as e:
        raise RuntimeError(
            "ssh-keygen не найден. Укажи публичный ключ как файл .pub или установи OpenSSH клиент (ssh-keygen)."
        ) from e


def _is_openssh_private_key_encrypted(private_key_path: str):
    """Return True/False if we can detect encryption, otherwise None."""
    if not private_key_path:
        return None
    path = os.path.expanduser(private_key_path)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except Exception:
        return None

    if "BEGIN OPENSSH PRIVATE KEY" not in text:
        return None

    # OpenSSH private key is base64 between header/footer.
    lines = [ln.strip() for ln in text.splitlines()]
    b64_lines = []
    in_blob = False
    for ln in lines:
        if ln.startswith("-----BEGIN OPENSSH PRIVATE KEY-----"):
            in_blob = True
            continue
        if ln.startswith("-----END OPENSSH PRIVATE KEY-----"):
            break
        if in_blob and ln and not ln.startswith("-----"):
            b64_lines.append(ln)

    if not b64_lines:
        return None

    try:
        blob = base64.b64decode("".join(b64_lines))
    except Exception:
        return None

    magic = b"openssh-key-v1\x00"
    if not blob.startswith(magic):
        return None

    # Parse the first cstring after magic: ciphername
    idx = len(magic)

    def read_cstring(buf, start):
        if start + 4 > len(buf):
            return None, start
        n = int.from_bytes(buf[start:start+4], "big")
        start += 4
        if start + n > len(buf):
            return None, start
        s = buf[start:start+n]
        start += n
        return s, start

    ciphername, idx = read_cstring(blob, idx)
    if ciphername is None:
        return None

    # If ciphername != b"none", the key is encrypted.
    return ciphername != b"none"


def vast_list_ssh_keys():
    """GET /api/v0/ssh/ -> list of keys."""
    data = make_api_request("ssh", method="GET")
    if data is None:
        return None
    if isinstance(data, list):
        return data
    # Be tolerant to possible wrappers
    if isinstance(data, dict):
        return data.get("keys") or data.get("ssh_keys") or data.get("data") or []
    return []


def vast_create_ssh_key(pubkey_text: str):
    """POST /api/v0/ssh/ with {ssh_key: <pub>}"""
    return make_api_request("ssh", method="POST", json_data={"ssh_key": pubkey_text})


def ensure_vast_has_ssh_key_text(pubkey_text: str) -> bool:
    """Ensure provided SSH public key text exists in Vast account."""
    pub = (pubkey_text or "").strip()
    pub_norm = _normalize_ssh_public_key(pub)
    if not pub_norm:
        print_safe("❌ Пустой SSH public key")
        return False

    keys = vast_list_ssh_keys()
    if keys is None:
        print_safe("❌ Не удалось получить список SSH ключей из Vast API")
        return False

    for k in keys:
        if isinstance(k, dict):
            existing = k.get("key") or k.get("public_key") or ""
        else:
            existing = str(k)
        if _normalize_ssh_public_key(existing) == pub_norm:
            print_safe("✓ SSH public key уже добавлен в Vast аккаунт")
            return True

    print_safe("➕ Добавляю SSH public key в Vast аккаунт...")
    res = vast_create_ssh_key(pub)
    if not res:
        print_safe("❌ Vast API не вернул ответ при добавлении SSH ключа")
        return False
    if isinstance(res, dict) and res.get("success") is True:
        print_safe("✓ SSH key добавлен в Vast")
        return True
    if isinstance(res, dict) and ("key" in res or "id" in res):
        print_safe("✓ SSH key добавлен в Vast")
        return True

    print_safe(f"⚠ Неожиданный ответ при добавлении SSH ключа: {str(res)[:400]}")
    return False


def ensure_vast_has_ssh_key(identity_path: str) -> bool:
    """Ensure the public key for identity_path exists in Vast account."""
    pub = _read_public_key_for_identity(identity_path)
    pub_norm = _normalize_ssh_public_key(pub)
    if not pub_norm:
        print_safe("❌ Не удалось получить public key из указанного --ssh-key")
        return False

    keys = vast_list_ssh_keys()
    if keys is None:
        print_safe("❌ Не удалось получить список SSH ключей из Vast API")
        return False

    for k in keys:
        if isinstance(k, dict):
            existing = k.get("key") or k.get("public_key") or ""
        else:
            existing = str(k)
        if _normalize_ssh_public_key(existing) == pub_norm:
            print_safe("✓ SSH public key уже добавлен в Vast аккаунт")
            return True

    print_safe("➕ Добавляю SSH public key в Vast аккаунт...")
    res = vast_create_ssh_key(pub)
    if not res:
        print_safe("❌ Vast API не вернул ответ при добавлении SSH ключа")
        return False
    if isinstance(res, dict) and res.get("success") is True:
        print_safe("✓ SSH key добавлен в Vast")
        return True

    # Some API responses may not include 'success' but still return created key.
    if isinstance(res, dict) and ("key" in res or "id" in res):
        print_safe("✓ SSH key добавлен в Vast")
        return True

    print_safe(f"⚠ Неожиданный ответ при добавлении SSH ключа: {str(res)[:400]}")
    return False


# ---------- CDI/GPU error detection helpers ----------
def _flatten_to_text(obj, limit=20000):
    """Собрать все строки/значения из вложенного JSON в один текст для поиска ошибок."""
    out = []

    def walk(x):
        if x is None:
            return
        if isinstance(x, (str, int, float, bool)):
            out.append(str(x))
            return
        if isinstance(x, dict):
            for k, v in x.items():
                out.append(str(k))
                walk(v)
            return
        if isinstance(x, list):
            for v in x:
                walk(v)
            return
        out.append(str(x))

    walk(obj)
    text = " ".join(out)
    return text[:limit]


_CDI_REGEXES = [
    re.compile(r"failed to inject cdi devices", re.IGNORECASE),
    re.compile(r"unresolvable cdi devices", re.IGNORECASE),
    re.compile(r"error modifying oci spec", re.IGNORECASE),
    re.compile(r"could not apply required modification to oci specification", re.IGNORECASE),
    # Твой конкретный формат:
    re.compile(r"unresolvable cdi devices\s+d\.[0-9a-f]+/gpu=\d+:\s*unknown", re.IGNORECASE),
    re.compile(r"d\.[0-9a-f]+/gpu=\d+:\s*unknown", re.IGNORECASE),
]

def looks_like_cdi_gpu_error(obj):
    """
    obj может быть dict/str.
    Возвращает (True/False, matched_regex_pattern, excerpt).
    """
    if isinstance(obj, str):
        text = obj
    else:
        text = _flatten_to_text(obj, limit=200000)

    for rx in _CDI_REGEXES:
        m = rx.search(text)
        if m:
            start = max(0, m.start() - 200)
            end = min(len(text), m.end() + 200)
            excerpt = text[start:end]
            return True, rx.pattern, excerpt
    return False, None, None

def looks_like_registry_dns_error(obj):
    text = _flatten_to_text(obj, limit=50000).lower()
    needles = [
        "lookup registry-1.docker.io: no such host",
        "dial tcp: lookup registry-1.docker.io: no such host",
        "failed to resolve reference",
        "registry-1.docker.io/v2/",
    ]
    return any(n in text for n in needles)


def get_instance_payload(instance_id):
    return make_api_request(f"instances/{instance_id}")


def get_instance_ssh_details(instance_id):
    """Получить ssh_host/ssh_port/ssh_user для существующего инстанса"""
    result = get_instance_payload(instance_id)
    if not result:
        print_safe("❌ Пустой ответ от API при запросе инстанса")
        return None

    instances = result.get("instances") or result.get("contract") or result
    instance = instances[0] if isinstance(instances, list) and instances else instances

    if not isinstance(instance, dict):
        print_safe("❌ Неожиданный формат ответа instances")
        return None

    ssh_host = instance.get("ssh_host") or instance.get("public_ipaddr") or instance.get("ip_now")
    ssh_port = instance.get("ssh_port", 22)
    ssh_user = instance.get("ssh_user", "root")

    status = instance.get("actual_status") or instance.get("cur_state") or instance.get("status", "unknown")
    print_safe(f"DEBUG: instance status = {status}")

    if not ssh_host:
        print_safe("❌ Не удалось получить ssh_host/public_ipaddr/ip_now")
        print_safe(f"DEBUG: keys = {list(instance.keys())}")
        return None

    return ssh_host, ssh_user, ssh_port, instance, result


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
    result = make_api_request("bundles", params={"q": f"id={bundle_id}"})
    if result and "offers" in result and result["offers"]:
        offer = result["offers"][0]
        print_safe(f"✓ Bundle найден: {offer.get('gpu_name')} - ${offer.get('dph_total')}/ч")
        print_safe(f" Доступность: {offer.get('onstart', 'unknown')}")
        print_safe(f" Min Bid: ${offer.get('min_bid', 'unknown')}")
        return True
    else:
        print_safe("✗ Bundle не найден или недоступен")
        return False


def find_cheapest_offers(gpu_name="RTX 5090", limit=20, max_price=None):
    """Находит несколько самых дешёвых офферов"""
    params = {
        "gpu_name": gpu_name,
        "limit": limit * 2,
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
        price = offer.get("dph_total", float("inf"))

        if max_price is not None and price > max_price:
            continue
        if offer.get("gpu_name") != gpu_name:
            continue

        print_safe(f"Найден оффер: {offer.get('gpu_name')} — ${price:.4f}/ч (id={offer.get('id')})")
        result.append(
            {
                "id": offer.get("id"),
                "ask_contract_id": offer.get("ask_contract_id"),
                "bundle_id": offer.get("bundle_id"),
                "gpu_name": offer.get("gpu_name"),
                "price": price,
            }
        )

        if len(result) >= limit:
            break

    if max_price is not None:
        print_safe(f"Найдено {len(result)} офферов в пределах ${max_price}/ч")

    return result


def create_instance(offer_ids, image="python:3.10", disk=10, label="auto-instance", runtype="ssh"):
    """
    Returns:
      (instance_id, err_code, raw_result)

    err_code:
      None            - успех
      "NO_SUCH_ASK"   - оффер исчез
      "REGISTRY_DNS"  - на хосте нет DNS до docker.io (pull невозможен)
            "CDI_GPU"       - unresolvable CDI devices gpu=0 unknown (host/runtime issue)
      "RAW_HTML"      - сервер вернул HTML вместо JSON
      "EMPTY"         - пустой ответ
      "OTHER"         - прочая ошибка
    """
    if isinstance(offer_ids, dict):
        bundle_id = offer_ids.get("bundle_id")
        ask_id = offer_ids.get("id")  # это же ask_contract_id
    else:
        ask_id = offer_ids
        bundle_id = offer_ids

    print_safe(f"Создаю инстанс: ask_id={ask_id}, bundle_id={bundle_id}…")

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

    endpoints_to_try = [
        ("put", f"asks/{ask_id}"),
        ("put", f"asks/{bundle_id}"),
        ("post", "instances"),
    ]

    result = None
    for endpoint_method, endpoint in endpoints_to_try:
        for payload in payloads_to_try:
            print_safe(f"Пытаюсь {endpoint_method.upper()} на /{endpoint}...")
            result = make_api_request(endpoint, method=endpoint_method, json_data=payload)

            # 1) Пусто
            if not result:
                continue

            # 2) Vast иногда возвращает HTML вместо JSON
            if "_raw_html" in result:
                if looks_like_registry_dns_error(result):
                    print_safe("🚫 Похоже на DNS проблему хоста: registry-1.docker.io не резолвится")
                    return None, "REGISTRY_DNS", result
                print_safe("✗ Сервер вернул HTML вместо JSON")
                return None, "RAW_HTML", result

            # 3) Оффер исчез
            if result.get("error") == "invalid_args" and "no_such_ask" in result.get("msg", ""):
                print_safe(f"⚠ Оффер недоступен (no_such_ask): {result.get('msg')}")
                return None, "NO_SUCH_ASK", result

            # 4) Ловим ошибку registry DNS по msg/error если она туда попала
            if looks_like_registry_dns_error(result):
                print_safe("🚫 DNS проблема хоста при pull образа (registry-1.docker.io: no such host)")
                return None, "REGISTRY_DNS", result

            # 4.5) Ловим CDI/GPU injection проблему (OCI spec / failed to inject CDI devices)
            is_cdi, pat, excerpt = looks_like_cdi_gpu_error(result)
            if is_cdi:
                print_safe(f"🚫 CDI/GPU error detected during create (pattern={pat})")
                if excerpt:
                    print_safe(f"DEBUG excerpt: {excerpt}")
                return None, "CDI_GPU", result

            # 5) Успешный/обещающий ответ
            if result.get("success") is not None:
                if result.get("success") or "id" in result or "new_contract" in result:
                    print_safe(f"✓ Получен обещающий ответ от /{endpoint}")
                    # выходим из обоих циклов
                    endpoint_method = None
                    break

        if endpoint_method is None:
            break

    if not result:
        print_safe("✗ Пустой ответ от сервера")
        return None, "EMPTY", None

    print_safe(f"DEBUG: Ответ на создание инстанса: {json.dumps(result, indent=2)[:500]}")

    instance_id = result.get("new_contract") or result.get("id") or result.get("contract_id") or result.get("instance_id")
    if instance_id:
        print_safe(f"✓ Инстанс создан, ID = {instance_id}")
        return instance_id, None, result

    if "id" in result:
        instance_id = result.get("id")
        print_safe(f"✓ Инстанс создан(?), ID = {instance_id}")
        return instance_id, None, result

    # На всякий: если сюда дошли и это всё же registry DNS — отметим правильно
    if looks_like_registry_dns_error(result):
        return None, "REGISTRY_DNS", result

    print_safe("✗ Не удалось получить ID инстанса. Ответ сервера:")
    print_safe(json.dumps(result, indent=2))
    return None, "OTHER", result



def wait_for_instance(instance_id, timeout=180, interval=10):
    print_safe(f"Ожидание запуска инстанса {instance_id}...")
    deadline = time.time() + timeout

    while time.time() < deadline:
        time.sleep(interval)

        result = get_instance_payload(instance_id)
        if not result:
            print_safe("⚠ Пустой ответ от сервера")
            continue

        instance = result.get("instances") or result.get("contract") or result
        if isinstance(instance, list) and instance:
            instance = instance[0]

        if isinstance(instance, dict):
            status = instance.get("actual_status") or instance.get("cur_state") or instance.get("status", "unknown")
            print_safe(f"DEBUG: Статус = {status}, доступные ключи инстанса: {list(instance.keys())}")

            if status == "exited" or status == "error" or "error" in str(status).lower():
                print_safe(f"✗ Инстанс завершился с ошибкой: {status}")

                payload = {"instance": instance, "raw": result}
                is_cdi, pat, excerpt = looks_like_cdi_gpu_error(payload)
                if is_cdi:
                    print_safe(f"🚫 CDI/GPU error detected (pattern={pat})")
                    if excerpt:
                        print_safe(f"DEBUG excerpt: {excerpt}")

                return False

            ssh_host = instance.get("ssh_host") or instance.get("public_ipaddr") or instance.get("ip_now")
            if ssh_host:
                ssh_user = instance.get("ssh_user", "root")
                ssh_port = instance.get("ssh_port", 22)
                ssh_command = f"ssh {ssh_user}@{ssh_host} -p {ssh_port}"

                print_safe("\n" + "=" * 50)
                print_safe("✓ ИНСТАНС ГОТОВ К РАБОТЕ!")
                print_safe(f"Команда SSH: {ssh_command}")
                print_safe("=" * 50)
                return True

            print_safe(f"Статус: {status}...")
        else:
            print_safe("⚠ Не удалось получить статус инстанса")
            print_safe(f" Полный ответ: {json.dumps(result, indent=2)[:500]}")

    print_safe("✗ Инстанс не запустился в отведённое время")
    return False


def stop_and_delete(instance_id):
    """Остановка и удаление инстанса"""
    print_safe(f"Останавливаю и удаляю инстанс {instance_id}...")

    # stop (retry)
    stop_ok = False
    for attempt in range(3):
        stop_result = make_api_request(f"instances/{instance_id}/stop", method="POST")
        if stop_result:
            stop_ok = True
            print_safe("✓ Инстанс остановлен (запрос принят)")
            break
        print_safe(f"⚠ Не удалось остановить инстанс (попытка {attempt+1}/3)")
        time.sleep(3)

    time.sleep(5)

    # delete (retry)
    for attempt in range(5):
        delete_result = make_api_request(f"instances/{instance_id}", method="DELETE")
        if delete_result:
            print_safe("✓ Инстанс удалён")
            return True

        payload = get_instance_payload(instance_id)
        if payload:
            inst = payload.get("instances") or payload.get("contract") or payload
            if isinstance(inst, list) and inst:
                inst = inst[0]
            if isinstance(inst, dict):
                status = inst.get("actual_status") or inst.get("cur_state") or inst.get("status", "unknown")
                print_safe(f"⚠ Удаление не удалось (попытка {attempt+1}/5), status={status}")
            else:
                print_safe(f"⚠ Удаление не удалось (попытка {attempt+1}/5)")
        else:
            print_safe(f"⚠ Удаление не удалось (попытка {attempt+1}/5)")

        time.sleep(4)

    print_safe("✗ Не удалось удалить инстанс после нескольких попыток")
    if not stop_ok:
        print_safe("⚠ Также не удалось корректно остановить инстанс")
    return False


def run_ssh_command(ssh_host, ssh_user, ssh_port, command):
    """Выполнить команду на инстансе через SSH"""
    ssh_args = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=NUL",
        "-o",
        "ConnectTimeout=10",
    ]

    if SSH_IDENTITY_FILE:
        ssh_args.extend([
            "-o",
            "IdentitiesOnly=yes",
            "-i",
            SSH_IDENTITY_FILE,
        ])

    ssh_args.extend([
        "-p",
        str(ssh_port),
        f"{ssh_user}@{ssh_host}",
        command,
    ])
    try:
        result = subprocess.run(ssh_args, capture_output=True, text=True, timeout=600)
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return None, "Command timeout", -1
    except Exception as e:
        return None, str(e), -1


def wait_ssh_ready(ssh_host, ssh_user, ssh_port, timeout=300, interval=5, instance_id=None):
    """Дождаться готовности SSH на инстансе"""
    print_safe(f"Жду готовности SSH {ssh_host}:{ssh_port}...")
    start_time = time.time()

    global LAST_SSH_ERROR
    LAST_SSH_ERROR = None

    consecutive_closed = 0

    while time.time() - start_time < timeout:
        stdout, stderr, code = run_ssh_command(ssh_host, ssh_user, ssh_port, "echo ok")
        if code == 0:
            print_safe(f"✓ SSH готов (ответ: {stdout.strip()})")
            return True
        else:
            elapsed = int(time.time() - start_time)
            print_safe(f"⏳ SSH не готов... ({elapsed}s) - {stderr}")

            # Fail fast on local key file permission errors (common on Windows OpenSSH).
            if isinstance(stderr, str) and ("UNPROTECTED PRIVATE KEY FILE" in stderr or "bad permissions" in stderr):
                LAST_SSH_ERROR = "BAD_KEY_PERMS"
                return False

            # Fail fast on auth errors: waiting longer won't help.
            if isinstance(stderr, str) and "Permission denied (publickey)" in stderr:
                LAST_SSH_ERROR = "PUBKEY_DENIED"
                return False

            # Частый кейс: TCP есть, но сервер сразу закрывает соединение.
            # Это бывает, когда инстанс ещё не поднялся, либо он уже упал (exited/error),
            # либо SSH не принимает ключи.
            if isinstance(stderr, str) and "Connection closed" in stderr:
                consecutive_closed += 1
            else:
                consecutive_closed = 0

            # Если несколько раз подряд "Connection closed" — проверим статус инстанса
            if instance_id and consecutive_closed >= 3:
                payload = get_instance_payload(instance_id)
                if payload:
                    # Даже если status ещё не обновился, CDI ошибка часто уже лежит в payload
                    is_cdi, pat, excerpt = looks_like_cdi_gpu_error(payload)
                    if is_cdi:
                        print_safe(f"🚫 CDI/GPU error detected (pattern={pat})")
                        if excerpt:
                            print_safe(f"DEBUG excerpt: {excerpt}")
                        return False

                    # Иногда проблема не в GPU, а в DNS до DockerHub на хосте (pull невозможен)
                    if looks_like_registry_dns_error(payload):
                        print_safe("🚫 DNS проблема хоста: registry-1.docker.io не резолвится (pull образа невозможен)")
                        return False

                    inst = payload.get("instances") or payload.get("contract") or payload
                    if isinstance(inst, list) and inst:
                        inst = inst[0]
                    if isinstance(inst, dict):
                        status = inst.get("actual_status") or inst.get("cur_state") or inst.get("status", "unknown")
                        if status in ("exited", "error") or "error" in str(status).lower():
                            print_safe(f"❌ SSH не поднимается, а инстанс уже в статусе: {status}")
                            is_cdi, pat, excerpt = looks_like_cdi_gpu_error({"instance": inst, "raw": payload})
                            if is_cdi:
                                print_safe(f"🚫 CDI/GPU error detected (pattern={pat})")
                                if excerpt:
                                    print_safe(f"DEBUG excerpt: {excerpt}")
                            return False

                            if looks_like_registry_dns_error(payload):
                                print_safe("🚫 DNS проблема хоста: registry-1.docker.io не резолвится (pull образа невозможен)")
                                return False

            time.sleep(interval)

    print_safe(f"❌ SSH не стал доступен за {timeout} секунд")
    return False


def setup_training_environment(ssh_host, ssh_user, ssh_port):
    """Установить зависимости для дообучения на инстансе"""
    print_safe(f"Настраиваю окружение на инстансе {ssh_host}...")

    # Keep this lean: avoid redundant apt steps and only "repair" apt if needed.
    setup_commands = [
        "apt-get update",
        "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 python3-pip git wget curl",
        "python3 -m pip install --upgrade pip",
        "python3 -m pip install -U transformers datasets peft bitsandbytes accelerate scikit-learn wandb",
        # Install torch only if missing (pytorch images already have it; cuda base images may not).
        "python3 -c \"import torch; print(torch.__version__)\" || python3 -m pip install -U torch",
        "mkdir -p /root/training",
    ]

    for cmd in setup_commands:
        print_safe(f"Выполняю: {cmd[:50]}...")
        for attempt in range(3):
            stdout, stderr, code = run_ssh_command(ssh_host, ssh_user, ssh_port, cmd)
            if code == 0:
                print_safe("✓ OK")
                break
            else:
                # If apt is broken, try a one-time repair path, then retry.
                if "apt-get" in cmd and attempt == 0:
                    repair = [
                        "dpkg --configure -a || true",
                        "apt-get -y --fix-broken install || true",
                        "apt-get update || true",
                    ]
                    for rcmd in repair:
                        print_safe(f"Выполняю repair: {rcmd[:50]}...")
                        run_ssh_command(ssh_host, ssh_user, ssh_port, rcmd)
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

    scp_args = [
        "scp",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=NUL",
    ]

    if SSH_IDENTITY_FILE:
        scp_args.extend([
            "-o",
            "IdentitiesOnly=yes",
            "-i",
            SSH_IDENTITY_FILE,
        ])

    scp_args.extend([
        "-P",
        str(ssh_port),
        script_file,
        f"{ssh_user}@{ssh_host}:/root/training/train.py",
    ])

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
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=NUL",
    ]

    if SSH_IDENTITY_FILE:
        scp_args.extend([
            "-o",
            "IdentitiesOnly=yes",
            "-i",
            SSH_IDENTITY_FILE,
        ])

    scp_args.extend([
        "-P",
        str(ssh_port),
        data_file,
        f"{ssh_user}@{ssh_host}:/root/training/data.jsonl",
    ])

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
    print_safe("Проверяю наличие обученной модели на инстансе...")

    check_cmd = "ls -la /root/training/"
    stdout, stderr, code = run_ssh_command(ssh_host, ssh_user, ssh_port, check_cmd)
    if code == 0:
        print_safe("Содержимое /root/training/:")
        print_safe(stdout)
    else:
        print_safe(f"✗ Ошибка при проверке директории: {stderr}")
        return None

    check_output_cmd = "ls -la /root/training/Mistral-lora-output/ 2>/dev/null || echo 'Directory not found'"
    stdout, stderr, code = run_ssh_command(ssh_host, ssh_user, ssh_port, check_output_cmd)
    print_safe(f"Содержимое выходной директории: {stdout}")

    if "Directory not found" in stdout or "No such file" in stdout:
        print_safe("✗ Модель не была сохранена - обучение завершилось с ошибкой")
        return None

    print_safe("Загружаю обученную модель с инстанса...")
    local_dir = os.path.join(output_dir, "Mistral-lora-model")
    os.makedirs(local_dir, exist_ok=True)

    scp_args = [
        "scp",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=NUL",
    ]

    if SSH_IDENTITY_FILE:
        scp_args.extend([
            "-o",
            "IdentitiesOnly=yes",
            "-i",
            SSH_IDENTITY_FILE,
        ])

    scp_args.extend([
        "-P",
        str(ssh_port),
        "-r",
        f"{ssh_user}@{ssh_host}:/root/training/Mistral-lora-output/*",
        f"{local_dir}/",
    ])

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

    parser = argparse.ArgumentParser(description="Vast.ai Auto Instance Manager")
    parser.add_argument("--attach", type=str, default=None, help="Подключиться к уже запущенному instance_id")
    parser.add_argument("--skip-setup", action="store_true", help="Не ставить зависимости на инстансе")
    parser.add_argument("--skip-upload", action="store_true", help="Не загружать train.py и data")
    parser.add_argument("--no-cleanup", action="store_true", help="Не удалять инстанс после завершения")
    parser.add_argument("--ssh-key", type=str, default=None, help="Путь к приватному SSH ключу (опционально)")
    parser.add_argument("--ssh-pubkey", type=str, default=None, help="SSH public key (строкой). Добавит ключ в Vast аккаунт перед запуском")
    parser.add_argument("--no-upload-ssh-key", action="store_true", help="Не загружать SSH public key в Vast (даже если указан --ssh-key)")
    parser.add_argument("--destroy", type=str, default=None, help="Остановить+удалить указанный instance_id и выйти")
    parser.add_argument("--continue-on-ssh-auth-failure", action="store_true", help="Продолжать перебор офферов, если SSH вернул Permission denied (publickey)")
    args = parser.parse_args()

    if args.ssh_key:
        # Users sometimes paste the .pub path by mistake; ssh -i must point to the PRIVATE key.
        key_path = os.path.expanduser(args.ssh_key)
        if key_path.lower().endswith(".pub"):
            candidate_private = key_path[:-4]
            if os.path.exists(candidate_private):
                print_safe(f"⚠ Указан .pub в --ssh-key; использую приватный ключ: {candidate_private}")
                key_path = candidate_private
        SSH_IDENTITY_FILE = key_path

        enc = _is_openssh_private_key_encrypted(SSH_IDENTITY_FILE)
        if enc is True:
            SSH_KEY_ENCRYPTED = True
            print_safe("⚠ ВНИМАНИЕ: приватный ключ выглядит зашифрованным (нужна passphrase).")
            print_safe("Скрипт использует BatchMode=yes, поэтому ввод passphrase невозможен.")
            print_safe("Решение: включи ssh-agent и добавь ключ: ssh-add C:/Users/Student/.ssh/id_ed25519")
        elif enc is False:
            SSH_KEY_ENCRYPTED = False
    if args.no_upload_ssh_key:
        AUTO_UPLOAD_SSH_KEY = False

    if args.destroy:
        if not check_api_connection():
            sys.exit(1)
        ok = stop_and_delete(args.destroy.strip())
        sys.exit(0 if ok else 2)

    if not check_api_connection():
        sys.exit(1)

    # Ensure SSH keys in Vast before attempting SSH.
    # According to Vast docs, keys are automatically added to all current instances as well.
    if AUTO_UPLOAD_SSH_KEY:
        try:
            if args.ssh_pubkey:
                ensure_vast_has_ssh_key_text(args.ssh_pubkey)
            elif SSH_IDENTITY_FILE:
                ensure_vast_has_ssh_key(SSH_IDENTITY_FILE)
        except Exception as e:
            print_safe(f"⚠ Не удалось обеспечить SSH key в Vast: {e}")

    # ===== ATTACH MODE =====
    if args.attach:
        instance_id = args.attach.strip()
        print_safe(f"🔗 Подключаюсь к существующему инстансу: {instance_id}")

        details = get_instance_ssh_details(instance_id)
        if not details:
            sys.exit(1)

        ssh_host, ssh_user, ssh_port, instance, raw = details
        print_safe(f"🔌 SSH: {ssh_user}@{ssh_host}:{ssh_port}")

        is_cdi, _, _ = looks_like_cdi_gpu_error({"instance": instance, "raw": raw})
        if is_cdi:
            print_safe("🚫 ВНИМАНИЕ: инстанс выглядит как проблемный по CDI/GPU. Возможно контейнер не стартует корректно.")

        if not wait_ssh_ready(ssh_host, ssh_user, ssh_port, timeout=300, interval=10, instance_id=instance_id):
            if LAST_SSH_ERROR == "PUBKEY_DENIED":
                print_safe("❌ SSH: Permission denied (publickey)")
                if SSH_KEY_ENCRYPTED:
                    print_safe("Ключ защищён passphrase; в BatchMode SSH не может спросить пароль.")
                    print_safe("Включи ssh-agent и добавь ключ: Start-Service ssh-agent; ssh-add C:/Users/Student/.ssh/id_ed25519")
                else:
                    print_safe("Проверь: публичный ключ (.pub) добавлен в Vast аккаунт, а инстанс создан ПОСЛЕ добавления ключа.")
                    print_safe("Также можно явно указать ключ: --ssh-key C:/Users/Student/.ssh/id_ed25519")
            elif LAST_SSH_ERROR == "BAD_KEY_PERMS":
                print_safe("❌ SSH: OpenSSH отклонил ключ из-за прав доступа (Windows)")
                print_safe("Исправить права на приватный ключ можно так (PowerShell):")
                print_safe("  icacls \"C:\\Users\\Student\\.ssh\\id_ed25519\" /inheritance:r")
                print_safe("  icacls \"C:\\Users\\Student\\.ssh\\id_ed25519\" /grant:r %USERNAME%:F")
                print_safe("  icacls \"C:\\Users\\Student\\.ssh\\id_ed25519\" /remove:g \"BUILTIN\\Users\" \"BUILTIN\\Administrators\" \"NT AUTHORITY\\SYSTEM\"")
            else:
                print_safe("❌ SSH не стал доступен")
            sys.exit(1)

        if not args.skip_setup:
            setup_training_environment(ssh_host, ssh_user, ssh_port)

        if not args.skip_upload:
            upload_training_script(ssh_host, ssh_user, ssh_port)
            data_file = "data/sample_training_data.jsonl"
            if os.path.exists(data_file):
                upload_training_data(ssh_host, ssh_user, ssh_port, data_file)
            else:
                print_safe(f"⚠ Файл данных {data_file} не найден, пропускаю загрузку")

        start_training(ssh_host, ssh_user, ssh_port)

        output_dir = os.path.join(os.getcwd(), "output")
        model_path = download_trained_model(ssh_host, ssh_user, ssh_port, output_dir)

        if model_path:
            print_safe(f"✓ Модель сохранена в: {model_path}")

        if not args.no_cleanup:
            stop_and_delete(instance_id)

        sys.exit(0)

    # ===== CREATE MODE (original flow) =====
    gpu_list = [ "RTX 5090", "Q RTX 8000", "RTX 6000Ada", "A4000", "RTX 5880Ada"]
    max_price = 0.5

    all_offers = []
    for gpu in gpu_list:
        print_safe(f"\nПоиск офферов для {gpu}...")
        offers = find_cheapest_offers(gpu_name=gpu, limit=20, max_price=max_price)
        all_offers.extend(offers)

    all_offers.sort(key=lambda x: x["price"])

    if not all_offers:
        print_safe(f"❌ Не найдено офферов в пределах ${max_price}/ч")
        sys.exit(1)

    print_safe(f"\n✓ Найдено {len(all_offers)} офферов для попытки (отсортировано по цене)")

    instance_id = None
    ssh_host = None
    ssh_port = None
    ssh_user = None

    images_to_try = [
        # Newer first; keep older tags as fallback.
        "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
        "nvidia/cuda:12.4.1-base-ubuntu22.04",
        "nvidia/cuda:12.2.2-base-ubuntu22.04",
        "nvidia/cuda:12.1.0-base-ubuntu22.04",
        "nvidia/cuda:11.8.0-base-ubuntu22.04",
    ]

    for i, offer_data in enumerate(all_offers, 1):

        print_safe(f"\n--- Попытка {i}/{len(all_offers)}: {offer_data['gpu_name']} @ ${offer_data['price']}/ч ---")

        # Если на конкретной машине/оффере ловим CDI/GPU injection проблему,
        # то дальнейший перебор image бессмысленен — сразу переходим к следующему офферу.
        cdi_bad_offer = False

        for image_idx, image in enumerate(images_to_try, 1):
            print_safe(f" Пробую образ {image_idx}/{len(images_to_try)}: {image}")

            instance_id, err, raw = create_instance(
                offer_ids=offer_data,
                image=image,
                disk=40,
                label="test-auto-instance",
            )

            if err == "REGISTRY_DNS":
                continue

            if err == "CDI_GPU":
                print_safe("↪ CDI/GPU ошибка на этом хосте — пропускаю остальные образы и перехожу к следующему офферу")
                cdi_bad_offer = True
                break

            if instance_id:
                print_safe(f"✓ Инстанс создан, ID = {instance_id}")

                if wait_for_instance(instance_id, timeout=60, interval=5):
                    print_safe(f"✓ Инстанс успешно запущен: {instance_id}")

                    # Получаем SSH детали и проверяем, что SSH реально поднимается.
                    instance_info = make_api_request(f"instances/{instance_id}")
                    if not instance_info:
                        print_safe("⚠ Не удалось получить детали инстанса для SSH, удаляю и пробую следующий...")
                        stop_and_delete(instance_id)
                        instance_id = None
                        continue

                    instances = instance_info.get("instances") or instance_info.get("contract") or instance_info
                    instance = instances[0] if isinstance(instances, list) else instances
                    if not isinstance(instance, dict):
                        print_safe("⚠ Неожиданный формат instance payload, удаляю и пробую следующий...")
                        stop_and_delete(instance_id)
                        instance_id = None
                        continue

                    ssh_host = instance.get("ssh_host") or instance.get("public_ipaddr") or instance.get("ip_now")
                    ssh_port = instance.get("ssh_port", 22)
                    ssh_user = instance.get("ssh_user", "root")

                    if ssh_host and (ssh_host.startswith("10.") or ssh_host.startswith("172.") or ssh_host.startswith("192.168.")):
                        if "ssh_host" in instance and "vast.ai" in str(instance.get("ssh_host", "")):
                            ssh_host = instance.get("ssh_host")
                        else:
                            print_safe(f"⚠ Обнаружен внутренний IP {ssh_host}, ищу публичный хост...")

                    if not ssh_host:
                        print_safe("❌ Не удалось получить IP адрес инстанса, удаляю и пробую следующий...")
                        stop_and_delete(instance_id)
                        instance_id = None
                        continue

                    print_safe(f"\n🔌 SSH: {ssh_user}@{ssh_host}:{ssh_port}")

                    if not wait_ssh_ready(ssh_host, ssh_user, ssh_port, timeout=300, interval=10, instance_id=instance_id):
                        payload = get_instance_payload(instance_id)
                        is_cdi, _, _ = looks_like_cdi_gpu_error(payload or {})
                        if payload and is_cdi:
                            print_safe("🚫 SSH не поднялся из-за CDI/GPU ошибки")
                            stop_and_delete(instance_id)
                            instance_id = None
                            cdi_bad_offer = True
                            break

                        if payload and looks_like_registry_dns_error(payload):
                            print_safe("🚫 SSH не поднялся из-за DNS до DockerHub")
                            stop_and_delete(instance_id)
                            instance_id = None
                            continue

                        if LAST_SSH_ERROR == "PUBKEY_DENIED":
                            print_safe("❌ SSH: Permission denied (publickey)")

                            if SSH_KEY_ENCRYPTED:
                                print_safe("Ключ защищён passphrase; в BatchMode SSH не может спросить пароль.")
                                print_safe("Включи ssh-agent и добавь ключ: Start-Service ssh-agent; ssh-add C:/Users/Student/.ssh/id_ed25519")
                            else:
                                print_safe("Проверь: Vast SSH Keys содержит твой .pub ключ, и этот инстанс создан после добавления ключа.")
                                print_safe("Можно явно указать ключ: --ssh-key C:/Users/Student/.ssh/id_ed25519")

                            stop_and_delete(instance_id)

                            instance_id = None
                            if args.continue_on_ssh_auth_failure:
                                print_safe("↪ Продолжаю перебор офферов (--continue-on-ssh-auth-failure)")
                                continue
                            break

                        print_safe("❌ SSH так и не стал доступен (не похоже на CDI). Останавливаю выполнение.")
                        stop_and_delete(instance_id)
                        sys.exit(1)

                    # SSH поднялся — выходим из циклов и продолжаем сценарий обучения.
                    break
                else:
                    print_safe("✗ Инстанс не запустился или завершился с ошибкой")
                    print_safe(" Удаляю проблемный инстанс...")

                    payload = get_instance_payload(instance_id)
                    is_cdi, _, _ = looks_like_cdi_gpu_error(payload or {})
                    if payload and is_cdi:
                        print_safe("🚫 CDI/GPU ошибка")
                        cdi_bad_offer = True

                    stop_and_delete(instance_id)
                    instance_id = None
            else:
                print_safe(f"✗ Не удалось создать инстанс с образом {image}")

            if cdi_bad_offer:
                break

        if instance_id:
            break
        elif cdi_bad_offer:
            print_safe("✗ Пропускаю этот оффер из-за CDI/GPU ошибки, пробую следующий...")
            continue
        else:
            print_safe("✗ Все образы не сработали для этого оффера, пробую следующий...")

    if not instance_id:
        print_safe("❌ Не удалось создать рабочий инстанс ни с одним оффером")
        sys.exit(1)

    # ===== НАСТРОЙКА ДООБУЧЕНИЯ =====
    print_safe("\n" + "=" * 50)
    print_safe("ПОДГОТОВКА К ДООБУЧЕНИЮ МОДЕЛИ")
    print_safe("=" * 50)

    setup_training_environment(ssh_host, ssh_user, ssh_port)
    upload_training_script(ssh_host, ssh_user, ssh_port)

    data_file = "data/sample_training_data.jsonl"
    if os.path.exists(data_file):
        upload_training_data(ssh_host, ssh_user, ssh_port, data_file)
    else:
        print_safe(f"⚠ Файл данных {data_file} не найден, пропускаю загрузку")

    print_safe("\n" + "=" * 50)
    print_safe("ЗАПУСК ДООБУЧЕНИЯ (это может занять несколько часов)")
    print_safe("=" * 50)

    start_training(ssh_host, ssh_user, ssh_port)

    print_safe("\n" + "=" * 50)
    print_safe("ЗАГРУЗКА ОБУЧЕННОЙ МОДЕЛИ")
    print_safe("=" * 50)

    output_dir = os.path.join(os.getcwd(), "output")
    model_path = download_trained_model(ssh_host, ssh_user, ssh_port, output_dir)

    if model_path:
        print_safe("\n✓ Дообучение завершено!")
        print_safe(f"✓ Модель сохранена в: {model_path}")
        print_safe("✓ Используй для инференса: AutoPeftModelForCausalLM.from_pretrained('<path>')")

    if args.no_cleanup:
        print_safe("\n⏰ Очистка отключена (--no-cleanup). Инстанс оставлен запущенным.")
        sys.exit(0)

    t = threading.Timer(30, stop_and_delete, args=(instance_id,))
    print_safe("\n⏰ Инстанс будет удалён через 30 секунд...")
    t.start()

    try:
        while t.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print_safe("\n👋 Прерывание пользователем...")
        t.cancel()
        stop_and_delete(instance_id)
