import unittest

from domain import SEED_SCRIPT, compile_shots, extract_assets, natural_key, parse_script, serialize_script, srt_for, utf16_index


FIXTURES = [
    "", "\n", "\r\n\r\n", "\ufeff第1集\r\n", "  第2集 空白  \n\n", "第1集\n1-1 日 外 湖畔\n",
    "1-2 夜 内 书房\r\n人物：甲、乙\r\n", "人物:甲,乙，丙；丁\n", "△  落雨。 \n", "[00:02] 甲（疲惫）：你好。\n",
    "[01:20] 旁白（画外）：往事。\r\n", "[00:04] 甲：无情绪台词\n", "[00:04] 甲(低声):半角标点\n", "甲（坚定）：无时间码\n",
    "注：用户自定义内容\n# 未知段落\n", "【场1 春·公寓 玄关】\n", "[12:59] 甲：长视频\n", "[00:77] 甲：坏时间码\n",
    "△ 😀风吹过\r\n\t保留缩进\r\n", "第1集\n1-1 清晨 外 青云宗\n人物：甲\n[00:00] 甲：你好。",
]


class DomainTests(unittest.TestCase):
    def test_example_metrics(self):
        stats = parse_script(SEED_SCRIPT)["stats"]
        self.assertEqual((stats["scenes"], stats["dialogues"], stats["timed"]), (3, 6, 6))
        self.assertEqual(stats["issues"], [])

    def test_ids_survive_insertion(self):
        before = parse_script("△ 甲走来\n[00:01] 甲：你好。\n")
        after = parse_script("\n△ 甲走来\n[00:01] 甲：你好。\n", before["nodes"])
        self.assertEqual(before["nodes"][1]["id"], after["nodes"][2]["id"])

    def test_edited_line_keeps_identity(self):
        before = parse_script("[00:01] 甲：你好。\n")
        after = parse_script("[00:01] 甲：再见。\n", before["nodes"])
        self.assertEqual(before["nodes"][0]["id"], after["nodes"][0]["id"])

    def test_time_regression_is_reported(self):
        ast = parse_script("1-1 日 外 街\n[00:04] 甲：a\n[00:02] 乙：b\n")
        self.assertTrue(any("早于" in issue["message"] for issue in ast["stats"]["issues"]))

    def test_compile_source_trace(self):
        ast = parse_script(SEED_SCRIPT)
        shots = compile_shots(ast,"chapter",3,[],"国漫")
        self.assertEqual(len(shots),9)
        ids = {n["id"] for n in ast["nodes"]}
        self.assertTrue(all(set(s["source_line_ids"]) <= ids and s["source_line_ids"] for s in shots))
        self.assertTrue(all(3<=s["duration"]<=8 and s["source_revision"]==3 for s in shots))

    def test_unicode_selection(self):
        value="甲😀乙"
        self.assertEqual(utf16_index(value,3),2)
        with self.assertRaises(ValueError):utf16_index(value,2)
        with self.assertRaises(ValueError):utf16_index(value,99)

    def test_extraction_ignores_mentions_in_dialogue(self):
        result=extract_assets(parse_script("1-1 日 外 街\n人物：甲\n[00:02] 甲：我听说路人乙在附近。\n"))
        self.assertEqual([a["name"] for a in result if a["type"]=="characters"],["甲"])

    def test_natural_episodes(self):
        files=["第10集.mp4","第2集.mp4","第01集.mp4"]
        self.assertEqual(sorted(files,key=natural_key),["第01集.mp4","第2集.mp4","第10集.mp4"])

    def test_metadata_is_not_a_dialogue(self):
        self.assertEqual(parse_script("备注：仅供导演参考\n")["nodes"][0]["type"],"unknown")

    def test_narrator_aliases_share_one_speaker(self):
        ast=parse_script("[00:01] 解说：过去。\n[00:04] narrator：现在。\n")
        self.assertEqual(ast["stats"]["speakers"],["旁白"])

    def test_subtitles_follow_duration(self):
        output=srt_for([{"duration":3,"dialogue":"你好","speaker":"甲"},{"duration":4.5,"dialogue":"再见","speaker":"乙"}])
        self.assertIn("00:00:03,000 --> 00:00:07,500",output)


def fixture_test(value):
    def test(self):
        self.assertEqual(serialize_script(parse_script(value)).encode("utf-8"),value.encode("utf-8"))
    return test


for index, fixture in enumerate(FIXTURES):
    setattr(DomainTests,f"test_lossless_{index+1:02d}",fixture_test(fixture))


if __name__ == "__main__":unittest.main()
