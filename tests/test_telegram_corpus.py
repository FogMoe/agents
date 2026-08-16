from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.telegram_corpus import (
    CorpusError,
    Message,
    flatten_text,
    load_messages,
    looks_pasted,
    profile,
    select_samples,
)


SELF = frozenset({"user1"})


def build_export(chats: list[dict]) -> dict:
    return {"chats": {"list": chats}}


def message(text: object, **overrides: object) -> dict:
    payload: dict = {"type": "message", "from_id": "user1", "date": "2026-01-01T00:00:00"}
    payload["text"] = text
    payload.update(overrides)
    return payload


def write_export(root: Path, chats: list[dict]) -> Path:
    path = root / "result.json"
    path.write_text(json.dumps(build_export(chats)), encoding="utf-8")
    return path


def sample(text: str, *, kinds: frozenset[str] = frozenset(), date: str = "2026-01-01T00:00:00") -> Message:
    return Message(
        chat="chat",
        date=date,
        text=text,
        entity_kinds=kinds,
        is_reply=False,
        edited=False,
        sender="user1",
    )


class FlattenTextTests(unittest.TestCase):
    def test_returns_plain_string_unchanged(self) -> None:
        self.assertEqual(flatten_text("你好"), ("你好", frozenset()))

    def test_joins_mixed_segments_and_collects_entity_kinds(self) -> None:
        text, kinds = flatten_text(
            ["看这个 ", {"type": "link", "text": "https://example.com"}, " 怎么样"]
        )
        self.assertEqual(text, "看这个 https://example.com 怎么样")
        self.assertEqual(kinds, frozenset({"link"}))

    def test_rejects_unexpected_shape(self) -> None:
        with self.assertRaisesRegex(CorpusError, "unexpected text field"):
            flatten_text(42)


class LooksPastedTests(unittest.TestCase):
    def test_short_handwritten_message_is_kept(self) -> None:
        self.assertFalse(looks_pasted("这个 bug 好烦"))

    def test_em_dash_marks_foreign_content(self) -> None:
        self.assertTrue(looks_pasted("这个功能——准确说是自动保存"))

    def test_markdown_bold_marks_foreign_content(self) -> None:
        self.assertTrue(looks_pasted("这是个**很有意思**的问题"))

    def test_very_long_message_is_treated_as_pasted(self) -> None:
        self.assertTrue(looks_pasted("字" * 200))

    def test_multi_paragraph_block_is_treated_as_pasted(self) -> None:
        self.assertTrue(looks_pasted("段落一\n" + "字" * 60 + "\n段落三"))


class LoadMessagesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_keeps_only_prose_written_by_the_owner(self) -> None:
        path = write_export(
            self.root,
            [
                {
                    "name": "chat",
                    "messages": [
                        message("留下这句"),
                        message("别人说的", from_id="user2"),
                        message("转发来的", forwarded_from="someone"),
                        message("/start"),
                        message(""),
                        message([{"type": "bot_command", "text": "/roll"}]),
                        message("🎉"),
                        {"type": "service", "text": "joined"},
                    ],
                }
            ],
        )

        messages, dropped = load_messages(path, SELF)

        self.assertEqual([m.text for m in messages], ["留下这句"])
        self.assertEqual(dropped["other_sender"], 1)
        self.assertEqual(dropped["forwarded"], 1)
        self.assertEqual(dropped["bot_command"], 1)
        self.assertEqual(dropped["media_only"], 1)
        self.assertEqual(dropped["structural_only"], 1)
        self.assertEqual(dropped["no_words"], 1)
        self.assertEqual(dropped["service"], 1)

    def test_excluded_chat_is_dropped_before_analysis(self) -> None:
        path = write_export(
            self.root,
            [
                {"name": "私密群", "messages": [message("敏感内容")]},
                {"name": "公开群", "messages": [message("普通内容")]},
            ],
        )

        messages, dropped = load_messages(path, SELF, frozenset({"私密群"}))

        self.assertEqual([m.text for m in messages], ["普通内容"])
        self.assertEqual(dropped["excluded_chat"], 1)

    def test_reports_when_no_message_matches_the_sender(self) -> None:
        path = write_export(self.root, [{"name": "chat", "messages": [message("hi")]}])

        with self.assertRaisesRegex(CorpusError, "no messages matched"):
            load_messages(path, frozenset({"user9"}))

    def test_rejects_export_without_chat_list(self) -> None:
        path = self.root / "result.json"
        path.write_text(json.dumps({"about": "partial export"}), encoding="utf-8")

        with self.assertRaisesRegex(CorpusError, "full account export"):
            load_messages(path, SELF)

    def test_rejects_invalid_json(self) -> None:
        path = self.root / "result.json"
        path.write_text("{not json", encoding="utf-8")

        with self.assertRaisesRegex(CorpusError, "invalid JSON"):
            load_messages(path, SELF)


class ProfileTests(unittest.TestCase):
    def test_counts_trailing_punctuation_and_casing(self) -> None:
        data = profile([sample("没有标点"), sample("有标点。"), sample("用 claude 写")])

        self.assertEqual(data["messages"], 3)
        self.assertAlmostEqual(data["punctuation"]["no_trailing_mark"], 2 / 3)
        self.assertAlmostEqual(data["punctuation"]["full_stop"], 1 / 3)
        self.assertAlmostEqual(data["latin"]["all_lowercase_share"], 1.0)

    def test_burst_ratio_uses_gaps_within_a_chat(self) -> None:
        data = profile(
            [
                sample("第一条", date="2026-01-01T00:00:00"),
                sample("第二条", date="2026-01-01T00:00:30"),
                sample("第三条", date="2026-01-01T01:00:00"),
            ]
        )

        self.assertAlmostEqual(data["rhythm"]["burst_within_60s"], 0.5)

    def test_rejects_empty_corpus(self) -> None:
        with self.assertRaisesRegex(CorpusError, "empty corpus"):
            profile([])


class SelectSamplesTests(unittest.TestCase):
    def test_drops_short_repeated_and_identifying_messages(self) -> None:
        messages = [
            sample("短"),
            sample("这条够长了应该可以留下来"),
            sample("重复出现的常用回复内容"),
            sample("重复出现的常用回复内容"),
            sample("重复出现的常用回复内容"),
            sample("带链接的一句话内容在这", kinds=frozenset({"link"})),
            sample("这个功能——是粘贴来的内容"),
        ]

        selected = [m.text for m in select_samples(messages)]

        self.assertEqual(selected, ["这条够长了应该可以留下来"])

    def test_spreads_candidates_across_length_buckets(self) -> None:
        messages = [sample(f"中等长度的句子编号{i:02d}") for i in range(60)]
        messages += [sample("长" * 40 + f"{i:02d}") for i in range(60)]

        selected = select_samples(messages, per_bucket=5)

        short = [m for m in selected if len(m.text) <= 30]
        long = [m for m in selected if len(m.text) > 30]
        self.assertEqual(len(short), 5)
        self.assertEqual(len(long), 5)


if __name__ == "__main__":
    unittest.main()
