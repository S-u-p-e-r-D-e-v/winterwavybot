import json
import os
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
QUEUES_PATH = os.path.join(DATA_DIR, "queues.json")
LIVE_STATS_PATH = os.path.join(DATA_DIR, "live_stats.json")


def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def read_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        write_json(path, default)
        return default
    except json.JSONDecodeError:
        return default


def write_json(path: str, data: Any) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def init_seed_files() -> None:
    ensure_data_dir()
    # Initialize queues.json if missing
    if not os.path.exists(QUEUES_PATH):
        write_json(QUEUES_PATH, {})
    else:
        # Validate it's a dict
        data = read_json(QUEUES_PATH, {})
        if not isinstance(data, dict):
            write_json(QUEUES_PATH, {})

    # Initialize live_stats.json if missing
    default_stats: Dict[str, Any] = {
        "connected": False,
        "viewers": 0,
        "likes": 0,
        "last_comment": None,
        "last_gift": None,
        "updated_at": None,
        "tiktok_username": os.getenv("TIKTOK_USERNAME", "")
    }
    if not os.path.exists(LIVE_STATS_PATH):
        write_json(LIVE_STATS_PATH, default_stats)
    else:
        stats = read_json(LIVE_STATS_PATH, default_stats)
        if not isinstance(stats, dict):
            write_json(LIVE_STATS_PATH, default_stats)


# Queue helpers

def get_queues() -> Dict[str, List[str]]:
    ensure_data_dir()
    data = read_json(QUEUES_PATH, {})
    if not isinstance(data, dict):
        return {}
    # Normalize values to unique lists of strings
    normalized: Dict[str, List[str]] = {}
    for game, users in data.items():
        if isinstance(users, list):
            normalized[game] = sorted(list({str(u).strip(): None for u in users}.keys()))
        else:
            normalized[game] = []
    return normalized


def save_queues(queues: Dict[str, List[str]]) -> None:
    ensure_data_dir()
    # Normalize before writing
    normalized: Dict[str, List[str]] = {}
    for game, users in queues.items():
        if isinstance(users, list):
            normalized[str(game).strip()] = sorted(list({str(u).strip(): None for u in users}.keys()))
    write_json(QUEUES_PATH, normalized)


def add_to_queue(game: str, username: str) -> None:
    queues = get_queues()
    game_key = game.strip().lower()
    username_key = username.strip()
    users = set(queues.get(game_key, []))
    users.add(username_key)
    queues[game_key] = sorted(users)
    save_queues(queues)


def remove_from_queue(game: str, username: str) -> bool:
    queues = get_queues()
    game_key = game.strip().lower()
    username_key = username.strip()
    if game_key not in queues:
        return False
    if username_key not in queues[game_key]:
        return False
    queues[game_key] = [u for u in queues[game_key] if u != username_key]
    save_queues(queues)
    return True


def clear_queue(game: str) -> None:
    queues = get_queues()
    queues[game.strip().lower()] = []
    save_queues(queues)


# Live stats helpers

def get_live_stats() -> Dict[str, Any]:
    ensure_data_dir()
    stats = read_json(LIVE_STATS_PATH, {})
    if not isinstance(stats, dict):
        return {}
    return stats


def update_live_stats(partial: Dict[str, Any]) -> Dict[str, Any]:
    ensure_data_dir()
    stats = get_live_stats()
    if not isinstance(stats, dict):
        stats = {}
    stats.update(partial)
    write_json(LIVE_STATS_PATH, stats)
    return stats


# Initialize on import by default
init_seed_files()
