import unittest

from model import run
from scenarios import cmd, config, end


class CommandLimitTests(unittest.TestCase):
    def setUp(self):
        self.prefix = [*config(1, [256, 0, 0, 0]), *[cmd(3, 2, 0)] * 63]
        self.replies = [cmd(0x83, 2, 0)] * 63

    def test_end_after_64_commands_succeeds(self):
        words = [*self.prefix, end(3)]
        self.assertEqual(run(words), (self.replies, (0, 0, 0), len(words)))

    def test_65th_command_is_rejected_at_header(self):
        words = [*self.prefix, cmd(2, 42, 1), (123, True), end(3)]
        self.assertEqual(run(words), (self.replies, (1, 7, 42), len(self.prefix) + 1))

    def test_malformed_65th_header_keeps_original_priority(self):
        words = [*self.prefix, cmd(0xee, 43, 0, False)]
        self.assertEqual(run(words), (self.replies, (1, 1, 43), len(words)))


if __name__ == '__main__':
    unittest.main()
