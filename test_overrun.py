from overrun import cmd, format_cmd
import unittest


class TestOverrun(unittest.TestCase):
    def test_simple(self):
        value = cmd('printf "%s\n" "Hello world"').read()
        self.assertEqual(value, 'Hello world')

    def test_value_interpolation(self):
        testing = 'Testing 123'
        value = cmd('printf "%s\n" {testing}').read()
        self.assertEqual(value, 'Testing 123')

    def test_value_interpolation_newline(self):
        testing = 'Testing\n123'
        value = cmd('printf "%s\n" {testing}').read()
        self.assertEqual(value, 'Testing\n123')

    def test_function_call(self):
        value = cmd('printf "%s\n" {"a".join("12345")}').read()
        self.assertEqual(value, '1a2a3a4a5')

    def test_bool_result(self):
        proc = cmd('ls /').run(silent=True)
        self.assertTrue(proc)

    def test_bool_result_fail(self):
        proc = cmd('ls /non_existent_directory').run(silent=True)
        self.assertFalse(proc)

    def test_shell_true(self):
        value = cmd('yes | head -n2', shell=True).read()
        self.assertEqual(value, 'y\ny')

    def test_exit_code(self):
        proc = cmd('exit 123', shell=True).run()
        self.assertEqual(proc.returncode, 123)

    def test_list_arg(self):
        value = cmd(['printf "%s\n"', 'hello', 'world']).read()
        self.assertEqual(value, 'hello\nworld')

    def test_conditional(self):
        value = cmd([
            'printf "%s\n"',
            'hello' if False else '',
            'world'
        ]).read()
        self.assertEqual(value, 'world')

    def test_guard_operator(self):
        value = cmd([
            'printf "%s\n"',
            False and '123',
            '456',
            True and '789'
            ]).read()
        self.assertEqual(value, '456\n789')

    def test_none_interpolation(self):
        value = cmd('printf "[%s]\n" {None}').read()
        self.assertEqual(value, '[]')

    def test_non_string_interpolation(self):
        value = cmd('printf "[%s]\n" {12345}').read()
        self.assertEqual(value, '[12345]')

    def test_manual_format(self):
        value = format_cmd('printf "1:%s 2:%s\n" {} {name}', 'Hello there', name='Chan Tai Man').read()
        self.assertEqual(value, '1:Hello there 2:Chan Tai Man')

    def test_raw_format(self):
        value = cmd('printf ">%s\n" Testing{"123 45":r}', shell=True).read()
        self.assertEqual(value, '>Testing123\n>45')



if __name__ == '__main__':
    unittest.main()
