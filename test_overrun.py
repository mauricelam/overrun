from overrun import cmd, format_cmd
import unittest


class TestOverrun(unittest.TestCase):

    shell = False

    def test_simple(self):
        value = cmd('printf "%s\n" "Hello world"', shell=self.shell).read()
        self.assertEqual(value, 'Hello world')

    def test_value_interpolation(self):
        testing = 'Testing 123'
        value = cmd('printf "[%s]" {testing}', shell=self.shell).read()
        self.assertEqual(value, '[Testing 123]')

    def test_value_interpolation_newline(self):
        testing = 'Testing\n123'
        value = cmd('printf "%s\n" {testing}', shell=self.shell).read()
        self.assertEqual(value, 'Testing\n123')

    def test_function_call(self):
        value = cmd('printf "[%s]\n" {"a".join("12345")}', shell=self.shell).read()
        self.assertEqual(value, '[1a2a3a4a5]')

    def test_bool_result(self):
        proc = cmd('ls /', shell=self.shell).run(silent=True)
        self.assertTrue(proc)

    def test_bool_result_fail(self):
        proc = cmd('ls /non_existent_directory', shell=self.shell).run(silent=True)
        self.assertFalse(proc)

    def test_conditional(self):
        value = cmd('printf "%s\n"',
                    'hello' if False else '',
                    'world',
                    shell=self.shell).read()
        self.assertEqual(value, 'world')

    def test_guard_operator(self):
        value = cmd('printf "%s\n"',
                    False and '123',
                    '456',
                    True and '789',
                    shell=self.shell).read()
        self.assertEqual(value, '456\n789')

    def test_none_interpolation(self):
        value = cmd('printf "[%s]\n" {None}', shell=self.shell).read()
        self.assertEqual(value, '[]')

    def test_non_string_interpolation(self):
        value = cmd('printf "[%s]\n" {12345}', shell=self.shell).read()
        self.assertEqual(value, '[12345]')

    def test_manual_format(self):
        value = format_cmd(
            'printf "1:%s 2:%s\n" {} {name}',
            'Hello there',
            name='Chan Tai Man',
            shell=self.shell).read()
        self.assertEqual(value, '1:Hello there 2:Chan Tai Man')

    def test_format_into_curly_braces(self):
        '''
        Even if the interpolated variable is a python format string, it should
        be printed out verbatim
        '''
        test = '{1}'
        value = cmd('printf "[%s]\n" {test}', shell=self.shell).read()
        self.assertEqual(value, '[{1}]')

    def test_undefined_variable(self):
        with self.assertRaises(NameError):
            cmd('printf "[%s]\n" {undefined_variable}')

    def test_variable_scope(self):
        value = cmd('printf "[%s]\n" {self}', shell=self.shell).read()
        self.assertEqual(value, f'[{str(self)}]')

    def test_list_interpolation(self):
        test = ['1 2', '3 4', '5 6']
        value = cmd('printf "[%s]" {test:l}', shell=self.shell).read()
        self.assertEqual(value, '[1 2][3 4][5 6]')

    def test_list_interpolation_manual(self):
        test = ['1', '2', '3', '4', '5']
        value = format_cmd('printf "[%s]" {test:l}', test=test, shell=self.shell).read()
        self.assertEqual(value, '[1][2][3][4][5]')

    def test_escaped_curly_braces(self):
        value = cmd('printf "[%s]" "{{curly}}"').read()
        self.assertEqual(value, '[{curly}]')


class TestOverrunShell(TestOverrun):
    shell = True

    def test_raw_format(self):
        value = cmd('printf "[%s]\n" Testing{"123 45":r}', shell=True).read()
        self.assertEqual(value, '[Testing123]\n[45]')

    def test_shell_true(self):
        value = cmd('yes | head -n2', shell=True).read()
        self.assertEqual(value, 'y\ny')

    def test_exit_code(self):
        proc = cmd('exit 123', shell=True).run()
        self.assertEqual(proc.returncode, 123)


if __name__ == '__main__':
    unittest.main()
