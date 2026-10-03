from itertools import pairwise

from app.core.word_chain_game import build_word_chain


def test_word_chain_has_target_length_and_uses_all_bots():
    bots = [
        "Swain_SubAgent_bot",
        "Shen_SubAgent_bot",
        "Garen_SubAgent_bot",
        "Kayn_SubAgent_bot",
    ]
    turns = build_word_chain("Swain_SubAgent_bot", bots, start_word="eye", target_length=50)
    assert len(turns) == 50
    assert {turn.bot_username for turn in turns} == set(bots)
    assert turns[0].word == "eye"
    for previous, current in pairwise(turns):
        assert current.word[0] == previous.word[-1]
    assert turns[-1].is_final is True
    assert turns[-1].next_bot_username is None


def test_word_chain_rejects_unsupported_start_word():
    try:
        build_word_chain("Swain_SubAgent_bot", ["Swain_SubAgent_bot"], start_word="quiz", target_length=50)
    except ValueError as exc:
        assert "No local word pool" in str(exc)
    else:
        raise AssertionError("Expected unsupported word-chain start to fail")
