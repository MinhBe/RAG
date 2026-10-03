from __future__ import annotations

import random
import re
from collections.abc import Sequence
from dataclasses import dataclass

WORD_POOL = {
    "a": ["anchor", "atlas", "amber", "autumn"],
    "b": ["bridge", "breeze", "beacon", "branch"],
    "c": ["cloud", "comet", "crystal", "compass"],
    "d": ["dragon", "delta", "dream", "diamond"],
    "e": ["eagle", "ember", "engine", "echo", "eclipse"],
    "f": ["forest", "flame", "falcon", "frost"],
    "g": ["garden", "galaxy", "giant", "glacier"],
    "h": ["harbor", "horizon", "hammer", "hero"],
    "i": ["island", "ivory", "icon", "iron"],
    "j": ["jungle", "jewel", "jacket", "journey"],
    "k": ["kingdom", "kite", "kernel", "keeper"],
    "l": ["lemon", "ladder", "lantern", "logic"],
    "m": ["mountain", "matrix", "meadow", "moon"],
    "n": ["nebula", "native", "nectar", "night"],
    "o": ["ocean", "orbit", "olive", "oracle"],
    "p": ["planet", "pulse", "pioneer", "pattern"],
    "r": ["river", "rocket", "raven", "radar"],
    "s": ["silver", "shadow", "storm", "signal"],
    "t": ["tiger", "tower", "thread", "tunnel"],
    "w": ["window", "winter", "wizard", "water"],
    "x": ["xenon", "xylem", "xavier", "xeric"],
    "y": ["yellow", "youth", "year", "yonder"],
}
DEFAULT_START_WORDS = ["apple", "ocean", "river", "garden", "silver"]
WORD_RE = re.compile(r"^[A-Za-z]{2,32}$")


@dataclass(frozen=True)
class WordChainTurn:
    index: int
    bot_username: str
    word: str
    previous_word: str | None
    next_bot_username: str | None
    is_final: bool

    def render(self) -> str:
        if self.is_final:
            return f"{self.word}\nChain complete: {self.index} turns."
        return f"{self.word} @{self.next_bot_username}"


def _last_letter(word: str) -> str:
    return word[-1].lower()


def _normalise_word(value: str | None) -> str:
    if value is None or not value.strip():
        return random.choice(DEFAULT_START_WORDS)
    word = value.strip().lower()
    if not WORD_RE.match(word):
        raise ValueError("Start word must be a single English alphabetic word, 2-32 letters.")
    if _last_letter(word) not in WORD_POOL:
        raise ValueError(
            f"No local word pool for words starting with '{_last_letter(word)}'. Choose another start word."
        )
    return word


def _choose_next_bot(current: str, bots: Sequence[str], visited: set[str]) -> str:
    unvisited = [bot for bot in bots if bot not in visited and bot != current]
    if unvisited:
        return random.choice(unvisited)
    choices = [bot for bot in bots if bot != current] or list(bots)
    return random.choice(choices)


def _choose_next_word(previous: str, used_words: set[str]) -> str:
    key = _last_letter(previous)
    pool = WORD_POOL.get(key, [])
    if not pool:
        raise ValueError(f"No local English word starts with '{key}'.")
    candidates = [word for word in pool if word not in used_words]
    return random.choice(candidates or pool)


def build_word_chain(
    start_bot_username: str,
    bot_usernames: Sequence[str],
    start_word: str | None = None,
    target_length: int = 10,
) -> list[WordChainTurn]:
    if target_length < 1:
        raise ValueError("target_length must be positive")
    bots = list(dict.fromkeys(bot_usernames))
    if start_bot_username not in bots:
        bots.insert(0, start_bot_username)
    word = _normalise_word(start_word)
    turns: list[WordChainTurn] = []
    used_words = {word}
    visited = {start_bot_username}
    current_bot = start_bot_username
    previous_word: str | None = None
    for index in range(1, target_length + 1):
        is_final = index == target_length
        next_bot = None if is_final else _choose_next_bot(current_bot, bots, visited)
        turns.append(
            WordChainTurn(
                index=index,
                bot_username=current_bot,
                word=word,
                previous_word=previous_word,
                next_bot_username=next_bot,
                is_final=is_final,
            )
        )
        if is_final:
            break
        previous_word = word
        current_bot = next_bot or current_bot
        visited.add(current_bot)
        word = _choose_next_word(previous_word, used_words)
        used_words.add(word)
    return turns
